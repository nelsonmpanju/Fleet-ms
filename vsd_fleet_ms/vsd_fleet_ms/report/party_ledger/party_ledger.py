# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Party Ledger
============
Shows all transactions for a specific party (Customer / Supplier / Driver / Agent)
on their Receivable or Payable account, with a running balance.

Customer  → Receivable account (Debit = invoice raised; Credit = payment received)
Supplier  → Payable account    (Credit = invoice raised; Debit = payment made)
Driver    → Payable account    (Credit = expense approved; Debit = payment made)
"""

import frappe
from frappe import _
from frappe.utils import flt

# Account types to show for each party type
_PARTY_ACCOUNT_TYPES = {
	"Customer": ("Receivable",),
	"Supplier": ("Payable",),
	"Driver":   ("Payable",),
	"Agent":    ("Payable", "Receivable"),
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate(filters)

	account_types = _PARTY_ACCOUNT_TYPES.get(filters.party_type, ("Receivable", "Payable"))
	opening  = _get_opening_balance(filters, account_types)
	rows     = _get_period_entries(filters, account_types, opening)
	summary  = _build_summary(rows, opening, filters)

	return _columns(), rows, None, None, summary


# ── columns ────────────────────────────────────────────────────────────────────

def _columns():
	return [
		{"fieldname": "posting_date", "label": _("Date"),        "fieldtype": "Date",     "width": 100},
		{"fieldname": "voucher_no",   "label": _("Reference"),    "fieldtype": "Link",     "options": "Ledger Entry", "width": 130},
		{"fieldname": "txn_type",     "label": _("Type"),         "fieldtype": "Data",     "width": 110},
		{"fieldname": "description",  "label": _("Description"),  "fieldtype": "Data",     "width": 260},
		{"fieldname": "account",      "label": _("Account"),      "fieldtype": "Data",     "width": 180},
		{"fieldname": "debit",        "label": _("Debit"),        "fieldtype": "Currency", "width": 130},
		{"fieldname": "credit",       "label": _("Credit"),       "fieldtype": "Currency", "width": 130},
		{"fieldname": "balance",      "label": _("Balance"),      "fieldtype": "Currency", "width": 140},
	]


# ── validation ─────────────────────────────────────────────────────────────────

def _validate(filters):
	if not filters.get("party_type"):
		frappe.throw(_("Please select a Party Type."))
	if not filters.get("party"):
		frappe.throw(_("Please select a Party."))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date."))


# ── helpers ────────────────────────────────────────────────────────────────────

def _account_type_placeholders(account_types):
	return ", ".join(["%s"] * len(account_types))


def _get_opening_balance(filters, account_types):
	ph = _account_type_placeholders(account_types)
	result = frappe.db.sql(
		f"""
		SELECT IFNULL(SUM(gle.debit - gle.credit), 0) AS balance
		FROM   `tabGL Entry` gle
		JOIN   `tabAccount` acc ON acc.name = gle.account
		WHERE  gle.party_type   = %s
		  AND  gle.party        = %s
		  AND  acc.account_type IN ({ph})
		  AND  gle.posting_date < %s
		""",
		(filters.party_type, filters.party, *account_types, filters.from_date),
		as_dict=True,
	)
	return flt(result[0].balance) if result else 0.0


def _get_period_entries(filters, account_types, opening_balance):
	ph = _account_type_placeholders(account_types)
	rows = frappe.db.sql(
		f"""
		SELECT
			gle.posting_date,
			gle.voucher_no,
			COALESCE(le.entry_type, gle.voucher_type)   AS txn_type,
			COALESCE(le.remarks, '')                     AS description,
			gle.account,
			IFNULL(gle.debit,  0)                        AS debit,
			IFNULL(gle.credit, 0)                        AS credit
		FROM   `tabGL Entry` gle
		LEFT JOIN `tabLedger Entry` le
		       ON le.name          = gle.voucher_no
		      AND gle.voucher_type = 'Ledger Entry'
		JOIN   `tabAccount` acc ON acc.name = gle.account
		WHERE  gle.party_type   = %s
		  AND  gle.party        = %s
		  AND  acc.account_type IN ({ph})
		  AND  gle.posting_date BETWEEN %s AND %s
		ORDER BY gle.posting_date, gle.creation
		""",
		(filters.party_type, filters.party, *account_types, filters.from_date, filters.to_date),
		as_dict=True,
	)

	result = []
	if opening_balance:
		result.append(frappe._dict({
			"posting_date": filters.from_date,
			"voucher_no":   "",
			"txn_type":     "",
			"description":  _("Opening Balance"),
			"account":      "",
			"debit":        opening_balance if opening_balance > 0 else 0.0,
			"credit":       -opening_balance if opening_balance < 0 else 0.0,
			"balance":      opening_balance,
			"is_opening":   1,
		}))

	running      = opening_balance
	total_debit  = 0.0
	total_credit = 0.0
	for row in rows:
		d = flt(row.debit)
		c = flt(row.credit)
		running      += d - c
		total_debit  += d
		total_credit += c
		row.balance   = running
		result.append(row)

	closing = running

	def _footer(label, debit, credit, row_type):
		return frappe._dict({
			"posting_date": None, "voucher_no": None,
			"txn_type": None, "account": None,
			"description": label,
			"debit":   flt(debit),
			"credit":  flt(credit),
			"balance": None,
			"is_footer": row_type,
		})

	result.append(_footer(
		_("Opening Balance"),
		opening_balance if opening_balance > 0 else 0.0,
		-opening_balance if opening_balance < 0 else 0.0,
		"opening",
	))
	result.append(_footer(_("Period Total"), total_debit, total_credit, "period_total"))
	result.append(_footer(
		_("Closing Balance"),
		closing if closing > 0 else 0.0,
		-closing if closing < 0 else 0.0,
		"closing",
	))

	return result


# ── summary cards ──────────────────────────────────────────────────────────────

def _build_summary(rows, opening_balance, filters):
	period_rows  = [r for r in rows if not r.get("is_opening") and not r.get("is_footer")]
	total_debit  = sum(flt(r.debit)  for r in period_rows)
	total_credit = sum(flt(r.credit) for r in period_rows)
	data_rows    = [r for r in rows if r.get("balance") is not None]
	closing      = data_rows[-1].balance if data_rows else opening_balance

	# For Customers: positive balance = they owe us (good)
	# For Suppliers/Drivers: negative balance = we owe them (normal)
	is_customer = filters.party_type == "Customer"
	closing_indicator = (
		("green" if closing >= 0 else "red") if is_customer
		else ("green" if closing <= 0 else "orange")
	)

	return [
		{"label": _("Opening Balance"),  "value": opening_balance, "datatype": "Currency", "indicator": "blue"},
		{"label": _("Total Debits"),     "value": total_debit,     "datatype": "Currency", "indicator": "blue"},
		{"label": _("Total Credits"),    "value": total_credit,    "datatype": "Currency", "indicator": "orange"},
		{"label": _("Closing Balance"),  "value": closing,         "datatype": "Currency", "indicator": closing_indicator},
	]
