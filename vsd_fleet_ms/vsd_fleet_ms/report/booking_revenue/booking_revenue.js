// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.query_reports["Booking Revenue"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "truck",
			label: __("Truck"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "payment_status",
			label: __("Payment Status"),
			fieldtype: "Select",
			options: "\nUnpaid\nPartly Paid\nPaid",
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: "\nCustomer\nTrip\nMonth",
			default: "Customer",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "payment_rate" && data) {
			const v = flt(data.payment_rate);
			if (v >= 100) value = `<span style="color:green;font-weight:bold">${value}</span>`;
			else if (v >= 50) value = `<span style="color:orange">${value}</span>`;
			else value = `<span style="color:red">${value}</span>`;
		}
		if (column.fieldname === "outstanding" && data) {
			if (flt(data.outstanding) > 0) value = `<span style="color:red">${value}</span>`;
		}
		return value;
	},
};
