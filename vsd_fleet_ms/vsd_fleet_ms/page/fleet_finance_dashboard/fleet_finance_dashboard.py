# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, nowdate


@frappe.whitelist()
def get_finance_kpis(from_date=None, to_date=None):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()
    params    = {"from_date": from_date, "to_date": to_date}

    # Sales
    si = frappe.db.sql("""
        SELECT
            COUNT(*)                        AS invoice_count,
            IFNULL(SUM(grand_total), 0)     AS revenue,
            IFNULL(SUM(paid_amount), 0)     AS collected,
            IFNULL(SUM(outstanding_amount), 0) AS receivables
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
    """, params, as_dict=True)[0]

    # Purchases
    pi = frappe.db.sql("""
        SELECT
            COUNT(*)                        AS invoice_count,
            IFNULL(SUM(grand_total), 0)     AS purchases,
            IFNULL(SUM(paid_amount), 0)     AS paid,
            IFNULL(SUM(outstanding_amount), 0) AS payables
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
    """, params, as_dict=True)[0]

    # Ledger entries
    le = frappe.db.sql("""
        SELECT
            IFNULL(SUM(CASE WHEN entry_type='Income'  THEN amount ELSE 0 END), 0) AS income,
            IFNULL(SUM(CASE WHEN entry_type='Expense' THEN amount ELSE 0 END), 0) AS expense
        FROM `tabLedger Entry`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
    """, params, as_dict=True)[0]

    # Payments
    payments = frappe.db.sql("""
        SELECT
            IFNULL(SUM(CASE WHEN payment_type='Receive' THEN paid_amount ELSE 0 END), 0) AS received,
            IFNULL(SUM(CASE WHEN payment_type='Pay'     THEN paid_amount ELSE 0 END), 0) AS paid
        FROM `tabPayment Entry`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
    """, params, as_dict=True)[0]

    # Trip expenses (approved fund rows)
    trip_exp = frappe.db.sql("""
        SELECT IFNULL(SUM(fd.request_amount), 0) AS trip_expense
        FROM `tabRequested Fund Details` fd
        INNER JOIN `tabTrips` t ON t.name = fd.parent
        WHERE fd.parenttype = 'Trips'
          AND fd.request_status IN ('Approved', 'Accounts Approved')
          AND t.date BETWEEN %(from_date)s AND %(to_date)s
    """, params, as_dict=True)[0]

    # Overdue receivables > 30 days
    overdue_si = frappe.db.sql("""
        SELECT COUNT(*) AS cnt, IFNULL(SUM(outstanding_amount), 0) AS amount
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0
          AND posting_date < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """, as_dict=True)[0]

    # Overdue payables > 30 days
    overdue_pi = frappe.db.sql("""
        SELECT COUNT(*) AS cnt, IFNULL(SUM(outstanding_amount), 0) AS amount
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0
          AND posting_date < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """, as_dict=True)[0]

    # Actual cash / bank balance from GL
    cash_balance_row = frappe.db.sql("""
        SELECT IFNULL(SUM(gle.debit - gle.credit), 0) AS balance
        FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE acc.account_sub_type IN ('Cash', 'Bank') AND acc.is_group = 0
    """, as_dict=True)
    cash_balance = flt(cash_balance_row[0].balance) if cash_balance_row else 0.0

    revenue      = flt(si.revenue)
    purchases    = flt(pi.purchases)
    collected    = flt(si.collected)
    paid_out     = flt(pi.paid)
    gross_profit = revenue - purchases
    net_profit   = gross_profit + flt(le.income) - flt(le.expense)
    profit_margin   = round(net_profit / revenue   * 100, 1) if revenue   > 0 else 0.0
    collection_rate = round(collected  / revenue   * 100, 1) if revenue   > 0 else 0.0
    payment_rate    = round(paid_out   / purchases * 100, 1) if purchases > 0 else 0.0

    return {
        "revenue":           revenue,
        "collected":         collected,
        "receivables":       flt(si.receivables),
        "si_count":          int(si.invoice_count or 0),
        "purchases":         purchases,
        "paid":              paid_out,
        "payables":          flt(pi.payables),
        "pi_count":          int(pi.invoice_count or 0),
        "ledger_income":     flt(le.income),
        "ledger_expense":    flt(le.expense),
        "trip_expense":      flt(trip_exp.trip_expense),
        "gross_profit":      gross_profit,
        "net_profit":        net_profit,
        "profit_margin":     profit_margin,
        "collection_rate":   collection_rate,
        "payment_rate":      payment_rate,
        "payments_in":       flt(payments.received),
        "payments_out":      flt(payments.paid),
        "net_cash":          flt(payments.received) - flt(payments.paid),
        "cash_balance":      cash_balance,
        "overdue_si_count":  int(overdue_si.cnt or 0),
        "overdue_si_amount": flt(overdue_si.amount),
        "overdue_pi_count":  int(overdue_pi.cnt or 0),
        "overdue_pi_amount": flt(overdue_pi.amount),
    }


