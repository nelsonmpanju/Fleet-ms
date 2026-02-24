# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, nowdate


@frappe.whitelist()
def get_trip_kpis(from_date=None, to_date=None):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    row = frappe.db.sql("""
        SELECT
            COUNT(*)                                                        AS total_trips,
            SUM(trip_status = 'Completed')                                  AS completed,
            SUM(trip_status = 'In Transit')                                 AS in_transit,
            SUM(trip_status = 'Breakdown')                                  AS breakdowns,
            SUM(trip_status = 'Pending')                                    AS pending,
            SUM(CASE WHEN transporter_type = 'In House' THEN 1 ELSE 0 END) AS in_house,
            SUM(CASE WHEN transporter_type != 'In House' THEN 1 ELSE 0 END) AS sub_contractor,
            IFNULL(SUM(CAST(NULLIF(TRIM(total_distance),'') AS DECIMAL(15,2))), 0) AS total_distance,
            IFNULL(SUM(total_fuel), 0)                                      AS total_fuel
        FROM `tabTrips`
        WHERE docstatus IN (0,1)
          AND date BETWEEN %(from_date)s AND %(to_date)s
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)[0]

    # Fleet utilisation: trucks with ≥1 trip / total active trucks
    total_trucks = flt(frappe.db.count("Truck", {"status": ["!=", "Disabled"]}))
    active_trucks = flt(frappe.db.sql("""
        SELECT COUNT(DISTINCT truck_number)
        FROM `tabTrips`
        WHERE docstatus IN (0,1) AND date BETWEEN %(from_date)s AND %(to_date)s
    """, {"from_date": from_date, "to_date": to_date})[0][0] or 0)

    utilisation  = round((active_trucks / total_trucks * 100), 1) if total_trucks > 0 else 0.0

    total_trips  = int(row.total_trips or 0)
    completed    = int(row.completed   or 0)
    breakdowns   = int(row.breakdowns  or 0)
    total_dist   = flt(row.total_distance)
    total_fuel   = flt(row.total_fuel)

    completion_rate = round(completed  / total_trips * 100, 1) if total_trips > 0 else 0.0
    breakdown_rate  = round(breakdowns / total_trips * 100, 1) if total_trips > 0 else 0.0
    fuel_per_km     = round(total_fuel / total_dist,        2) if total_dist  > 0 else 0.0
    avg_distance    = round(total_dist / total_trips,        1) if total_trips > 0 else 0.0

    return {
        "total_trips":     total_trips,
        "completed":       completed,
        "in_transit":      int(row.in_transit     or 0),
        "breakdowns":      breakdowns,
        "pending":         int(row.pending        or 0),
        "in_house":        int(row.in_house       or 0),
        "sub_contractor":  int(row.sub_contractor or 0),
        "total_distance":  total_dist,
        "total_fuel":      total_fuel,
        "utilisation":     utilisation,
        "active_trucks":   int(active_trucks),
        "total_trucks":    int(total_trucks),
        "completion_rate": completion_rate,
        "breakdown_rate":  breakdown_rate,
        "fuel_per_km":     fuel_per_km,
        "avg_distance":    avg_distance,
    }


@frappe.whitelist()
def get_cargo_kpis(from_date=None, to_date=None):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    row = frappe.db.sql("""
        SELECT
            COUNT(DISTINCT cr.name)              AS bookings,
            IFNULL(SUM(cd.net_weight_tonne), 0)  AS total_weight,
            IFNULL(SUM(cd.number_of_packages), 0) AS total_packages
        FROM `tabCargo Registration` cr
        LEFT JOIN `tabCargo Detail` cd ON cd.parent = cr.name
        WHERE cr.docstatus IN (0,1)
          AND cr.booking_date BETWEEN %(from_date)s AND %(to_date)s
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    r = row[0] if row else {}
    return {
        "bookings":       int(r.get("bookings", 0) or 0),
        "total_weight":   flt(r.get("total_weight", 0)),
        "total_packages": int(r.get("total_packages", 0) or 0),
    }


@frappe.whitelist()
def get_fleet_status():
    """Current truck status distribution (ignores date range — snapshot)."""
    rows = frappe.db.sql("""
        SELECT status, COUNT(*) AS cnt
        FROM `tabTruck`
        GROUP BY status
    """, as_dict=True)
    return {r.status: int(r.cnt) for r in rows}


@frappe.whitelist()
def get_trips_by_period(from_date=None, to_date=None, group_by="week"):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    fmt = "%Y-%u" if group_by == "week" else "%Y-%m"
    sql_fmt = "%%Y-%%u" if group_by == "week" else "%%Y-%%m"

    rows = frappe.db.sql(f"""
        SELECT
            DATE_FORMAT(date, '{sql_fmt}') AS period,
            SUM(transporter_type = 'In House') AS in_house,
            SUM(transporter_type != 'In House') AS sub_contractor,
            COUNT(*) AS total
        FROM `tabTrips`
        WHERE docstatus IN (0,1) AND date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY period
        ORDER BY period
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    return rows


@frappe.whitelist()
def get_top_routes(from_date=None, to_date=None, limit=10):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    rows = frappe.db.sql("""
        SELECT
            route,
            COUNT(*) AS trips,
            SUM(trip_status = 'Completed') AS completed,
            IFNULL(SUM(CAST(NULLIF(TRIM(total_distance),'') AS DECIMAL(15,2))), 0) AS total_distance,
            IFNULL(SUM(total_fuel), 0) AS total_fuel
        FROM `tabTrips`
        WHERE docstatus IN (0,1) AND date BETWEEN %(from_date)s AND %(to_date)s
          AND route IS NOT NULL AND route != ''
        GROUP BY route
        ORDER BY trips DESC
        LIMIT %(limit)s
    """, {"from_date": from_date, "to_date": to_date, "limit": int(limit)}, as_dict=True)

    return rows


@frappe.whitelist()
def get_truck_utilisation(from_date=None, to_date=None, limit=12):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    rows = frappe.db.sql("""
        SELECT
            truck_number                AS truck,
            COUNT(*) AS trips,
            SUM(trip_status = 'Completed') AS completed,
            SUM(trip_status = 'Breakdown') AS breakdowns,
            IFNULL(SUM(total_fuel), 0)  AS total_fuel
        FROM `tabTrips`
        WHERE docstatus IN (0,1)
          AND truck_number IS NOT NULL AND truck_number != ''
          AND date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY truck_number
        ORDER BY trips DESC
        LIMIT %(limit)s
    """, {"from_date": from_date, "to_date": to_date, "limit": int(limit)}, as_dict=True)

    return rows


@frappe.whitelist()
def get_driver_stats(from_date=None, to_date=None, limit=10):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    rows = frappe.db.sql("""
        SELECT
            assigned_driver             AS driver,
            driver_name,
            COUNT(*) AS trips,
            SUM(trip_status = 'Completed') AS completed,
            SUM(trip_status = 'Breakdown') AS breakdowns
        FROM `tabTrips`
        WHERE docstatus IN (0,1)
          AND assigned_driver IS NOT NULL AND assigned_driver != ''
          AND date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY assigned_driver, driver_name
        ORDER BY trips DESC
        LIMIT %(limit)s
    """, {"from_date": from_date, "to_date": to_date, "limit": int(limit)}, as_dict=True)

    return rows


@frappe.whitelist()
def get_recent_trips(from_date=None, to_date=None, limit=25):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    rows = frappe.db.sql("""
        SELECT
            name, date, route, truck_number, driver_name,
            trip_status, transporter_type, total_distance, total_fuel
        FROM `tabTrips`
        WHERE docstatus IN (0,1) AND date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY date DESC, name DESC
        LIMIT %(limit)s
    """, {"from_date": from_date, "to_date": to_date, "limit": int(limit)}, as_dict=True)

    return rows


@frappe.whitelist()
def get_live_status():
    """Real-time snapshot — not date-filtered. Shows current operational state."""
    active = frappe.db.sql("""
        SELECT trip_status, COUNT(*) AS cnt
        FROM `tabTrips`
        WHERE docstatus = 1 AND trip_status NOT IN ('Completed', 'Cancelled')
        GROUP BY trip_status
    """, as_dict=True)
    active_map = {r.trip_status: int(r.cnt) for r in active}

    pending_funds = frappe.db.sql("""
        SELECT COUNT(*) AS cnt, IFNULL(SUM(request_amount), 0) AS amount
        FROM `tabRequested Fund Details`
        WHERE parenttype = 'Trips'
          AND request_status IN ('Pending', 'Requested')
    """, as_dict=True)[0]

    on_trip = frappe.db.sql("""
        SELECT COUNT(DISTINCT truck_number) AS cnt
        FROM `tabTrips`
        WHERE docstatus = 1 AND trip_status = 'In Transit'
    """, as_dict=True)[0]

    overdue_trips = frappe.db.sql("""
        SELECT COUNT(*) AS cnt
        FROM `tabTrips`
        WHERE docstatus = 1
          AND trip_status = 'In Transit'
          AND date < DATE_SUB(CURDATE(), INTERVAL 5 DAY)
    """, as_dict=True)[0]

    return {
        "in_transit_now":      active_map.get("In Transit", 0),
        "breakdown_now":       active_map.get("Breakdown", 0),
        "pending_now":         active_map.get("Pending", 0),
        "trucks_on_trip":      int(on_trip.cnt or 0),
        "pending_fund_count":  int(pending_funds.cnt or 0),
        "pending_fund_amount": flt(pending_funds.amount),
        "overdue_trips":       int(overdue_trips.cnt or 0),
    }
