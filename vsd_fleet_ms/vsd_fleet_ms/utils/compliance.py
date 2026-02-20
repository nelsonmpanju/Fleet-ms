# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Compliance utilities for VSD Fleet MS.
Handles:
  - Parking Bills via TARURA API
  - Vehicle Fines via TPF web scraping
  - Insurance Cover Notes via TIRA API
"""

import frappe
import requests
from frappe.utils import today, now, date_diff, getdate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARURA_API_KEY = "e9f3e572-db87-4eff-9ed6-66922f1f7f24"
TARURA_BASE_URL = (
    "https://termis.tarura.go.tz:6003/termis-parking-service/api/v1"
    "/parkingDetails/debts/plateNumber/"
)
TPF_URL = "https://tms.tpf.go.tz/"
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
    for bill in bills:
        bill_id = str(bill.get("billId") or bill.get("bill_id") or "")
        if not bill_id:
            continue

        exists = frappe.db.exists("Parking Bill", {"bill_id": bill_id})
        if exists:
            doc = frappe.get_doc("Parking Bill", exists)
            _map_tarura_bill(doc, bill, truck, plate)
            doc.last_synced = now()
            doc.save(ignore_permissions=True)
            updated += 1
        else:
            doc = frappe.new_doc("Parking Bill")
            doc.truck = truck
            doc.plate_number = plate
            _map_tarura_bill(doc, bill, truck, plate)
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
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        resp.raise_for_status()
        data = resp.json()
        # API may return a list directly or wrapped in a key
        if isinstance(data, list):
            return data
        return data.get("data") or data.get("bills") or []
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"TARURA API Error — {plate}")
        return None


def _map_tarura_bill(doc, bill, truck, plate):
    """Map a TARURA bill dict onto a Parking Bill document."""
    doc.truck = truck
    doc.plate_number = plate
    doc.bill_id = str(bill.get("billId") or bill.get("bill_id") or "")
    doc.amount = float(bill.get("amount") or bill.get("totalAmount") or 0)
    doc.issued_date = _safe_date(bill.get("issuedDate") or bill.get("issued_date"))
    doc.due_date = _safe_date(bill.get("dueDate") or bill.get("due_date"))
    doc.location = bill.get("location") or bill.get("parkingArea") or ""
    doc.offence = bill.get("offence") or bill.get("violation") or ""
    doc.description = bill.get("description") or ""
    raw_status = str(bill.get("status") or "Outstanding").strip().title()
    if raw_status in ("Outstanding", "Paid", "Waived"):
        doc.status = raw_status
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
# VEHICLE FINES — TPF web scraping
# ===========================================================================

@frappe.whitelist()
def sync_vehicle_fines(truck):
    """Scrape TPF for fines related to a single truck and upsert records."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "BeautifulSoup4 is not installed. Run: pip install beautifulsoup4"

    truck_doc = frappe.get_doc("Truck", truck)
    plate = truck_doc.license_plate
    if not plate:
        return f"Truck {truck} has no license plate configured."

    fines = _scrape_tpf_fines(plate, BeautifulSoup)
    if fines is None:
        return "Could not reach TPF website. Please try again later."

    created, updated = 0, 0
    for fine in fines:
        ref = fine.get("reference", "")
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


def _scrape_tpf_fines(plate, BeautifulSoup):
    """
    POST to TPF and parse the HTML response.
    Returns list of fine dicts or None on failure.
    """
    session = requests.Session()
    try:
        # Load the form to get formSig / CSRF token
        resp = session.get(TPF_URL, timeout=REQUEST_TIMEOUT, verify=False)
        soup = BeautifulSoup(resp.text, "html.parser")

        form_sig_tag = soup.find("input", {"name": "formSig"})
        form_sig = form_sig_tag["value"] if form_sig_tag else ""

        payload = {
            "service": "VEHICLE",
            "vehicle": plate,
            "formSig": form_sig,
        }
        resp2 = session.post(TPF_URL, data=payload, timeout=REQUEST_TIMEOUT, verify=False)
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        return _parse_tpf_table(soup2)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"TPF scrape error — {plate}")
        return None