@frappe.whitelist()
def get_revenue_vs_expense_monthly(from_date=None, to_date=None):
    from_date = from_date or (nowdate()[:4] + "-01-01")
    to_date   = to_date   or nowdate()
    params    = {"from_date": from_date, "to_date": to_date}

    revenue_rows = frappe.db.sql("""
        SELECT DATE_FORMAT(posting_date,'%%Y-%%m') AS period,
               IFNULL(SUM(grand_total), 0) AS amount
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY period ORDER BY period
    """, params, as_dict=True)

    expense_rows = frappe.db.sql("""
        SELECT DATE_FORMAT(posting_date,'%%Y-%%m') AS period,
               IFNULL(SUM(grand_total), 0) AS amount
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY period ORDER BY period
    """, params, as_dict=True)

    return {
        "revenue": revenue_rows,
        "expense": expense_rows,
    }


@frappe.whitelist()
def get_top_customers(from_date=None, to_date=None, limit=10):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    rows = frappe.db.sql("""
        SELECT
            customer,
            COUNT(*) AS invoices,
            IFNULL(SUM(grand_total), 0)        AS revenue,
            IFNULL(SUM(paid_amount), 0)        AS collected,
            IFNULL(SUM(outstanding_amount), 0) AS outstanding
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY customer
        ORDER BY revenue DESC
        LIMIT %(limit)s
    """, {"from_date": from_date, "to_date": to_date, "limit": int(limit)}, as_dict=True)

    return rows


@frappe.whitelist()
def get_top_suppliers(from_date=None, to_date=None, limit=10):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    rows = frappe.db.sql("""
        SELECT
            supplier,
            COUNT(*) AS invoices,
            IFNULL(SUM(grand_total), 0)        AS purchases,
            IFNULL(SUM(paid_amount), 0)        AS paid,
            IFNULL(SUM(outstanding_amount), 0) AS outstanding
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY supplier
        ORDER BY purchases DESC
        LIMIT %(limit)s
    """, {"from_date": from_date, "to_date": to_date, "limit": int(limit)}, as_dict=True)

    return rows


@frappe.whitelist()
def get_unpaid_invoices(doctype="Sales Invoice", limit=20):
    if doctype not in ("Sales Invoice", "Purchase Invoice"):
        frappe.throw("Invalid doctype")

    if doctype == "Sales Invoice":
        rows = frappe.db.sql("""
            SELECT name, posting_date, customer AS party,
                   grand_total, outstanding_amount, payment_status
            FROM `tabSales Invoice`
            WHERE docstatus = 1 AND outstanding_amount > 0
            ORDER BY posting_date ASC
            LIMIT %(limit)s
        """, {"limit": int(limit)}, as_dict=True)
    else:
        rows = frappe.db.sql("""
            SELECT name, posting_date, supplier AS party,
                   grand_total, outstanding_amount, payment_status
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1 AND outstanding_amount > 0
            ORDER BY posting_date ASC
            LIMIT %(limit)s
        """, {"limit": int(limit)}, as_dict=True)

    return rows


