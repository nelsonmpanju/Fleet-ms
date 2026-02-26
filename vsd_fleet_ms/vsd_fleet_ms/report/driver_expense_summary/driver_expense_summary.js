// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.query_reports["Driver Expense Summary"] = {
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
			fieldname: "driver",
			label: __("Driver"),
			fieldtype: "Link",
			options: "Driver",
		},
		{
			fieldname: "expense_type",
			label: __("Expense Type"),
			fieldtype: "Data",
		},
		{
			fieldname: "trip",
			label: __("Trip"),
			fieldtype: "Link",
			options: "Trips",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "request_status" && data) {
			if (data.request_status === "Accounts Approved") {
				value = `<span class="indicator-pill green">${value}</span>`;
			} else if (data.request_status === "Approved") {
				value = `<span class="indicator-pill blue">${value}</span>`;
			}
		}
		if (column.fieldname === "payment_ref" && data && data.payment_ref) {
			value = `<a href="/app/payment-entry/${data.payment_ref}">${data.payment_ref}</a>`;
		}
		return value;
	},
};
