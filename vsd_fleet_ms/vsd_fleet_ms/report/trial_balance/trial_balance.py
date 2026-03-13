# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Trial Balance Report
====================
Shows all accounts with:
  - Opening Balance (debit/credit before from_date)
  - Period Activity  (debit/credit within date range)
  - Closing Balance  (debit/credit at end of period)

Account hierarchy is preserved — group accounts are shown with totals.
"""

import frappe
from frappe import _
from frappe.utils import flt
from vsd_fleet_ms.utils.accounting import get_company_currency


def execute(filters=None):
    filters = frappe._dict(filters or {})
    _validate(filters)

    company_currency = get_company_currency()
    accounts = _get_account_tree()
    gl_data = _get_gl_data(filters)
    rows, summary = _build_rows(accounts, gl_data, filters, company_currency)
    return _columns(company_currency), rows, None, None, summary


# ── columns ────────────────────────────────────────────────────────────────────

def _columns(company_currency):
    return [
        {
            "fieldname": "account",
            "label": _("Account"),
            "fieldtype": "Link",
            "options": "Account",
            "width": 280,
        },
        {
            "fieldname": "account_type",
            "label": _("Type"),
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "fieldname": "opening_debit",
            "label": _("Opening Dr"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "opening_credit",
            "label": _("Opening Cr"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "debit",
            "label": _("Period Dr"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "credit",
            "label": _("Period Cr"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "closing_debit",
            "label": _("Closing Dr"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "closing_credit",
            "label": _("Closing Cr"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
    ]


# ── validation ─────────────────────────────────────────────────────────────────

def _validate(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))
    if filters.from_date > filters.to_date:
        frappe.throw(_("From Date cannot be after To Date."))


# ── account tree ───────────────────────────────────────────────────────────────

def _get_account_tree():
    """Return all accounts ordered by lft (nested set order) for tree display."""
    conditions = ""
    params = {}
    # Optional account type filter
    # (applied in _build_rows by skipping unwanted accounts)
    rows = frappe.db.sql(
        """
        SELECT
            name       AS account,
            account_name,
            account_type,
            is_group,
            parent_account,
            lft,
            rgt
        FROM `tabAccount`
        ORDER BY lft
        """,
        as_dict=True,
    )
    return rows


# ── GL aggregates ──────────────────────────────────────────────────────────────

def _get_gl_data(filters):
    """
    Return two dicts keyed by account name:
      opening[account] = net balance before from_date   (debit - credit)
      period[account]  = {debit, credit} within range
    """
    # Opening balance: all GL entries before from_date
    open_rows = frappe.db.sql(
        """
        SELECT account,
               SUM(debit  - credit) AS net
        FROM   `tabGL Entry`
        WHERE  posting_date < %(from_date)s
        GROUP  BY account
        """,
        {"from_date": filters.from_date},
        as_dict=True,
    )

    # Period activity: GL entries within the date range
    period_rows = frappe.db.sql(
        """
        SELECT account,
               SUM(debit)  AS debit,
               SUM(credit) AS credit
        FROM   `tabGL Entry`
        WHERE  posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP  BY account
        """,
        {"from_date": filters.from_date, "to_date": filters.to_date},
        as_dict=True,
    )

    opening = {r.account: flt(r.net) for r in open_rows}
    period  = {r.account: {"debit": flt(r.debit), "credit": flt(r.credit)} for r in period_rows}
    return opening, period


# ── row builder ────────────────────────────────────────────────────────────────

def _build_rows(accounts, gl_data, filters, company_currency):
    opening_map, period_map = gl_data
    account_type_filter = filters.get("account_type")
    show_zero = filters.get("show_zero_balances")

    # Build a dict for quick lookup and to accumulate totals for groups
    acct_dict = {a.account: a for a in accounts}

    # Per-account aggregated opening & period (leaf only first, then roll up)
    opening_agg = {}  # net debit-credit opening
    period_debit = {}
    period_credit = {}

    for acct in accounts:
        nm = acct.account
        opening_agg[nm] = opening_map.get(nm, 0.0)
        p = period_map.get(nm, {})
        period_debit[nm]  = p.get("debit",  0.0)
        period_credit[nm] = p.get("credit", 0.0)

    # Roll up from leaves → groups using nested-set (lft/rgt)
    # Process in reverse lft order so children are done before parents
    sorted_accounts = sorted(accounts, key=lambda a: a.lft, reverse=True)
    for acct in sorted_accounts:
        if not acct.is_group:
            continue
        # Accumulate all descendants
        for child in accounts:
            if child.lft > acct.lft and child.rgt < acct.rgt and not child.is_group:
                opening_agg[acct.account] += opening_agg.get(child.account, 0.0)
                period_debit[acct.account]  += period_debit.get(child.account, 0.0)
                period_credit[acct.account] += period_credit.get(child.account, 0.0)

    rows = []
    total_od = total_oc = total_pd = total_pc = total_cd = total_cc = 0.0

    for acct in accounts:
        nm = acct.account
        at = acct.account_type or ""

        # Account type filter
        if account_type_filter and at != account_type_filter:
            continue

        ob = opening_agg.get(nm, 0.0)
        pd = period_debit.get(nm, 0.0)
        pc = period_credit.get(nm, 0.0)
        cb = ob + pd - pc

        # Opening split
        od = ob if ob > 0 else 0.0
        oc = -ob if ob < 0 else 0.0
        # Closing split
        cd = cb if cb > 0 else 0.0
        cc = -cb if cb < 0 else 0.0

        # Skip zero-balance accounts unless show_zero is on
        if not show_zero and od == 0 and oc == 0 and pd == 0 and pc == 0 and cd == 0 and cc == 0:
            continue

        indent = _get_indent(acct, acct_dict)

        rows.append(frappe._dict({
            "account":        nm,
            "account_type":   at,
            "opening_debit":  od,
            "opening_credit": oc,
            "debit":          pd,
            "credit":         pc,
            "closing_debit":  cd,
            "closing_credit": cc,
            "indent":         indent,
            "is_group":       acct.is_group,
            "currency":       company_currency,
        }))

        if not acct.is_group:
            total_od += od; total_oc += oc
            total_pd += pd; total_pc += pc
            total_cd += cd; total_cc += cc

    summary = [
        {"label": _("Total Opening Dr"), "value": total_od, "datatype": "Currency", "indicator": "blue", "currency": company_currency},
        {"label": _("Total Opening Cr"), "value": total_oc, "datatype": "Currency", "indicator": "blue", "currency": company_currency},
        {"label": _("Period Debits"),    "value": total_pd, "datatype": "Currency", "indicator": "orange", "currency": company_currency},
        {"label": _("Period Credits"),   "value": total_pc, "datatype": "Currency", "indicator": "red", "currency": company_currency},
        {"label": _("Total Closing Dr"), "value": total_cd, "datatype": "Currency", "indicator": "green", "currency": company_currency},
        {"label": _("Total Closing Cr"), "value": total_cc, "datatype": "Currency", "indicator": "green", "currency": company_currency},
    ]
    return rows, summary


def _get_indent(acct, acct_dict):
    """Count ancestor levels for visual indentation."""
    level = 0
    parent = acct.parent_account
    while parent and parent in acct_dict:
        level += 1
        parent = acct_dict[parent].parent_account
    return level
