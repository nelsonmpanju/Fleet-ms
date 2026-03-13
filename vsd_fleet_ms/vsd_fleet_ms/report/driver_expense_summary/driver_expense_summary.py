# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Driver Expense Summary Report
==============================
Aggregates all approved Requested Fund Details rows by driver,
broken down by expense type. Shows per-trip detail when a driver filter is set.
"""

import frappe
from frappe import _
from frappe.utils import flt

from vsd_fleet_ms.utils.accounting import get_company_currency


def execute(filters=None):
    filters = frappe._dict(filters or {})
    _validate(filters)
    company_currency = get_company_currency()
    data = _get_data(filters)
    return _columns(filters), data, None, _chart(data, filters), _summary(data, company_currency)


def _columns(filters):
    cols = [
        {"fieldname": "driver",       "label": _("Driver"),        "fieldtype": "Link",    "options": "Driver",  "width": 160},
        {"fieldname": "trip",         "label": _("Trip"),          "fieldtype": "Link",    "options": "Trips",   "width": 120},
        {"fieldname": "expense_type", "label": _("Expense Type"),  "fieldtype": "Data",     "width": 160},
        {"fieldname": "description",  "label": _("Description"),   "fieldtype": "Data",     "width": 200},
        {"fieldname": "requested_date","label": _("Date"),          "fieldtype": "Date",     "width": 100},
        {"fieldname": "amount",       "label": _("Amount"),        "fieldtype": "Currency", "options": "currency", "width": 130},
        {"fieldname": "currency",     "label": _("Currency"),      "fieldtype": "Data",     "width": 80},
        {"fieldname": "request_status","label": _("Status"),       "fieldtype": "Data",     "width": 120},
        {"fieldname": "payment_ref",  "label": _("Payment Ref"),   "fieldtype": "Data",     "width": 120},
    ]
    return cols


def _validate(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))
    if filters.from_date > filters.to_date:
        frappe.throw(_("From Date cannot be after To Date."))


def _get_data(filters):
    conditions = [
        "fd.parenttype = 'Trips'",
        "fd.request_status IN ('Approved', 'Accounts Approved')",
        "t.date BETWEEN %(from_date)s AND %(to_date)s",
    ]
    params = {"from_date": filters.from_date, "to_date": filters.to_date}

    if filters.get("driver"):
        conditions.append("(fd.party = %(driver)s OR t.assigned_driver = %(driver)s)")
        params["driver"] = filters.driver

    if filters.get("expense_type"):
        conditions.append("fd.expense_type LIKE %(expense_type)s")
        params["expense_type"] = f"%{filters.expense_type}%"

    if filters.get("trip"):
        conditions.append("fd.parent = %(trip)s")
        params["trip"] = filters.trip

    where = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(fd.party, t.assigned_driver) AS driver,
            fd.parent                AS trip,
            fd.expense_type,
            fd.request_description   AS description,
            fd.requested_date,
            fd.request_amount        AS amount,
            fd.request_currency      AS currency,
            fd.request_status,
            fd.journal_entry         AS payment_ref
        FROM `tabRequested Fund Details` fd
        INNER JOIN `tabTrips` t ON t.name = fd.parent
        WHERE {where}
        ORDER BY driver, t.date, fd.expense_type
        """,
        params,
        as_dict=True,
    )

    return rows


def _chart(rows, filters):
    if not rows:
        return None

    # Group by expense type
    by_type = {}
    for r in rows:
        key = r.expense_type or "Other"
        by_type[key] = by_type.get(key, 0) + flt(r.amount)

    sorted_types = sorted(by_type.items(), key=lambda x: -x[1])[:10]
    labels  = [t[0] for t in sorted_types]
    amounts = [t[1] for t in sorted_types]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Total Expense"), "values": amounts}],
        },
        "type": "pie" if len(labels) <= 6 else "bar",
        "height": 240,
    }


def _summary(rows, company_currency):
    total = sum(flt(r.amount) for r in rows)
    by_driver = {}
    for r in rows:
        d = r.driver or "Unknown"
        by_driver[d] = by_driver.get(d, 0) + flt(r.amount)

    top_driver = max(by_driver, key=by_driver.get) if by_driver else "—"
    top_amount = by_driver.get(top_driver, 0)

    return [
        {"label": _("Total Expense Rows"), "value": len(rows),     "datatype": "Int",      "indicator": "blue"},
        {"label": _("Total Amount"),        "value": total,         "datatype": "Currency", "currency": company_currency, "indicator": "orange"},
        {"label": _("Drivers"),             "value": len(by_driver),"datatype": "Int",      "indicator": "blue"},
        {"label": _("Top Driver"),          "value": top_driver,    "datatype": "Data",     "indicator": "red"},
        {"label": _("Top Driver Amount"),   "value": top_amount,    "datatype": "Currency", "currency": company_currency, "indicator": "red"},
    ]
