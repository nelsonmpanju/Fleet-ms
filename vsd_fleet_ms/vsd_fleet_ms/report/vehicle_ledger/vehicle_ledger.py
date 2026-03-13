# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Vehicle Ledger
==============
Shows all income and expense transactions linked to a vehicle (Truck)
or a specific trip, with per-row Income / Expense / Net columns.

Filter by Truck   → shows all trips for that truck within the date range.
Filter by Trip    → shows only that trip's transactions.
Both              → shows the specific trip (trip filter takes priority).

Income  = Sales Invoice income posted to GL
Expense = Purchase Invoice expense + fund disbursements posted to GL
Net     = Income − Expense  (positive = profitable)
"""

import frappe
from frappe import _
from frappe.utils import flt

from vsd_fleet_ms.utils.accounting import get_company_currency


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate(filters)

	company_currency = get_company_currency()
	trips   = _get_trips(filters)
	rows    = _get_ledger_rows(filters, trips, company_currency)
	summary = _build_summary(rows, company_currency)

	return _columns(company_currency), rows, None, None, summary


# ── columns ────────────────────────────────────────────────────────────────────

def _columns(company_currency):
	return [
		{"fieldname": "posting_date", "label": _("Date"),        "fieldtype": "Date",     "width": 100},
		{"fieldname": "trip",         "label": _("Trip"),         "fieldtype": "Link",     "options": "Trips", "width": 120},
		{"fieldname": "voucher_no",   "label": _("Reference"),    "fieldtype": "Link",     "options": "Ledger Entry", "width": 130},
		{"fieldname": "txn_type",     "label": _("Type"),         "fieldtype": "Data",     "width": 110},
		{"fieldname": "description",  "label": _("Description"),  "fieldtype": "Data",     "width": 240},
		{"fieldname": "account",      "label": _("Account"),      "fieldtype": "Data",     "width": 170},
		{"fieldname": "income",       "label": _("Income"),       "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "expense",      "label": _("Expense"),      "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "net",          "label": _("Net"),          "fieldtype": "Currency", "options": "currency", "width": 130},
	]


# ── validation ─────────────────────────────────────────────────────────────────

def _validate(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date."))
	if not filters.get("truck") and not filters.get("trip"):
		frappe.throw(_("Please select a Truck or a Trip."))


# ── helpers ────────────────────────────────────────────────────────────────────

def _get_trips(filters):
	"""Return list of trip names matching the filter."""
	if filters.get("trip"):
		return [filters.trip]

	# All trips for the selected truck within the date range
	trips = frappe.db.sql(
		"""
		SELECT name FROM `tabTrips`
		WHERE truck_number = %(truck)s
		  AND date BETWEEN %(from_date)s AND %(to_date)s
		""",
		{"truck": filters.truck, "from_date": filters.from_date, "to_date": filters.to_date},
		pluck="name",
	)
	return trips or []


def _get_ledger_rows(filters, trips, company_currency):
	if not trips:
		return []

	trip_ph = ", ".join(["%s"] * len(trips))

	# Query GL entries via Ledger Entries that reference these trips
	rows = frappe.db.sql(
		f"""
		SELECT
			gle.posting_date,
			le.reference_trip                                 AS trip,
			gle.voucher_no,
			le.entry_type                                     AS txn_type,
			COALESCE(le.remarks, '')                          AS description,
			gle.account,
			acc.account_type,
			IFNULL(gle.debit,  0)                             AS debit,
			IFNULL(gle.credit, 0)                             AS credit
		FROM   `tabGL Entry` gle
		JOIN   `tabLedger Entry` le
		       ON le.name          = gle.voucher_no
		      AND gle.voucher_type = 'Ledger Entry'
		LEFT JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE  le.reference_trip IN ({trip_ph})
		  AND  gle.posting_date BETWEEN %s AND %s
		ORDER BY le.reference_trip, gle.posting_date, gle.creation
		""",
		(*trips, filters.from_date, filters.to_date),
		as_dict=True,
	)

	result = []
	trip_totals = {}  # trip → {income, expense}

	for row in rows:
		account_type = row.get("account_type") or ""
		txn_type     = row.get("txn_type") or ""

		# Determine if this GL leg is the Income or Expense side
		# Income entry type: DR contra(AR) CR Income → Income account is credit side
		# Expense entry type: DR Expense CR contra(Payable) → Expense account is debit side
		# Payment Debit (Receive): DR Cash CR AR → Income clearance, skip (already in AR)
		# Payment Credit (Pay): DR Payable CR Cash → Expense clearance, skip

		if txn_type == "Income" and account_type == "Income":
			income_amt  = flt(row.credit)   # Income is credited
			expense_amt = 0.0
		elif txn_type == "Expense" and account_type == "Expense":
			income_amt  = 0.0
			expense_amt = flt(row.debit)    # Expense is debited
		else:
			continue  # Skip AR, AP, Cash legs — avoid double-counting

		if income_amt == 0 and expense_amt == 0:
			continue

		net = income_amt - expense_amt
		result.append(frappe._dict({
			"posting_date": row.posting_date,
			"trip":         row.trip or "",
			"voucher_no":   row.voucher_no,
			"txn_type":     txn_type,
			"description":  row.description,
			"account":      row.account,
			"income":       income_amt,
			"expense":      expense_amt,
			"net":          net,
			"currency":     company_currency,
		}))

		t = row.trip or ""
		if t not in trip_totals:
			trip_totals[t] = {"income": 0.0, "expense": 0.0}
		trip_totals[t]["income"]  += income_amt
		trip_totals[t]["expense"] += expense_amt

	# Append subtotal rows per trip when multiple trips are shown
	if len(trips) > 1:
		final = []
		seen_trips = []
		for row in result:
			t = row.trip
			if t not in seen_trips:
				seen_trips.append(t)
			final.append(row)

		# Add trip subtotal after each trip's rows
		grouped = {}
		for row in result:
			grouped.setdefault(row.trip, []).append(row)

		result = []
		for t in seen_trips:
			result.extend(grouped[t])
			tot = trip_totals.get(t, {})
			ti  = flt(tot.get("income", 0))
			te  = flt(tot.get("expense", 0))
			result.append(frappe._dict({
				"posting_date": None,
				"trip":         t,
				"voucher_no":   None,
				"txn_type":     None,
				"description":  _("Trip Total: {0}").format(t),
				"account":      None,
				"income":       ti,
				"expense":      te,
				"net":          ti - te,
				"is_total":     True,
				"currency":     company_currency,
			}))

	return result


# ── summary cards ──────────────────────────────────────────────────────────────

def _build_summary(rows, company_currency):
	data_rows    = [r for r in rows if not r.get("is_total")]
	total_income  = sum(flt(r.income)  for r in data_rows)
	total_expense = sum(flt(r.expense) for r in data_rows)
	net           = total_income - total_expense

	return [
		{"label": _("Total Income"),  "value": total_income,  "datatype": "Currency", "currency": company_currency, "indicator": "green"},
		{"label": _("Total Expense"), "value": total_expense, "datatype": "Currency", "currency": company_currency, "indicator": "red"},
		{"label": _("Net Profit"),    "value": net,           "datatype": "Currency", "currency": company_currency,
		 "indicator": "green" if net >= 0 else "red"},
	]
