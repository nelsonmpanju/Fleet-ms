# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Fuel Cost Per KM Report
========================
Shows fuel consumption and cost efficiency per trip and per vehicle.
Key metrics: Litres/KM, Cost/KM, Cost/Litre.
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


def _columns(company_currency):
    return [
        {"fieldname": "trip",          "label": _("Trip"),          "fieldtype": "Link",    "options": "Trips", "width": 120},
        {"fieldname": "date",          "label": _("Date"),          "fieldtype": "Date",     "width": 100},
        {"fieldname": "truck",         "label": _("Truck"),         "fieldtype": "Link",    "options": "Truck", "width": 130},
        {"fieldname": "driver",        "label": _("Driver"),        "fieldtype": "Link",    "options": "Driver","width": 130},
        {"fieldname": "route",         "label": _("Route"),         "fieldtype": "Data",     "width": 150},
        {"fieldname": "distance_km",   "label": _("Distance (KM)"), "fieldtype": "Float",    "width": 110},
        {"fieldname": "fuel_litres",   "label": _("Fuel (Ltrs)"),   "fieldtype": "Float",    "width": 100},
        {"fieldname": "fuel_cost",     "label": _("Fuel Cost"),     "fieldtype": "Currency", "options": "currency", "width": 120},
        {"fieldname": "cost_per_km",   "label": _("Cost / KM"),     "fieldtype": "Currency", "options": "currency", "width": 110},
        {"fieldname": "litres_per_km", "label": _("Ltrs / KM"),     "fieldtype": "Float",    "width": 100},
        {"fieldname": "cost_per_litre","label": _("Cost / Litre"),  "fieldtype": "Currency", "options": "currency", "width": 110},
        {"fieldname": "trip_status",   "label": _("Status"),        "fieldtype": "Data",     "width": 90},
    ]


def _validate(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))
    if filters.from_date > filters.to_date:
        frappe.throw(_("From Date cannot be after To Date."))


def _get_data(filters, company_currency):
    conditions = ["t.docstatus IN (0,1)", "t.date BETWEEN %(from_date)s AND %(to_date)s"]
    params = {"from_date": filters.from_date, "to_date": filters.to_date}

    if filters.get("truck"):
        conditions.append("t.truck_number = %(truck)s")
        params["truck"] = filters.truck

    if filters.get("driver"):
        conditions.append("t.assigned_driver = %(driver)s")
        params["driver"] = filters.driver

    where = " AND ".join(conditions)

    trips = frappe.db.sql(
        f"""
        SELECT
            t.name              AS trip,
            t.date,
            t.truck_number      AS truck,
            t.assigned_driver   AS driver,
            t.route,
            t.trip_status,
            t.total_fuel        AS fuel_litres,
            t.total_distance    AS distance_km_raw
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

    # Fuel cost from Requested Fund Details (fuel expense rows)
    fuel_expense_rows = frappe.db.sql(
        f"""
        SELECT parent, IFNULL(SUM(request_amount), 0) AS fuel_cost
        FROM `tabRequested Fund Details`
        WHERE parenttype = 'Trips'
          AND request_status IN ('Approved', 'Accounts Approved')
          AND parent IN ({placeholders})
        GROUP BY parent
        """,
        trip_names,
        as_dict=True,
    )
    fuel_cost_map = {r.parent: flt(r.fuel_cost) for r in fuel_expense_rows}

    rows = []
    for t in trips:
        nm = t.trip
        # total_distance is a Data field — try to parse as float
        try:
            dist = flt(str(t.distance_km_raw).replace(",", "").strip())
        except Exception:
            dist = 0.0

        litres    = flt(t.fuel_litres)
        fuel_cost = fuel_cost_map.get(nm, 0.0)

        cost_per_km    = (fuel_cost / dist)   if dist > 0 else 0.0
        litres_per_km  = (litres / dist)      if dist > 0 else 0.0
        cost_per_litre = (fuel_cost / litres) if litres > 0 else 0.0

        rows.append(frappe._dict({
            "trip":          nm,
            "date":          t.date,
            "truck":         t.truck,
            "driver":        t.driver,
            "route":         t.route,
            "distance_km":   dist,
            "fuel_litres":   round(litres, 2),
            "fuel_cost":     fuel_cost,
            "cost_per_km":   round(cost_per_km, 4),
            "litres_per_km": round(litres_per_km, 4),
            "cost_per_litre":round(cost_per_litre, 2),
            "trip_status":   t.trip_status,
            "currency":      company_currency,
        }))

    return rows


def _chart(rows):
    if not rows:
        return None
    # Show cost/KM for first 15 trips
    sample = [r for r in rows if r.cost_per_km > 0][:15]
    if not sample:
        return None
    return {
        "data": {
            "labels": [r.trip for r in sample],
            "datasets": [{"name": _("Cost / KM"), "values": [flt(r.cost_per_km) for r in sample]}],
        },
        "type": "bar",
        "height": 240,
    }


def _summary(rows, company_currency):
    has_dist   = [r for r in rows if r.distance_km > 0]
    has_litres = [r for r in rows if r.fuel_litres > 0]
    total_dist   = sum(r.distance_km   for r in rows)
    total_litres = sum(r.fuel_litres   for r in rows)
    total_cost   = sum(r.fuel_cost     for r in rows)
    avg_cost_km  = (total_cost / total_dist)   if total_dist   > 0 else 0.0
    avg_l_km     = (total_litres / total_dist) if total_dist   > 0 else 0.0
    avg_cpl      = (total_cost / total_litres) if total_litres > 0 else 0.0
    return [
        {"label": _("Total Distance (KM)"), "value": round(total_dist, 1),   "datatype": "Float",    "indicator": "blue"},
        {"label": _("Total Fuel (Ltrs)"),   "value": round(total_litres, 1), "datatype": "Float",    "indicator": "blue"},
        {"label": _("Total Fuel Cost"),     "value": total_cost,             "datatype": "Currency", "currency": company_currency, "indicator": "orange"},
        {"label": _("Avg Cost / KM"),       "value": round(avg_cost_km, 4),  "datatype": "Float",    "indicator": "green"},
        {"label": _("Avg Ltrs / KM"),       "value": round(avg_l_km, 4),     "datatype": "Float",    "indicator": "green"},
        {"label": _("Avg Cost / Litre"),    "value": round(avg_cpl, 2),      "datatype": "Float",    "indicator": "green"},
    ]
