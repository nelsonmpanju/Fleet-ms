# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Compliance utilities for VSD Fleet MS.
Handles:
  - Parking Bills via TARURA API
  - Vehicle Fines via TPF JSON API
  - Insurance Cover Notes via TIRA API
"""

import base64
import hashlib
import json as _json
import re
from datetime import datetime

import frappe
import requests
from frappe.utils import today, now, date_diff, getdate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARURA_API_KEY = "e9f3e572-db87-4eff-9ed6-66922f1f7f24"
# Port 6003 is plain HTTP — HTTPS causes SSL handshake failure
TARURA_BASE_URL = (
    "http://termis.tarura.go.tz:6003/termis-parking-service/api/v1"
    "/parkingDetails/debts/plateNumber/"
)
TPF_API_URL = "https://tms.tpf.go.tz/api/OffenceCheck"
TPF_SECRET_KEY = "irtismutDkjQBbZKEUn8hw7WqKdxld01E6HIY"
TIRA_URL = "https://tiramis.tira.go.tz/covernote/api/public/portal/verify"
REQUEST_TIMEOUT = 30  # seconds


# ===========================================================================
# PARKING BILLS — TARURA API
# ===========================================================================

@frappe.whitelist()
def sync_parking_bills(truck):
    """Fetch parking bills for a single truck from TARURA and upsert records."""
    truck_doc = frappe.get_doc("Truck", truck)
    plate = truck_doc.license_plate
    if not plate:
        return f"Truck {truck} has no license plate configured."

    bills = _fetch_tarura_bills(plate)
    if bills is None:
        return "Could not reach TARURA API. Please try again later."

    created, updated = 0, 0
    for row in bills:
        # The API wraps bill data inside a "bill" key per row
        bill = row.get("bill", row) if isinstance(row, dict) else row
        bill_id = str(bill.get("billId") or bill.get("bill_id") or "")
        if not bill_id:
            continue

        exists = frappe.db.exists("Parking Bill", {"bill_id": bill_id})
        if exists:
            doc = frappe.get_doc("Parking Bill", exists)
            _map_tarura_bill(doc, row, truck, plate)
            doc.last_synced = now()
            doc.save(ignore_permissions=True)
            updated += 1
        else:
            doc = frappe.new_doc("Parking Bill")
            doc.truck = truck
            doc.plate_number = plate
            _map_tarura_bill(doc, row, truck, plate)
            doc.last_synced = now()
            doc.insert(ignore_permissions=True)
            created += 1

    frappe.db.commit()
    return f"Parking bills synced: {created} created, {updated} updated."


def _fetch_tarura_bills(plate):
    """Call TARURA API and return list of bill dicts, or None on error."""
    headers = {"x-transfer-key": TARURA_API_KEY}
    url = TARURA_BASE_URL + plate
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # API returns {"status": true, "code": 6000, "data": [...]}
        if isinstance(data, dict):
            if data.get("code") == 6000:
                return data.get("data") or []
            # code 6004 = no records found
            if data.get("code") == 6004:
                return []
            return data.get("data") or data.get("bills") or []
        if isinstance(data, list):
            return data
        return []
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"TARURA API Error — {plate}")
        return None


def _map_tarura_bill(doc, row, truck, plate):
    """Map a TARURA API row onto a Parking Bill document."""
    # The API returns nested data: row has "bill" and "parkingDetails"
    bill = row.get("bill", row) if isinstance(row, dict) else row

    doc.truck = truck
    doc.plate_number = plate
    doc.bill_id = str(bill.get("billId") or bill.get("bill_id") or "")
    doc.amount = _safe_float(bill.get("billedAmount") or bill.get("amount") or 0)
    doc.issued_date = _safe_date(bill.get("generatedDate") or bill.get("issuedDate"))
    doc.due_date = _safe_date(bill.get("expiryDate") or bill.get("dueDate"))

    # Extract location from parkingDetails if available
    parking_details = row.get("parkingDetails") if isinstance(row, dict) else None
    if parking_details and isinstance(parking_details, list) and parking_details:
        first = parking_details[0]
        doc.location = first.get("locationName") or first.get("location") or ""
    elif not doc.location:
        doc.location = ""

    doc.offence = bill.get("billDescription") or bill.get("offence") or ""
    doc.description = bill.get("remarks") or bill.get("description") or ""

    # billPayed is a boolean in the API
    if bill.get("billPayed") or bill.get("billPaid"):
        doc.status = "Paid"
    else:
        raw_status = str(row.get("billStatus", "") if isinstance(row, dict) else "").strip()
        if raw_status.lower() in ("true", "1"):
            doc.status = "Outstanding"
        elif raw_status.title() in ("Outstanding", "Paid", "Waived"):
            doc.status = raw_status.title()
        else:
            doc.status = "Outstanding"


@frappe.whitelist()
def sync_all_parking_bills():
    """Scheduled: sync parking bills for every truck that has a license plate."""
    trucks = frappe.get_all("Truck", filters={"license_plate": ["!=", ""]}, fields=["name"])
    results = []
    for t in trucks:
        try:
            msg = sync_parking_bills(t.name)
            results.append(f"{t.name}: {msg}")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Parking sync failed — {t.name}")
    frappe.db.commit()
    return "\n".join(results)


# ===========================================================================
# VEHICLE FINES — TPF JSON API
# ===========================================================================

def _decrypt_tpf_payload(payload_b64):
    """Decrypt AES-CBC encrypted payload from TPF API."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_padding

    key = TPF_SECRET_KEY[:32].encode("utf-8").ljust(32, b"\0")
    iv_hex = hashlib.sha256(TPF_SECRET_KEY.encode("latin-1")).hexdigest()[:16]
    iv = iv_hex.encode("utf-8")

    # Handle double base64 encoding
    decoded = base64.b64decode(payload_b64)
    try:
        decoded_str = decoded.decode("ascii")
        if re.match(r"^[A-Za-z0-9+/]+=*$", decoded_str.strip()) and len(decoded_str) % 4 == 0:
            decoded = base64.b64decode(decoded_str)
    except (UnicodeDecodeError, Exception):
        pass

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(decoded) + decryptor.finalize()

    unpadder = sym_padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(plaintext) + unpadder.finalize()

    return _json.loads(plaintext.decode("utf-8"))


