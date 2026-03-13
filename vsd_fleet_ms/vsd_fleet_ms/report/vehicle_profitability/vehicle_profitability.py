# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Vehicle Profitability Report
============================
Per-trip breakdown: Revenue (Sales Invoices linked to trip) vs Expenses
(Requested Fund Details rows), with Gross Profit and Margin %.

Groups available: by Vehicle (truck) or flat per-trip.
"""

import frappe
from frappe import _
from frappe.utils import flt

from vsd_fleet_ms.utils.accounting import get_company_currency


def execute(filters=None):
    filters = frappe._dict(filters or {})
    _validate(filters)
    company_currency = get_company_currency()
    data = _get_data(filters, company_currency)
    return _columns(company_currency), data, None, _chart(data), _summary(data, company_currency)


# ── columns ────────────────────────────────────────────────────────────────────

def _columns(company_currency):
    return [
        {"fieldname": "trip",           "label": _("Trip"),           "fieldtype": "Link",     "options": "Trips", "width": 120},
        {"fieldname": "date",           "label": _("Date"),           "fieldtype": "Date",      "width": 100},
        {"fieldname": "truck",          "label": _("Truck"),          "fieldtype": "Link",     "options": "Truck", "width": 130},
        {"fieldname": "driver",         "label": _("Driver"),         "fieldtype": "Link",     "options": "Driver","width": 130},
        {"fieldname": "route",          "label": _("Route"),          "fieldtype": "Data",      "width": 150},
        {"fieldname": "trip_status",    "label": _("Status"),         "fieldtype": "Data",      "width": 100},
        {"fieldname": "transporter",    "label": _("Type"),           "fieldtype": "Data",      "width": 100},
        {"fieldname": "revenue",        "label": _("Revenue"),        "fieldtype": "Currency",  "options": "currency", "width": 130},
        {"fieldname": "expenses",       "label": _("Expenses"),       "fieldtype": "Currency",  "options": "currency", "width": 130},
        {"fieldname": "fuel_cost",      "label": _("Fuel Cost"),      "fieldtype": "Currency",  "options": "currency", "width": 120},
        {"fieldname": "gross_profit",   "label": _("Gross Profit"),   "fieldtype": "Currency",  "options": "currency", "width": 130},
        {"fieldname": "margin_pct",     "label": _("Margin %"),       "fieldtype": "Percent",   "width": 90},
    ]


# ── validation ─────────────────────────────────────────────────────────────────

def _validate(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))
    if filters.from_date > filters.to_date:
        frappe.throw(_("From Date cannot be after To Date."))


# ── data ───────────────────────────────────────────────────────────────────────

def _get_data(filters, company_currency):
    conditions = ["t.docstatus IN (0,1)", "t.date BETWEEN %(from_date)s AND %(to_date)s"]
    params = {"from_date": filters.from_date, "to_date": filters.to_date}

    if filters.get("truck"):
        conditions.append("t.truck_number = %(truck)s")
        params["truck"] = filters.truck

    if filters.get("transporter_type"):
        conditions.append("t.transporter_type = %(transporter_type)s")
        params["transporter_type"] = filters.transporter_type

    if filters.get("trip_status"):
        conditions.append("t.trip_status = %(trip_status)s")
        params["trip_status"] = filters.trip_status

    where = " AND ".join(conditions)

    trips = frappe.db.sql(
        f"""
        SELECT
            t.name          AS trip,
            t.date,
            t.truck_number  AS truck,
            t.assigned_driver AS driver,
            t.route,
            t.trip_status,
            t.transporter_type AS transporter,
            t.total_distance
        FROM `tabTrips` t
        WHERE {where}
        ORDER BY t.date DESC, t.name
        """,
        params,
        as_dict=True,
    )

    if not trips:
        return []

    trip_names = [t.trip for t in trips]
    placeholders = ", ".join(["%s"] * len(trip_names))

    # Revenue: Sales Invoices linked to each trip
    revenue_rows = frappe.db.sql(
        f"""
        SELECT reference_trip, IFNULL(SUM(grand_total), 0) AS revenue
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND reference_trip IN ({placeholders})
        GROUP BY reference_trip
        """,
        trip_names,
        as_dict=True,
    )
    revenue_map = {r.reference_trip: flt(r.revenue) for r in revenue_rows}

    # Expenses: Approved Requested Fund Details rows for each trip
    expense_rows = frappe.db.sql(
        f"""
        SELECT parent, IFNULL(SUM(request_amount), 0) AS expenses
        FROM `tabRequested Fund Details`
        WHERE parenttype = 'Trips'
          AND request_status IN ('Approved', 'Accounts Approved')
          AND parent IN ({placeholders})
        GROUP BY parent
        """,
        trip_names,
        as_dict=True,
    )
    expense_map = {r.parent: flt(r.expenses) for r in expense_rows}

    # Fuel cost: from GL entries linked to trip (voucher_type = Payment Entry, against = trip)
    # Use Ledger Entry trip expense as fuel cost indicator
    fuel_rows = frappe.db.sql(
        f"""
        SELECT reference_trip, IFNULL(SUM(amount), 0) AS fuel_cost
        FROM `tabLedger Entry`
        WHERE docstatus = 1
          AND source_type = 'Trip Expense'
          AND entry_type = 'Expense'
          AND reference_trip IN ({placeholders})
        GROUP BY reference_trip
        """,
        trip_names,
        as_dict=True,
    )
    fuel_map = {r.reference_trip: flt(r.fuel_cost) for r in fuel_rows}

    rows = []
    for t in trips:
        nm = t.trip
        revenue    = revenue_map.get(nm, 0.0)
        expenses   = expense_map.get(nm, 0.0)
        fuel_cost  = fuel_map.get(nm, 0.0)
        gross_profit = revenue - expenses
        margin_pct   = (gross_profit / revenue * 100) if revenue else 0.0

        rows.append(frappe._dict({
            "trip":        nm,
            "date":        t.date,
            "truck":       t.truck,
            "driver":      t.driver,
            "route":       t.route,
            "trip_status": t.trip_status,
            "transporter": t.transporter,
            "revenue":     revenue,
            "expenses":    expenses,
            "fuel_cost":   fuel_cost,
            "gross_profit": gross_profit,
            "margin_pct":  round(margin_pct, 2),
            "currency":    company_currency,
        }))

    return rows


# ── chart & summary ────────────────────────────────────────────────────────────

def _chart(rows):
    if not rows:
        return None
    labels  = [r.trip for r in rows[:15]]
    revenue = [flt(r.revenue)    for r in rows[:15]]
    expense = [flt(r.expenses)   for r in rows[:15]]
    profit  = [flt(r.gross_profit) for r in rows[:15]]
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Revenue"),     "values": revenue},
                {"name": _("Expenses"),    "values": expense},
                {"name": _("Gross Profit"), "values": profit},
            ],
        },
        "type": "bar",
        "height": 280,
    }


def _summary(rows, company_currency):
    total_rev  = sum(flt(r.revenue)      for r in rows)
    total_exp  = sum(flt(r.expenses)     for r in rows)
    total_fuel = sum(flt(r.fuel_cost)    for r in rows)
    total_gp   = sum(flt(r.gross_profit) for r in rows)
    avg_margin = (total_gp / total_rev * 100) if total_rev else 0.0
    return [
        {"label": _("Total Revenue"),     "value": total_rev,  "datatype": "Currency", "currency": company_currency, "indicator": "blue"},
        {"label": _("Total Expenses"),    "value": total_exp,  "datatype": "Currency", "currency": company_currency, "indicator": "red"},
        {"label": _("Total Fuel Cost"),   "value": total_fuel, "datatype": "Currency", "currency": company_currency, "indicator": "orange"},
        {"label": _("Gross Profit"),      "value": total_gp,   "datatype": "Currency", "currency": company_currency, "indicator": "green" if total_gp >= 0 else "red"},
        {"label": _("Avg Margin %"),      "value": round(avg_margin, 2), "datatype": "Float", "indicator": "green" if avg_margin >= 0 else "red"},
    ]
