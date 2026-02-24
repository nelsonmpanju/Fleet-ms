import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	metrics = get_metrics(filters)
	columns = get_columns()
	data = [metrics]
	chart = get_chart(metrics)
	summary = get_summary(metrics)
	return columns, data, None, chart, summary


def validate_filters(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
	return [
		{"fieldname": "from_date", "label": _("From Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "to_date", "label": _("To Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "width": 90},
		{"fieldname": "sales_total", "label": _("Sales"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "purchase_total", "label": _("Purchases"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "ledger_income", "label": _("Ledger Income"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "ledger_expense", "label": _("Ledger Expense"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "trip_expense_total", "label": _("Trip Expense (Ledger)"), "fieldtype": "Currency", "width": 160},
		{"fieldname": "stock_receipt_value", "label": _("Stock Receipt Value"), "fieldtype": "Currency", "width": 150},
		{"fieldname": "stock_issue_value", "label": _("Stock Issue Value"), "fieldtype": "Currency", "width": 140},
		{"fieldname": "gross_profit", "label": _("Gross Profit"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "net_profit", "label": _("Net Profit"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "payments_received", "label": _("Payments Received"), "fieldtype": "Currency", "width": 140},
		{"fieldname": "payments_made", "label": _("Payments Made"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "net_cash_flow", "label": _("Net Cash Flow"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "receivables_outstanding", "label": _("Receivables Outstanding"), "fieldtype": "Currency", "width": 160},
		{"fieldname": "payables_outstanding", "label": _("Payables Outstanding"), "fieldtype": "Currency", "width": 150},
		{"fieldname": "net_position", "label": _("Net Position"), "fieldtype": "Currency", "width": 120},
	]


def get_metrics(filters):
	sales = get_sales_totals(filters)
	purchases = get_purchase_totals(filters)
	ledger = get_ledger_totals(filters)
	stock = get_stock_totals(filters)
	payments_received = get_payment_total(filters, payment_type="Receive")
	payments_made = get_payment_total(filters, payment_type="Pay")

	sales_total = flt(sales.sales_total)
	purchase_total = flt(purchases.purchase_total)
	ledger_income = flt(ledger.income_total)
	ledger_expense = flt(ledger.expense_total)
	trip_expense_total = flt(ledger.trip_expense_total)
	stock_receipt_value = flt(stock.stock_receipt_value)
	stock_issue_value = flt(stock.stock_issue_value)
	receivables_outstanding = flt(sales.receivables_outstanding)
	payables_outstanding = flt(purchases.payables_outstanding)
	gross_profit = sales_total - purchase_total
	net_profit = gross_profit + ledger_income - ledger_expense - stock_issue_value
	net_cash_flow = payments_received - payments_made
	net_position = receivables_outstanding - payables_outstanding

	currency = (
		frappe.db.get_value("Currency", {"enabled": 1}, "name")
		or sales.currency
		or purchases.currency
		or ledger.currency
		or "USD"
	)

	return {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
		"currency": currency,
		"sales_total": sales_total,
		"purchase_total": purchase_total,
		"ledger_income": ledger_income,
		"ledger_expense": ledger_expense,
		"trip_expense_total": trip_expense_total,
		"stock_receipt_value": stock_receipt_value,
		"stock_issue_value": stock_issue_value,
		"gross_profit": gross_profit,
		"net_profit": net_profit,
		"payments_received": payments_received,
		"payments_made": payments_made,
		"net_cash_flow": net_cash_flow,
		"receivables_outstanding": receivables_outstanding,
		"payables_outstanding": payables_outstanding,
		"net_position": net_position,
	}


def get_sales_totals(filters):
	conditions = ["docstatus = 1", "posting_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.get("customer"):
		conditions.append("customer = %(customer)s")
		values["customer"] = filters.customer

	if filters.get("trip"):
		conditions.append("reference_trip = %(trip)s")
		values["trip"] = filters.trip

	where_clause = " and ".join(conditions)
	return frappe.db.sql(
		f"""
		select
			ifnull(sum(grand_total), 0) as sales_total,
			ifnull(sum(outstanding_amount), 0) as receivables_outstanding,
			max(currency) as currency
		from `tabSales Invoice`
		where {where_clause}
		""",
		values,
		as_dict=True,
	)[0]


def get_purchase_totals(filters):
	conditions = ["docstatus = 1", "posting_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.get("supplier"):
		conditions.append("supplier = %(supplier)s")
		values["supplier"] = filters.supplier

	if filters.get("trip"):
		conditions.append("reference_trip = %(trip)s")
		values["trip"] = filters.trip

	where_clause = " and ".join(conditions)
	return frappe.db.sql(
		f"""
		select
			ifnull(sum(grand_total), 0) as purchase_total,
			ifnull(sum(outstanding_amount), 0) as payables_outstanding,
			max(currency) as currency
		from `tabPurchase Invoice`
		where {where_clause}
		""",
		values,
		as_dict=True,
	)[0]


def get_payment_total(filters, payment_type: str) -> float:
	conditions = [
		"docstatus = 1",
		"payment_type = %(payment_type)s",
		"posting_date between %(from_date)s and %(to_date)s",
	]
	values = {
		"payment_type": payment_type,
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.get("mode_of_payment"):
		conditions.append("mode_of_payment = %(mode_of_payment)s")
		values["mode_of_payment"] = filters.mode_of_payment

	if payment_type == "Receive":
		conditions.append("party_type = 'Customer'")
		if filters.get("customer"):
			conditions.append("party = %(customer)s")
			values["customer"] = filters.customer
		if filters.get("trip"):
			conditions.append(
				"""
				exists (
					select 1 from `tabSales Invoice` si
					where si.name = `tabPayment Entry`.reference_name
						and `tabPayment Entry`.reference_doctype = 'Sales Invoice'
						and si.reference_trip = %(trip)s
				)
				"""
			)
			values["trip"] = filters.trip
	elif payment_type == "Pay":
		conditions.append("party_type = 'Supplier'")
		if filters.get("supplier"):
			conditions.append("party = %(supplier)s")
			values["supplier"] = filters.supplier
		if filters.get("trip"):
			conditions.append(
				"""
				exists (
					select 1 from `tabPurchase Invoice` pi
					where pi.name = `tabPayment Entry`.reference_name
						and `tabPayment Entry`.reference_doctype = 'Purchase Invoice'
						and pi.reference_trip = %(trip)s
				)
				"""
			)
			values["trip"] = filters.trip

	where_clause = " and ".join(conditions)
	row = frappe.db.sql(
		f"""
		select ifnull(sum(paid_amount), 0) as amount
		from `tabPayment Entry`
		where {where_clause}
		""",
		values,
		as_dict=True,
	)[0]
	return flt(row.amount)


def get_ledger_totals(filters):
	conditions = ["docstatus = 1", "posting_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.get("trip"):
		conditions.append("reference_trip = %(trip)s")
		values["trip"] = filters.trip

	if filters.get("customer"):
		conditions.append(
			"(party_type != 'Customer' or (party_type = 'Customer' and party = %(customer)s))"
		)
		values["customer"] = filters.customer

	if filters.get("supplier"):
		conditions.append(
			"(party_type != 'Supplier' or (party_type = 'Supplier' and party = %(supplier)s))"
		)
		values["supplier"] = filters.supplier

	where_clause = " and ".join(conditions)
	return frappe.db.sql(
		f"""
		select
			ifnull(sum(case when entry_type = 'Income' and ifnull(source_type, '') != 'Sales Invoice' then amount else 0 end), 0) as income_total,
			ifnull(sum(case when entry_type = 'Expense' then amount else 0 end), 0) as expense_total,
			ifnull(sum(case when source_type = 'Trip Expense' and entry_type = 'Expense' then amount else 0 end), 0) as trip_expense_total,
			max(currency) as currency
		from `tabLedger Entry`
		where {where_clause}
		""",
		values,
		as_dict=True,
	)[0]


def get_stock_totals(filters):
	conditions = ["is_cancelled_entry = 0", "posting_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.get("trip"):
		conditions.append("reference_trip = %(trip)s")
		values["trip"] = filters.trip

	where_clause = " and ".join(conditions)
	return frappe.db.sql(
		f"""
		select
			ifnull(sum(case when stock_value_difference > 0 then stock_value_difference else 0 end), 0) as stock_receipt_value,
			ifnull(sum(case when stock_value_difference < 0 then -stock_value_difference else 0 end), 0) as stock_issue_value
		from `tabStock Ledger Entry`
		where {where_clause}
		""",
		values,
		as_dict=True,
	)[0]


def get_chart(metrics):
	return {
		"data": {
			"labels": ["Sales", "Purchases", "Ledger Expense", "Stock Issue", "Net Profit"],
			"datasets": [
				{
					"name": "Amount",
					"values": [
						flt(metrics.get("sales_total")),
						flt(metrics.get("purchase_total")),
						flt(metrics.get("ledger_expense")),
						flt(metrics.get("stock_issue_value")),
						flt(metrics.get("net_profit")),
					],
				}
			],
		},
		"type": "bar",
		"height": 240,
	}


def get_summary(metrics):
	return [
		{"value": metrics.get("sales_total"), "label": _("Sales"), "datatype": "Currency"},
		{"value": metrics.get("purchase_total"), "label": _("Purchases"), "datatype": "Currency"},
		{"value": metrics.get("ledger_income"), "label": _("Ledger Income"), "datatype": "Currency"},
		{"value": metrics.get("ledger_expense"), "label": _("Ledger Expense"), "datatype": "Currency"},
		{"value": metrics.get("stock_issue_value"), "label": _("Stock Issue Value"), "datatype": "Currency"},
		{"value": metrics.get("gross_profit"), "label": _("Gross Profit"), "datatype": "Currency"},
		{"value": metrics.get("net_profit"), "label": _("Net Profit"), "datatype": "Currency"},
		{"value": metrics.get("net_cash_flow"), "label": _("Net Cash Flow"), "datatype": "Currency"},
	]