def _parse_tpf_table(soup):
    """Parse the results table from TPF response HTML."""
    fines = []
    table = soup.find("table")
    if not table:
        return fines

    rows = table.find_all("tr")
    for row in rows[1:]:  # skip header
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cols) < 5:
            continue
        fine = {
            "reference": cols[0],
            "issued_date": _safe_date(cols[1]),
            "offence": cols[2],
            "officer": cols[3] if len(cols) > 3 else "",
            "charge": _safe_float(cols[4] if len(cols) > 4 else "0"),
            "penalty": _safe_float(cols[5] if len(cols) > 5 else "0"),
            "total": _safe_float(cols[6] if len(cols) > 6 else "0"),
            "status": cols[7].upper() if len(cols) > 7 else "PENDING",
            "location": cols[8] if len(cols) > 8 else "",
            "licence": cols[9] if len(cols) > 9 else "",
            "qr_code": cols[10] if len(cols) > 10 else "",
        }
        fines.append(fine)
    return fines


def _map_tpf_fine(doc, fine, truck, plate):
    doc.truck = truck
    doc.vehicle = plate
    doc.issued_date = fine.get("issued_date")
    doc.offence = fine.get("offence") or ""
    doc.officer = fine.get("officer") or ""
    doc.licence = fine.get("licence") or ""
    doc.location = fine.get("location") or ""
    doc.charge = fine.get("charge") or 0
    doc.penalty = fine.get("penalty") or 0
    doc.total = fine.get("total") or 0
    doc.qr_code = fine.get("qr_code") or ""
    raw_status = str(fine.get("status") or "PENDING").upper()
    if raw_status in ("PENDING", "PAID", "CANCELLED"):
        doc.status = raw_status
    else:
        doc.status = "PENDING"


@frappe.whitelist()
def update_fine_status(reference):
    """Re-scrape TPF to refresh a single fine's status."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "BeautifulSoup4 is not installed."

    doc = frappe.get_doc("Vehicle Fine Record", reference)
    plate = doc.vehicle
    fines = _scrape_tpf_fines(plate, BeautifulSoup)
    if fines is None:
        return "Could not reach TPF website."

    for fine in fines:
        if fine.get("reference") == reference:
            _map_tpf_fine(doc, fine, doc.truck, plate)
            doc.last_synced = now()
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return f"Fine {reference} status updated to {doc.status}."

    return f"Fine {reference} not found in TPF results."


@frappe.whitelist()
def sync_all_vehicle_fines():
    """Scheduled: scrape vehicle fines for every truck."""
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

@frappe.whitelist()
def sync_insurance(truck):
    """Fetch insurance cover note for a single truck from TIRA and upsert."""
    truck_doc = frappe.get_doc("Truck", truck)
    reg_number = truck_doc.license_plate  # registration number = plate
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
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(
            TIRA_URL, json=payload, headers=headers,
            timeout=REQUEST_TIMEOUT, verify=False
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("data") or data.get("coverNotes") or [data] if data else []
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"TIRA API Error — {reg_number}")
        return None


def _map_tira_note(doc, note, truck, reg_number):
    doc.truck = truck
    doc.vehicle = note.get("vehiclePlateNumber") or note.get("vehicle") or reg_number
    doc.registration_number = reg_number
    doc.insurance_company = note.get("insurerName") or note.get("insurance_company") or ""
    doc.policy_number = note.get("policyNumber") or note.get("policy_number") or ""
    doc.policy_type = note.get("policyType") or note.get("policy_type") or ""
    doc.cover_note_start_date = _safe_date(
        note.get("coverNoteStartDate") or note.get("start_date")
    )
    doc.cover_note_end_date = _safe_date(
        note.get("coverNoteExpiryDate") or note.get("end_date")
    )
    doc.sum_insured = _safe_float(note.get("sumInsured") or note.get("sum_insured") or 0)

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
    plate = frappe.db.get_value("Truck", truck, "license_plate") or ""
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
