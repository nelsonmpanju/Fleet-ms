# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Traccar GPS integration utilities for VSD Fleet MS.

Handles authenticated sessions with Traccar server, device lookup and
linking to Trucks, and position polling/syncing to Trip location updates.
"""

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime, get_datetime

REQUEST_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Session / Auth
# ---------------------------------------------------------------------------

def _get_settings():
    """Return Transport Settings singleton, throw if Traccar not enabled."""
    settings = frappe.get_single("Transport Settings")
    if not settings.traccar_enabled:
        frappe.throw(_("Traccar GPS is not enabled. Enable it in Transport Settings."))
    return settings


def _get_traccar_session():
    """Create an authenticated requests.Session for Traccar API.

    Returns (session, base_url) tuple.
    """
    settings = _get_settings()
    base_url = settings.traccar_server_url
    session = requests.Session()

    if settings.traccar_auth_method == "Token":
        token = settings.get_password("traccar_api_token")
        session.params = {"token": token}
    else:
        email = settings.traccar_email
        password = settings.get_password("traccar_password")
        resp = session.post(
            f"{base_url}/api/session",
            data={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            frappe.throw(
                _("Traccar authentication failed (HTTP {0}). Check credentials in Transport Settings.").format(
                    resp.status_code
                )
            )

    return session, base_url


def _api_get(session, base_url, endpoint, params=None):
    """GET helper with error handling. Returns parsed JSON or None."""
    try:
        resp = session.get(
            f"{base_url}{endpoint}",
            params=params or {},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Traccar API Error \u2014 GET {endpoint}")
        return None


# ---------------------------------------------------------------------------
# Device Operations
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_devices():
    """Fetch all devices from Traccar. Returns list of device dicts."""
    session, base_url = _get_traccar_session()
    devices = _api_get(session, base_url, "/api/devices")
    return devices or []


@frappe.whitelist()
def find_device_by_plate(plate):
    """Search Traccar devices for one matching the given license plate.

    Searches device 'name' and 'uniqueId' fields (case-insensitive,
    ignoring spaces and hyphens).
    """
    if not plate:
        return None

    norm_plate = plate.upper().replace(" ", "").replace("-", "")
    devices = get_devices()

    for device in devices:
        dev_name = (device.get("name") or "").upper().replace(" ", "").replace("-", "")
        dev_uid = (device.get("uniqueId") or "").upper().replace(" ", "").replace("-", "")
        if norm_plate in dev_name or norm_plate in dev_uid or dev_name in norm_plate:
            return device

    return None


@frappe.whitelist()
def get_device_position(device_id):
    """Get latest position for a specific Traccar device.

    Returns position dict or None.
    """
    session, base_url = _get_traccar_session()
    positions = _api_get(session, base_url, "/api/positions", {"deviceId": device_id})
    if positions and len(positions) > 0:
        return positions[0]
    return None


@frappe.whitelist()
def get_route_history(device_id, from_date, to_date):
    """Get route/position history for a device between two ISO 8601 dates."""
    session, base_url = _get_traccar_session()
    params = {
        "deviceId": device_id,
        "from": from_date,
        "to": to_date,
    }
    positions = _api_get(session, base_url, "/api/reports/route", params)
    return positions or []


# ---------------------------------------------------------------------------
# Device Linking
# ---------------------------------------------------------------------------

@frappe.whitelist()
def link_truck_to_device(truck_name):
    """Find and link a Traccar device to a Truck by license plate.

    If already linked, verifies the device still exists in Traccar.
    """
    truck = frappe.get_doc("Truck", truck_name)

    # If already linked, verify
    if truck.traccar_device_id:
        session, base_url = _get_traccar_session()
        devices = _api_get(session, base_url, "/api/devices")
        found = None
        if devices:
            for d in devices:
                if d.get("id") == truck.traccar_device_id:
                    found = d
                    break
        if found:
            _update_truck_device_fields(truck, found)
            return _("Device already linked: {0} (ID: {1})").format(
                found.get("name"), found.get("id")
            )
        else:
            truck.db_set("traccar_device_id", 0)
            truck.db_set("traccar_unique_id", "")

    plate = truck.license_plate
    if not plate:
        return _("Truck {0} has no license plate configured.").format(truck_name)

    device = find_device_by_plate(plate)
    if not device:
        return _(
            "No Traccar device found matching plate '{0}'. "
            "Please create the device in Traccar or link manually."
        ).format(plate)

    _update_truck_device_fields(truck, device)
    return _("Linked to Traccar device: {0} (ID: {1}, UniqueID: {2})").format(
        device.get("name"), device.get("id"), device.get("uniqueId")
    )


def _update_truck_device_fields(truck, device):
    """Write Traccar device info onto a Truck document using db_set."""
    truck.db_set("traccar_device_id", device.get("id"))
    truck.db_set("traccar_unique_id", device.get("uniqueId") or "")
    truck.db_set("traccar_device_status", device.get("status") or "unknown")
    if device.get("lastUpdate"):
        truck.db_set("traccar_last_update", _parse_traccar_datetime(device.get("lastUpdate")))


# ---------------------------------------------------------------------------
# Position Syncing
# ---------------------------------------------------------------------------

@frappe.whitelist()
def sync_vehicle_position(truck_name):
    """Sync the latest GPS position for a single truck.

    - Fetches latest position from Traccar
    - Updates cached fields on the Truck doc
    - If truck is On Trip, appends a GPS Update row to the trip's location_update
    """
    truck = frappe.get_doc("Truck", truck_name)

    if not truck.traccar_device_id:
        return _("Truck {0} has no linked Traccar device.").format(truck_name)

    position = get_device_position(truck.traccar_device_id)
    if not position:
        return _("No position data available for device {0}.").format(truck.traccar_device_id)

    lat = position.get("latitude")
    lng = position.get("longitude")
    fix_time = position.get("fixTime")
    address = position.get("address") or ""
    speed = position.get("speed") or 0

    if not lat or not lng:
        return _("Position has no coordinates.")

    position_dt = _parse_traccar_datetime(fix_time)

    # Skip if not newer than last update
    if truck.traccar_last_update:
        last_update = get_datetime(truck.traccar_last_update)
        if position_dt and last_update and get_datetime(position_dt) <= last_update:
            return _("Position is not newer than last update. Skipping.")

    # Update cached position on Truck
    truck.db_set("traccar_last_update", position_dt)
    truck.db_set("traccar_last_latitude", str(lat))
    truck.db_set("traccar_last_longitude", str(lng))
    truck.db_set("traccar_last_address", address)
    truck.db_set("traccar_device_status", "online" if position.get("valid") else "unknown")

    # If truck is not on a trip, just update the truck fields
    if truck.status != "On Trip" or not truck.trans_ms_current_trip:
        return _("Position updated on truck. No active trip to update.")

    trip = frappe.get_doc("Trips", truck.trans_ms_current_trip)

    # Build location string
    location_str = address if address else f"{lat:.6f}, {lng:.6f}"
    comment = ""
    if speed > 0:
        speed_kmh = round(speed * 1.852, 1)  # Traccar speed is in knots
        comment = f"Speed: {speed_kmh} km/h"

    trip.append("location_update", {
        "timestamp": position_dt,
        "location": location_str,
        "longitude": str(lng),
        "latitude": str(lat),
        "type_of_update": "GPS Update",
        "comment": comment,
    })
    trip.save(ignore_permissions=True)
    frappe.db.commit()

    return _("Position synced: {0} at {1}").format(location_str, position_dt)


@frappe.whitelist()
def sync_all_vehicle_positions():
    """Scheduled task: sync GPS positions for all trucks currently On Trip.

    Respects the sync interval configured in Transport Settings.
    """
    settings = frappe.get_single("Transport Settings")
    if not settings.traccar_enabled:
        return

    # Interval gating
    interval_map = {
        "Every 5 Minutes": 5,
        "Every 10 Minutes": 10,
        "Every 15 Minutes": 15,
        "Every 30 Minutes": 30,
    }
    interval_minutes = interval_map.get(settings.traccar_sync_interval, 15)

    cache_key = "traccar_last_sync_time"
    last_sync = frappe.cache.get_value(cache_key)
    if last_sync:
        from frappe.utils import time_diff_in_seconds
        elapsed = time_diff_in_seconds(now_datetime(), get_datetime(last_sync))
        if elapsed < (interval_minutes * 60):
            return

    frappe.cache.set_value(cache_key, str(now_datetime()))

    trucks = frappe.get_all(
        "Truck",
        filters={
            "status": "On Trip",
            "traccar_device_id": [">", 0],
        },
        fields=["name"],
    )

    for t in trucks:
        try:
            sync_vehicle_position(t.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Traccar sync failed \u2014 {t.name}")

    frappe.db.commit()


@frappe.whitelist()
def sync_all_device_links():
    """Batch-link all trucks that have a license plate but no traccar_device_id."""
    settings = frappe.get_single("Transport Settings")
    if not settings.traccar_enabled:
        return _("Traccar GPS is not enabled.")

    trucks = frappe.get_all(
        "Truck",
        filters={
            "license_plate": ["!=", ""],
            "traccar_device_id": ["in", [0, None, ""]],
        },
        fields=["name"],
    )

    results = []
    for t in trucks:
        try:
            msg = link_truck_to_device(t.name)
            results.append(f"{t.name}: {msg}")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Traccar link failed \u2014 {t.name}")

    frappe.db.commit()
    return "\n".join(results) if results else _("No unlinked trucks found.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_traccar_datetime(iso_string):
    """Convert Traccar ISO 8601 datetime to Frappe-compatible datetime string.

    Traccar returns: "2026-03-12T10:30:00.000+0000"
    Frappe expects:  "2026-03-12 10:30:00"
    """
    if not iso_string:
        return None
    try:
        clean = iso_string.replace("T", " ")
        if "+" in clean:
            clean = clean[:clean.index("+")]
        if clean.endswith("Z"):
            clean = clean[:-1]
        if "." in clean:
            clean = clean[:clean.index(".")]
        return clean.strip()
    except Exception:
        return None
