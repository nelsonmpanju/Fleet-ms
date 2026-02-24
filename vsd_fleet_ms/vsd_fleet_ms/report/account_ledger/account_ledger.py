# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Account Ledger Report
=====================
Shows every GL posting to a selected account within a date range,
with a running balance and an opening-balance line at the top.

How to read it
--------------
- Debit  → money flowing INTO  the account (increases asset / expense balance)
- Credit → money flowing OUT OF the account (increases liability / income balance)
- Balance is the running algebraic total (Debit − Credit accumulated from day one)
"""

import frappe
from frappe import _
from frappe.utils import flt


# ── public entry point ─────────────────────────────────────────────────────────

def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate(filters)

	account_meta = _get_account_meta(filters.account)
	opening      = _get_opening_balance(filters)
	rows         = _get_period_entries(filters, opening)
	summary      = _build_summary(rows, opening)

	return _columns(), rows, None, None, summary


# ── columns ────────────────────────────────────────────────────────────────────

def _columns():
	return [
		{
			"fieldname": "posting_date",
			"label":     _("Date"),
			"fieldtype": "Date",
			"width":     100,
		},
		{
			"fieldname": "voucher_no",
			"label":     _("Reference"),
			"fieldtype": "Link",
			"options":   "Ledger Entry",
			"width":     130,
		},
		{
			"fieldname": "entry_type",
			"label":     _("Type"),
			"fieldtype": "Data",
			"width":     110,
		},
		{
			"fieldname": "description",
			"label":     _("Description"),
			"fieldtype": "Data",
			"width":     260,
		},
		{
			"fieldname": "party",
			"label":     _("Party"),
			"fieldtype": "Data",
			"width":     130,
		},
		{
			"fieldname": "debit",
			"label":     _("Debit"),
			"fieldtype": "Currency",
			"width":     120,
		},
		{
			"fieldname": "credit",
			"label":     _("Credit"),
			"fieldtype": "Currency",
			"width":     120,
		},
		{
			"fieldname": "balance",
			"label":     _("Balance"),
			"fieldtype": "Currency",
			"width":     130,
		},
	]


# ── validation ─────────────────────────────────────────────────────────────────

def _validate(filters):
	if not filters.get("account"):
		frappe.throw(_("Please select an Account."))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date."))


# ── data helpers ───────────────────────────────────────────────────────────────

def _get_account_meta(account):
	return frappe.db.get_value(
		"Account", account,
		["account_name", "account_number", "account_type", "balance_type"],
		as_dict=True,
	) or frappe._dict()


def _party_where(filters, prefix=""):
	"""
	Return (extra_conditions_list, params_dict) for optional party filtering.
	prefix should be 'gle.' when used inside a JOIN query.
	"""
	conds, params = [], {}
	if filters.get("party_type"):
		conds.append(f"{prefix}party_type = %(party_type)s")
		params["party_type"] = filters.party_type
	if filters.get("party"):
		conds.append(f"{prefix}party = %(party)s")
		params["party"] = filters.party
	return conds, params


def _get_opening_balance(filters):
	"""Sum of all GL postings to this account BEFORE the from_date, party-aware."""
	extra, party_params = _party_where(filters)
	where = "account = %(account)s AND posting_date < %(from_date)s"
	if extra:
		where += " AND " + " AND ".join(extra)

	result = frappe.db.sql(
		f"SELECT IFNULL(SUM(debit - credit), 0) AS balance FROM `tabGL Entry` WHERE {where}",
		{"account": filters.account, "from_date": filters.from_date, **party_params},
		as_dict=True,
	)
	return flt(result[0].balance) if result else 0.0


def _get_period_entries(filters, opening_balance):
	"""
	Fetch GL entries within the date range, join with Ledger Entry for
	human-readable description, then compute the running balance.
	Party filters are applied when party_type / party are set.
	"""
	extra, party_params = _party_where(filters, prefix="gle.")
	party_where = (" AND " + " AND ".join(extra)) if extra else ""

	rows = frappe.db.sql(
		f"""
		SELECT
			gle.posting_date,
			gle.voucher_no,
			COALESCE(le.entry_type, gle.voucher_type) AS entry_type,
			COALESCE(le.remarks,    '')                AS description,
			COALESCE(le.party,      gle.party, '')     AS party,
			IFNULL(gle.debit,  0)                      AS debit,
			IFNULL(gle.credit, 0)                      AS credit
		FROM   `tabGL Entry` gle
		LEFT JOIN `tabLedger Entry` le
		       ON le.name          = gle.voucher_no
		      AND gle.voucher_type = 'Ledger Entry'
		WHERE  gle.account      = %(account)s
		  AND  gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
		{party_where}
		ORDER BY gle.posting_date, gle.creation
		""",
		{
			"account":   filters.account,
			"from_date": filters.from_date,
			"to_date":   filters.to_date,
			**party_params,
		},
		as_dict=True,
	)

	# Prepend opening-balance row (only when non-zero or explicitly useful)
	result = []
	if opening_balance:
		result.append(frappe._dict({
			"posting_date": filters.from_date,
			"voucher_no":   "",
			"entry_type":   "",
			"description":  _("Opening Balance"),
			"party":        "",
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

	# ── Tally-style summary rows at the bottom of the table ────────────────
	def _footer(label, debit, credit, row_type):
		return frappe._dict({
			"posting_date": None, "voucher_no": None,
			"entry_type":   None, "party":      None,
			"description":  label,
			"debit":        flt(debit),
			"credit":       flt(credit),
			"balance":      None,
			"is_footer":    row_type,
		})

	result.append(_footer(
		_("Opening Balance"),
		opening_balance if opening_balance > 0 else 0.0,
		-opening_balance if opening_balance < 0 else 0.0,
		"opening",
	))
	result.append(_footer(_("Current Period Total"), total_debit, total_credit, "period_total"))
	result.append(_footer(
		_("Closing Balance"),
		closing if closing > 0 else 0.0,
		-closing if closing < 0 else 0.0,
		"closing",
	))

	return result


# ── summary cards ──────────────────────────────────────────────────────────────

def _build_summary(rows, opening_balance):
	period_rows  = [r for r in rows if not r.get("is_opening") and not r.get("is_footer")]
	total_debit  = sum(flt(r.debit)  for r in period_rows)
	total_credit = sum(flt(r.credit) for r in period_rows)
	# closing = last row that carries a real running balance (footer rows have balance=None)
	data_rows = [r for r in rows if r.get("balance") is not None]
	closing   = data_rows[-1].balance if data_rows else opening_balance

	return [
		{
			"label":    _("Opening Balance"),
			"value":    opening_balance,
			"datatype": "Currency",
			"indicator": "blue",
		},
		{
			"label":    _("Total Debits"),
			"value":    total_debit,
			"datatype": "Currency",
			"indicator": "orange",
		},
		{
			"label":    _("Total Credits"),
			"value":    total_credit,
			"datatype": "Currency",
			"indicator": "red",
		},
		{
			"label":    _("Closing Balance"),
			"value":    closing,
			"datatype": "Currency",
			"indicator": "green" if closing >= 0 else "red",
		},
	]
