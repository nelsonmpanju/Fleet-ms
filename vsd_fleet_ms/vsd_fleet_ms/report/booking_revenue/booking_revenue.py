# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Booking Revenue Report
======================
Sales Invoices with their payment status, grouped by Customer, Trip, or Month.
Shows billed amount, collected amount, outstanding, and payment rate %.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    _validate(filters)
    data = _get_data(filters)
    return _columns(filters), data, None, _chart(data, filters), _summary(data)


def _columns(filters):
    group_by = filters.get("group_by") or "Customer"
    cols = []

    if group_by == "Month":
        cols.append({"fieldname": "period", "label": _("Month"), "fieldtype": "Data", "width": 100})
    elif group_by == "Trip":
        cols += [
            {"fieldname": "trip",     "label": _("Trip"),     "fieldtype": "Link",   "options": "Trips",    "width": 120},
            {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link",   "options": "Customer", "width": 160},
        ]
    else:  # Customer
        cols += [
            {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link",   "options": "Customer", "width": 180},
            {"fieldname": "invoices", "label": _("Invoices"), "fieldtype": "Int",     "width": 80},
        ]

    if group_by not in ("Month",):
        cols.append({"fieldname": "invoices", "label": _("Invoices"), "fieldtype": "Int", "width": 80})

    cols += [
        {"fieldname": "billed",       "label": _("Billed"),       "fieldtype": "Currency", "width": 130},
        {"fieldname": "collected",    "label": _("Collected"),    "fieldtype": "Currency", "width": 130},
        {"fieldname": "outstanding",  "label": _("Outstanding"),  "fieldtype": "Currency", "width": 130},
        {"fieldname": "payment_rate", "label": _("Paid %"),       "fieldtype": "Percent",  "width": 90},
        {"fieldname": "last_invoice", "label": _("Last Invoice"), "fieldtype": "Date",     "width": 100},
    ]
    return cols


def _validate(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))
    if filters.from_date > filters.to_date:
        frappe.throw(_("From Date cannot be after To Date."))


def _get_data(filters):
    group_by = filters.get("group_by") or "Customer"
    conditions = ["docstatus = 1", "posting_date BETWEEN %(from_date)s AND %(to_date)s"]
    params = {"from_date": filters.from_date, "to_date": filters.to_date}

    if filters.get("customer"):
        conditions.append("customer = %(customer)s")
        params["customer"] = filters.customer

    if filters.get("truck"):
        conditions.append(
            "reference_trip IN (SELECT name FROM `tabTrips` WHERE truck_number = %(truck)s)"
        )
        params["truck"] = filters.truck

    if filters.get("payment_status"):
        conditions.append("payment_status = %(payment_status)s")
        params["payment_status"] = filters.payment_status

    where = " AND ".join(conditions)

    if group_by == "Month":
        rows = frappe.db.sql(
            f"""
            SELECT
                DATE_FORMAT(posting_date, '%%Y-%%m') AS period,
                COUNT(*) AS invoices,
                SUM(grand_total)        AS billed,
                SUM(paid_amount)        AS collected,
                SUM(outstanding_amount) AS outstanding,
                MAX(posting_date)       AS last_invoice
            FROM `tabSales Invoice`
            WHERE {where}
            GROUP BY DATE_FORMAT(posting_date, '%%Y-%%m')
            ORDER BY period
            """,
            params,
            as_dict=True,
        )
    elif group_by == "Trip":
        rows = frappe.db.sql(
            f"""
            SELECT
                reference_trip AS trip,
                customer,
                COUNT(*) AS invoices,
                SUM(grand_total)        AS billed,
                SUM(paid_amount)        AS collected,
                SUM(outstanding_amount) AS outstanding,
                MAX(posting_date)       AS last_invoice
            FROM `tabSales Invoice`
            WHERE {where}
            GROUP BY reference_trip, customer
            ORDER BY last_invoice DESC
            """,
            params,
            as_dict=True,
        )
    else:  # Customer
        rows = frappe.db.sql(
            f"""
            SELECT
                customer,
                COUNT(*) AS invoices,
                SUM(grand_total)        AS billed,
                SUM(paid_amount)        AS collected,
                SUM(outstanding_amount) AS outstanding,
                MAX(posting_date)       AS last_invoice
            FROM `tabSales Invoice`
            WHERE {where}
            GROUP BY customer
            ORDER BY billed DESC
            """,
            params,
            as_dict=True,
        )

    result = []
    for r in rows:
        billed = flt(r.billed)
        collected = flt(r.collected)
        payment_rate = (collected / billed * 100) if billed > 0 else 0.0
        d = frappe._dict(r)
        d.billed = billed
        d.collected = collected
        d.outstanding = flt(r.outstanding)
        d.payment_rate = round(payment_rate, 1)
        result.append(d)

    return result


def _chart(rows, filters):
    group_by = filters.get("group_by") or "Customer"
    if not rows:
        return None

    if group_by == "Month":
        labels = [r.get("period", "") for r in rows]
    elif group_by == "Trip":
        labels = [r.get("trip", "") or "—" for r in rows[:15]]
        rows   = rows[:15]
    else:
        labels = [r.get("customer", "") or "—" for r in rows[:10]]
        rows   = rows[:10]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Billed"),      "values": [flt(r.billed)     for r in rows]},
                {"name": _("Collected"),   "values": [flt(r.collected)  for r in rows]},
                {"name": _("Outstanding"), "values": [flt(r.outstanding) for r in rows]},
            ],
        },
        "type": "bar",
        "height": 260,
    }


def _summary(rows):
    total_billed      = sum(flt(r.billed)      for r in rows)
    total_collected   = sum(flt(r.collected)   for r in rows)
    total_outstanding = sum(flt(r.outstanding) for r in rows)
    total_inv         = sum(int(r.get("invoices", 0) or 0) for r in rows)
    collection_rate   = (total_collected / total_billed * 100) if total_billed > 0 else 0.0
    return [
        {"label": _("Total Invoices"),   "value": total_inv,           "datatype": "Int",      "indicator": "blue"},
        {"label": _("Total Billed"),     "value": total_billed,        "datatype": "Currency", "indicator": "blue"},
        {"label": _("Total Collected"),  "value": total_collected,     "datatype": "Currency", "indicator": "green"},
        {"label": _("Outstanding"),      "value": total_outstanding,   "datatype": "Currency", "indicator": "red"},
        {"label": _("Collection Rate %"),"value": round(collection_rate, 1), "datatype": "Float", "indicator": "green" if collection_rate >= 80 else "orange"},
    ]
