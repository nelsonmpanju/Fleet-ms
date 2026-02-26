// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.query_reports["Vehicle Profitability"] = {
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
			fieldname: "truck",
			label: __("Truck"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "transporter_type",
			label: __("Transporter Type"),
			fieldtype: "Select",
			options: "\nIn House\nSub-Contractor",
		},
		{
			fieldname: "trip_status",
			label: __("Trip Status"),
			fieldtype: "Select",
			options: "\nPending\nIn Transit\nCompleted\nBreakdown",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "gross_profit" && data) {
			const v = flt(data.gross_profit);
			if (v < 0) value = `<span style="color:red">${value}</span>`;
			else if (v > 0) value = `<span style="color:green">${value}</span>`;
		}
		if (column.fieldname === "margin_pct" && data) {
			const v = flt(data.margin_pct);
			if (v < 0) value = `<span style="color:red">${value}</span>`;
			else if (v >= 20) value = `<span style="color:green">${value}</span>`;
		}
		return value;
	},
};
