import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	report_summary = get_summary(data)
	return columns, data, None, None, report_summary


def get_columns():
	return [
		{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "posting_time", "label": _("Posting Time"), "fieldtype": "Time", "width": 90},
		{"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 130},
		{"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"fieldname": "transaction_type", "label": _("Transaction"), "fieldtype": "Data", "width": 140},
		{"fieldname": "voucher_type", "label": _("Voucher Type"), "fieldtype": "Data", "width": 120},
		{"fieldname": "voucher_no", "label": _("Voucher No"), "fieldtype": "Data", "width": 130},
		{"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier", "width": 120},
		{"fieldname": "reference_trip", "label": _("Reference Trip"), "fieldtype": "Link", "options": "Trips", "width": 120},
		{"fieldname": "actual_qty", "label": _("Qty Change"), "fieldtype": "Float", "width": 110},
		{"fieldname": "qty_after_transaction", "label": _("Balance Qty"), "fieldtype": "Float", "width": 110},
		{"fieldname": "incoming_rate", "label": _("Incoming Rate"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "valuation_rate", "label": _("Valuation Rate"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "stock_value_difference", "label": _("Value Change"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "stock_value", "label": _("Balance Value"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "width": 90},
		{"fieldname": "is_cancelled_entry", "label": _("Cancelled"), "fieldtype": "Check", "width": 80},
	]


def get_child_warehouses(filters):
	warehouse = filters.get("warehouse")
	if not warehouse:
		return []

	if not filters.get("include_child_warehouses"):
		return [warehouse]

	lft_rgt = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"], as_dict=True)
	if not lft_rgt or not lft_rgt.lft or not lft_rgt.rgt:
		return [warehouse]

	return frappe.get_all(
		"Warehouse",
		filters={"lft": [">=", lft_rgt.lft], "rgt": ["<=", lft_rgt.rgt]},
		pluck="name",
	)


def get_data(filters):
	conditions = ["sle.posting_date between %(from_date)s and %(to_date)s"]
	values = {
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
	}

	if not filters.get("show_cancelled_entries"):
		conditions.append("ifnull(sle.is_cancelled_entry, 0) = 0")

	if filters.get("item_code"):
		conditions.append("sle.item_code = %(item_code)s")
		values["item_code"] = filters.get("item_code")

	if filters.get("transaction_type"):
		conditions.append("sle.transaction_type = %(transaction_type)s")
		values["transaction_type"] = filters.get("transaction_type")

	if filters.get("voucher_type"):
		conditions.append("sle.voucher_type = %(voucher_type)s")
		values["voucher_type"] = filters.get("voucher_type")

	if filters.get("voucher_no"):
		conditions.append("sle.voucher_no = %(voucher_no)s")
		values["voucher_no"] = filters.get("voucher_no")

	if filters.get("supplier"):
		conditions.append("sle.supplier = %(supplier)s")
		values["supplier"] = filters.get("supplier")

	if filters.get("reference_trip"):
		conditions.append("sle.reference_trip = %(reference_trip)s")
		values["reference_trip"] = filters.get("reference_trip")

	warehouses = get_child_warehouses(filters)
	if warehouses:
		conditions.append("sle.warehouse in %(warehouses)s")
		values["warehouses"] = tuple(warehouses)

	where_clause = " and ".join(conditions)

	return frappe.db.sql(
		f"""
		select
			sle.posting_date,
			sle.posting_time,
			sle.item_code,
			sle.warehouse,
			sle.transaction_type,
			sle.voucher_type,
			sle.voucher_no,
			sle.supplier,
			sle.reference_trip,
			sle.actual_qty,
			sle.qty_after_transaction,
			sle.incoming_rate,
			sle.valuation_rate,
			sle.stock_value_difference,
			sle.stock_value,
			sle.currency,
			sle.is_cancelled_entry
		from `tabStock Ledger Entry` sle
		where {where_clause}
		order by sle.posting_date, sle.posting_time, sle.creation
		""",
		values,
		as_dict=True,
	)


def get_summary(data):
	total_in_qty = 0
	total_out_qty = 0
	total_in_value = 0
	total_out_value = 0

	for d in data:
		qty = flt(d.actual_qty)
		value = flt(d.stock_value_difference)
		if qty >= 0:
			total_in_qty += qty
			total_in_value += max(value, 0)
		else:
			total_out_qty += abs(qty)
			total_out_value += abs(min(value, 0))

	return [
		{"value": total_in_qty, "label": _("Total In Qty"), "datatype": "Float"},
		{"value": total_out_qty, "label": _("Total Out Qty"), "datatype": "Float"},
		{"value": total_in_value, "label": _("Total In Value"), "datatype": "Currency"},
		{"value": total_out_value, "label": _("Total Out Value"), "datatype": "Currency"},
	]