def _fetch_tpf_fines(plate):
    """Call TPF JSON API and return list of fine dicts, or None on error."""
    try:
        resp = requests.post(
            TPF_API_URL,
            json={"vehicle": plate},
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        if resp.status_code == 429:
            frappe.log_error("TPF API rate limit hit", f"TPF Rate Limit — {plate}")
            return None
        resp.raise_for_status()
        data = resp.json()
        if not data.get("payload"):
            return []
        result = _decrypt_tpf_payload(data["payload"])
        if result.get("status") != "success":
            return []
        return result.get("pending_transactions") or []
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"TPF API error — {plate}")
        return None


def _fetch_tpf_by_reference(reference):
    """Call TPF API by reference number to get updated fine status."""
    try:
        resp = requests.post(
            TPF_API_URL,
            json={"reference": reference},
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        if resp.status_code == 429:
            return None
        resp.raise_for_status()
        data = resp.json()
        if not data.get("payload"):
            return []
        result = _decrypt_tpf_payload(data["payload"])
        if result.get("status") != "success":
            return []
        return result.get("pending_transactions") or []
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"TPF API error — ref {reference}")
        return None


@frappe.whitelist()
def sync_vehicle_fines(truck):
    """Fetch fines for a single truck from TPF API and upsert records."""
    truck_doc = frappe.get_doc("Truck", truck)
    plate = truck_doc.license_plate
    if not plate:
        return f"Truck {truck} has no license plate configured."

    fines = _fetch_tpf_fines(plate)
    if fines is None:
        return "Could not reach TPF. Please try again later."

    created, updated = 0, 0
    for fine in fines:
        ref = str(fine.get("reference") or fine.get("reference_number") or "")
        if not ref:
            continue

        exists = frappe.db.exists("Vehicle Fine Record", {"reference": ref})
        if exists:
            doc = frappe.get_doc("Vehicle Fine Record", exists)
            _map_tpf_fine(doc, fine, truck, plate)
            doc.last_synced = now()
            doc.save(ignore_permissions=True)
            updated += 1
        else:
            doc = frappe.new_doc("Vehicle Fine Record")
            doc.reference = ref
            doc.truck = truck
            doc.vehicle = plate
            _map_tpf_fine(doc, fine, truck, plate)
            doc.last_synced = now()
            doc.insert(ignore_permissions=True)
            created += 1

    frappe.db.commit()
    return f"Vehicle fines synced: {created} created, {updated} updated."


