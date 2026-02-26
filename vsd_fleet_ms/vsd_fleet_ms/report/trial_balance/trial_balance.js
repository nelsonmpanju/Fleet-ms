// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.query_reports["Trial Balance"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
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
			fieldname: "account_type",
			label: __("Account Type"),
			fieldtype: "Select",
			options: "\nAsset\nLiability\nIncome\nExpense\nEquity",
		},
		{
			fieldname: "show_zero_balances",
			label: __("Show Zero Balances"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.is_group) {
			value = `<strong>${value}</strong>`;
		}
		return value;
	},

	get_datatable_options(options) {
		return Object.assign(options, {
			treeView: true,
		});
	},
};