@frappe.whitelist()
def get_payment_status_breakdown(from_date=None, to_date=None):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()
    params    = {"from_date": from_date, "to_date": to_date}

    si_rows = frappe.db.sql("""
        SELECT payment_status, COUNT(*) AS cnt, IFNULL(SUM(grand_total), 0) AS amount
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY payment_status
    """, params, as_dict=True)

    pi_rows = frappe.db.sql("""
        SELECT payment_status, COUNT(*) AS cnt, IFNULL(SUM(grand_total), 0) AS amount
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY payment_status
    """, params, as_dict=True)

    return {"sales": si_rows, "purchases": pi_rows}


@frappe.whitelist()
def get_expense_by_type(from_date=None, to_date=None):
    from_date = from_date or nowdate()[:7] + "-01"
    to_date   = to_date   or nowdate()

    rows = frappe.db.sql("""
        SELECT
            fd.expense_type,
            IFNULL(SUM(fd.request_amount), 0) AS amount
        FROM `tabRequested Fund Details` fd
        INNER JOIN `tabTrips` t ON t.name = fd.parent
        WHERE fd.parenttype = 'Trips'
          AND fd.request_status IN ('Approved', 'Accounts Approved')
          AND t.date BETWEEN %(from_date)s AND %(to_date)s
          AND fd.expense_type IS NOT NULL AND fd.expense_type != ''
        GROUP BY fd.expense_type
        ORDER BY amount DESC
        LIMIT 10
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    return rows


@frappe.whitelist()
def get_cash_flow_monthly(from_date=None, to_date=None):
    """Monthly cash in (payments received) vs cash out (payments made)."""
    from_date = from_date or (nowdate()[:4] + "-01-01")
    to_date   = to_date   or nowdate()
    params    = {"from_date": from_date, "to_date": to_date}

    rows = frappe.db.sql("""
        SELECT
            DATE_FORMAT(posting_date, '%%Y-%%m') AS period,
            IFNULL(SUM(CASE WHEN payment_type = 'Receive' THEN paid_amount ELSE 0 END), 0) AS cash_in,
            IFNULL(SUM(CASE WHEN payment_type = 'Pay'     THEN paid_amount ELSE 0 END), 0) AS cash_out
        FROM `tabPayment Entry`
        WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY period
        ORDER BY period
    """, params, as_dict=True)

    return rows


@frappe.whitelist()
def get_ar_aging():
    """Accounts Receivable aging buckets (all outstanding Sales Invoices)."""
    buckets = frappe.db.sql("""
        SELECT
            IFNULL(SUM(CASE WHEN DATEDIFF(CURDATE(), posting_date) BETWEEN 0  AND 30  THEN outstanding_amount ELSE 0 END), 0) AS days_0_30,
            IFNULL(SUM(CASE WHEN DATEDIFF(CURDATE(), posting_date) BETWEEN 31 AND 60  THEN outstanding_amount ELSE 0 END), 0) AS days_31_60,
            IFNULL(SUM(CASE WHEN DATEDIFF(CURDATE(), posting_date) BETWEEN 61 AND 90  THEN outstanding_amount ELSE 0 END), 0) AS days_61_90,
            IFNULL(SUM(CASE WHEN DATEDIFF(CURDATE(), posting_date)  > 90              THEN outstanding_amount ELSE 0 END), 0) AS days_90_plus
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0
    """, as_dict=True)[0]

    return {
        "0-30":   flt(buckets.days_0_30),
        "31-60":  flt(buckets.days_31_60),
        "61-90":  flt(buckets.days_61_90),
        "90+":    flt(buckets.days_90_plus),
    }
