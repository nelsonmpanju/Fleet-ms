frappe.query_reports["Stock Ledger Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.month_start()
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today()
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item"
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse"
		},
		{
			fieldname: "include_child_warehouses",
			label: __("Include Child Warehouses"),
			fieldtype: "Check",
			default: 1
		},
		{
			fieldname: "transaction_type",
			label: __("Transaction Type"),
			fieldtype: "Select",
			options: "\nPurchase Receipt\nMaterial Issue\nMaterial Receipt\nMaterial Transfer (In)\nMaterial Transfer (Out)\nStock Reconciliation"
		},
		{
			fieldname: "voucher_type",
			label: __("Voucher Type"),
			fieldtype: "Data"
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher No"),
			fieldtype: "Data"
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier"
		},
		{
			fieldname: "reference_trip",
			label: __("Reference Trip"),
			fieldtype: "Link",
			options: "Trips"
		},
		{
			fieldname: "show_cancelled_entries",
			label: __("Show Cancelled Entries"),
			fieldtype: "Check",
			default: 0
		}
	]
};
