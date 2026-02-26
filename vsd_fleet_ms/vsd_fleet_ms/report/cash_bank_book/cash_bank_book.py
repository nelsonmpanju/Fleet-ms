# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Cash / Bank Book
================
Shows every receipt (Money In) and payment (Money Out) through a selected
Cash or Bank account within a date range, with a running balance.

Money In  → account is debited   (cash/asset increases)
Money Out → account is credited  (cash/asset decreases)
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate(filters)

	opening  = _get_opening_balance(filters)
	rows     = _get_period_entries(filters, opening)
	summary  = _build_summary(rows, opening)

	return _columns(), rows, None, None, summary


# ── columns ────────────────────────────────────────────────────────────────────

def _columns():
	return [
		{"fieldname": "posting_date", "label": _("Date"),       "fieldtype": "Date",     "width": 100},
		{"fieldname": "voucher_no",   "label": _("Reference"),   "fieldtype": "Link",     "options": "Ledger Entry", "width": 130},
		{"fieldname": "txn_type",     "label": _("Type"),        "fieldtype": "Data",     "width": 110},
		{"fieldname": "description",  "label": _("Description"), "fieldtype": "Data",     "width": 280},
		{"fieldname": "party",        "label": _("Party"),       "fieldtype": "Data",     "width": 130},
		{"fieldname": "money_in",     "label": _("Money In"),    "fieldtype": "Currency", "width": 130},
		{"fieldname": "money_out",    "label": _("Money Out"),   "fieldtype": "Currency", "width": 130},
		{"fieldname": "balance",      "label": _("Balance"),     "fieldtype": "Currency", "width": 140},
	]


# ── validation ─────────────────────────────────────────────────────────────────

def _validate(filters):
	if not filters.get("account"):
		frappe.throw(_("Please select a Cash / Bank Account."))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date."))


# ── data helpers ───────────────────────────────────────────────────────────────

def _get_opening_balance(filters):
	result = frappe.db.sql(
		"""
		SELECT IFNULL(SUM(debit - credit), 0) AS balance
		FROM   `tabGL Entry`
		WHERE  account      = %(account)s
		  AND  posting_date < %(from_date)s
		""",
		{"account": filters.account, "from_date": filters.from_date},
		as_dict=True,
	)
	return flt(result[0].balance) if result else 0.0


def _get_period_entries(filters, opening_balance):
	rows = frappe.db.sql(
		"""
		SELECT
			gle.posting_date,
			gle.voucher_no,
			COALESCE(le.entry_type, gle.voucher_type)        AS txn_type,
			COALESCE(le.remarks, '')                          AS description,
			COALESCE(le.party, gle.party, '')                 AS party,
			IFNULL(gle.debit,  0)                             AS money_in,
			IFNULL(gle.credit, 0)                             AS money_out
		FROM   `tabGL Entry` gle
		LEFT JOIN `tabLedger Entry` le
		       ON le.name          = gle.voucher_no
		      AND gle.voucher_type = 'Ledger Entry'
		WHERE  gle.account      = %(account)s
		  AND  gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY gle.posting_date, gle.creation
		""",
		{"account": filters.account, "from_date": filters.from_date, "to_date": filters.to_date},
		as_dict=True,
	)

	result = []
	if opening_balance:
		result.append(frappe._dict({
			"posting_date": filters.from_date,
			"voucher_no":   "",
			"txn_type":     "",
			"description":  _("Opening Balance"),
			"party":        "",
			"money_in":     opening_balance if opening_balance > 0 else 0.0,
			"money_out":    -opening_balance if opening_balance < 0 else 0.0,
			"balance":      opening_balance,
			"is_opening":   1,
		}))

	running    = opening_balance
	total_in   = 0.0
	total_out  = 0.0
	for row in rows:
		mi = flt(row.money_in)
		mo = flt(row.money_out)
		running   += mi - mo
		total_in  += mi
		total_out += mo
		row.balance = running
		result.append(row)

	closing = running

	def _footer(label, money_in, money_out, row_type):
		return frappe._dict({
			"posting_date": None, "voucher_no": None,
			"txn_type": None, "party": None,
			"description": label,
			"money_in":    flt(money_in),
			"money_out":   flt(money_out),
			"balance":     None,
			"is_footer":   row_type,
		})

	result.append(_footer(
		_("Opening Balance"),
		opening_balance if opening_balance > 0 else 0.0,
		-opening_balance if opening_balance < 0 else 0.0,
		"opening",
	))
	result.append(_footer(_("Period Total"), total_in, total_out, "period_total"))
	result.append(_footer(
		_("Closing Balance"),
		closing if closing > 0 else 0.0,
		-closing if closing < 0 else 0.0,
		"closing",
	))

	return result


# ── summary cards ──────────────────────────────────────────────────────────────

def _build_summary(rows, opening_balance):
	period_rows = [r for r in rows if not r.get("is_opening") and not r.get("is_footer")]
	total_in    = sum(flt(r.money_in)  for r in period_rows)
	total_out   = sum(flt(r.money_out) for r in period_rows)
	data_rows   = [r for r in rows if r.get("balance") is not None]
	closing     = data_rows[-1].balance if data_rows else opening_balance

	return [
		{"label": _("Opening Balance"), "value": opening_balance, "datatype": "Currency", "indicator": "blue"},
		{"label": _("Total Money In"),  "value": total_in,        "datatype": "Currency", "indicator": "green"},
		{"label": _("Total Money Out"), "value": total_out,       "datatype": "Currency", "indicator": "red"},
		{"label": _("Closing Balance"), "value": closing,         "datatype": "Currency",
		 "indicator": "green" if closing >= 0 else "red"},
	]