def _map_tpf_fine(doc, fine, truck, plate):
    doc.truck = truck
    doc.vehicle = plate
    doc.issued_date = _safe_date(fine.get("issued_date") or fine.get("issuedDate"))
    doc.offence = fine.get("offence") or fine.get("offense") or ""
    doc.officer = fine.get("officer") or ""
    doc.licence = fine.get("licence") or fine.get("license") or ""
    doc.location = fine.get("location") or ""
    doc.charge = _safe_float(fine.get("charge") or 0)
    doc.penalty = _safe_float(fine.get("penalty") or 0)
    doc.total = _safe_float(fine.get("total") or fine.get("amount") or 0)
    doc.qr_code = fine.get("qr_code") or fine.get("qrCode") or ""
    raw_status = str(fine.get("status") or "PENDING").upper()
    if raw_status in ("PENDING", "PAID", "CANCELLED"):
        doc.status = raw_status
    else:
        doc.status = "PENDING"


@frappe.whitelist()
def update_fine_status(reference):
    """Call TPF API to refresh a single fine's status."""
    doc = frappe.get_doc("Vehicle Fine Record", reference)
    fines = _fetch_tpf_by_reference(reference)
    if fines is None:
        return "Could not reach TPF. Please try again later."

    for fine in fines:
        ref = str(fine.get("reference") or fine.get("reference_number") or "")
        if ref == reference:
            _map_tpf_fine(doc, fine, doc.truck, doc.vehicle)
            doc.last_synced = now()
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return f"Fine {reference} status updated to {doc.status}."

    return f"Fine {reference} not found in TPF results."


@frappe.whitelist()
def sync_all_vehicle_fines():
    """Scheduled: fetch vehicle fines for every truck."""
    trucks = frappe.get_all("Truck", filters={"license_plate": ["!=", ""]}, fields=["name"])
    results = []
    for t in trucks:
        try:
            msg = sync_vehicle_fines(t.name)
            results.append(f"{t.name}: {msg}")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Fine sync failed — {t.name}")
    frappe.db.commit()
    return "\n".join(results)


# ===========================================================================
# INSURANCE COVER NOTES — TIRA API
# ===========================================================================

def _timestamp_to_date(value):
    """Convert Unix timestamp in milliseconds to date, or return None."""
    if not value:
        return None
    try:
        if isinstance(value, (int, float)) and value > 1_000_000_000_000:
            # Milliseconds — convert to seconds
            return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d")
        if isinstance(value, (int, float)) and value > 1_000_000_000:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d")
        return _safe_date(value)
    except Exception:
        return _safe_date(value)


@frappe.whitelist()
def sync_insurance(truck):
    """Fetch insurance cover note for a single truck from TIRA and upsert."""
    truck_doc = frappe.get_doc("Truck", truck)
    reg_number = truck_doc.license_plate
    if not reg_number:
        return f"Truck {truck} has no registration number configured."

    notes = _fetch_tira_covernote(reg_number)
    if notes is None:
        return "Could not reach TIRA API. Please try again later."
    if not notes:
        return f"No insurance cover notes found for {reg_number}."

    created, updated = 0, 0
    for note in notes:
        cover_no = str(note.get("coverNoteNumber") or note.get("cover_note_number") or "")
        if not cover_no:
            continue

        exists = frappe.db.exists("Insurance Cover Note", {"cover_note_number": cover_no})
        if exists:
            doc = frappe.get_doc("Insurance Cover Note", exists)
            _map_tira_note(doc, note, truck, reg_number)
            doc.last_synced = now()
            doc.save(ignore_permissions=True)
            updated += 1
        else:
            doc = frappe.new_doc("Insurance Cover Note")
            doc.cover_note_number = cover_no
            doc.truck = truck
            _map_tira_note(doc, note, truck, reg_number)
            doc.last_synced = now()
            doc.insert(ignore_permissions=True)
            created += 1

    frappe.db.commit()
    return f"Insurance notes synced: {created} created, {updated} updated."


def _fetch_tira_covernote(reg_number):
    """Call TIRA API and return list of cover note dicts, or None on error."""
    payload = {"paramType": 2, "searchParam": reg_number}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        resp = requests.post(
            TIRA_URL, json=payload, headers=headers,
            timeout=REQUEST_TIMEOUT, verify=False
        )
        resp.raise_for_status()
        data = resp.json()
        # API returns {"code": 1000, "data": [...]} on success
        if isinstance(data, dict):
            if data.get("code") == 1000:
                result = data.get("data")
                if isinstance(result, list):
                    return result
                if result:
                    return [result]
                return []
            return []
        if isinstance(data, list):
            return data
        return []
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"TIRA API Error — {reg_number}")
        return None


def _map_tira_note(doc, note, truck, reg_number):
    doc.truck = truck
    # Extract plate from motor sub-object or top-level
    motor = note.get("motor") or {}
    doc.vehicle = (
        motor.get("registrationNumber")
        or note.get("vehiclePlateNumber")
        or reg_number
    )
    doc.registration_number = reg_number

    # Company info
    company = note.get("company") or {}
    doc.insurance_company = company.get("companyName") or note.get("insurerName") or ""
    doc.policy_number = note.get("policyNumber") or note.get("policy_number") or ""
    doc.policy_type = note.get("policyType") or note.get("policy_type") or ""

    # Dates are Unix timestamps in milliseconds
    doc.cover_note_start_date = _timestamp_to_date(
        note.get("coverNoteStartDate") or note.get("start_date")
    )
    doc.cover_note_end_date = _timestamp_to_date(
        note.get("coverNoteEndDate") or note.get("coverNoteExpiryDate") or note.get("end_date")
    )
    doc.sum_insured = _safe_float(
        note.get("totalPremiumAmountIncludingTax")
        or note.get("sumInsured")
        or note.get("sum_insured")
        or 0
    )

    # Compute days_to_expiry and status
    if doc.cover_note_end_date:
        days = date_diff(doc.cover_note_end_date, today())
        doc.days_to_expiry = days
        if days < 0:
            doc.status = "Expired"
        elif days <= 30:
            doc.status = "Expiring Soon"
        else:
            doc.status = "Active"


@frappe.whitelist()
def sync_all_insurance():
    """Scheduled: sync insurance cover notes for every truck."""
    trucks = frappe.get_all("Truck", filters={"license_plate": ["!=", ""]}, fields=["name"])
    results = []
    for t in trucks:
        try:
            msg = sync_insurance(t.name)
            results.append(f"{t.name}: {msg}")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Insurance sync failed — {t.name}")
    frappe.db.commit()
    return "\n".join(results)


# ===========================================================================
# COMBINED SYNC + SUMMARY
# ===========================================================================

@frappe.whitelist()
def sync_truck_compliance(truck):
    """
    Sync all compliance data for a single truck (parking, fines, insurance).
    Returns a combined status message.
    """
    results = []
    for fn in (sync_parking_bills, sync_vehicle_fines, sync_insurance):
        try:
            msg = fn(truck)
            results.append(msg)
        except Exception as e:
            results.append(str(e))
    return "\n".join(results)


@frappe.whitelist()
def get_truck_compliance_summary(truck):
    """Return compliance counts for a truck (used by truck.js dashboard section)."""
    return {
        "outstanding_bills": frappe.db.count(
            "Parking Bill", {"truck": truck, "status": "Outstanding"}
        ),
        "unpaid_fines": frappe.db.count(
            "Vehicle Fine Record", {"truck": truck, "status": "PENDING"}
        ),
        "active_insurance": frappe.db.count(
            "Insurance Cover Note", {"truck": truck, "status": "Active"}
        ),
        "expiring_insurance": frappe.db.count(
            "Insurance Cover Note", {"truck": truck, "status": "Expiring Soon"}
        ),
        "expired_insurance": frappe.db.count(
            "Insurance Cover Note", {"truck": truck, "status": "Expired"}
        ),
    }


# ===========================================================================
# HELPERS
# ===========================================================================

def _safe_date(value):
    if not value:
        return None
    try:
        return getdate(str(value)[:10])
    except Exception:
        return None


def _safe_float(value):
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0
