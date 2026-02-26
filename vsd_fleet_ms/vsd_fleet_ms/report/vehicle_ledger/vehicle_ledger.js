// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.query_reports["Vehicle Ledger"] = {
	filters: [
		{
			fieldname: "truck",
			label: __("Truck / Vehicle"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "trip",
			label: __("Trip"),
			fieldtype: "Link",
			options: "Trips",
			get_query: function () {
				const truck = frappe.query_report.get_filter_value("truck");
				return truck ? { filters: { truck_number: truck } } : {};
			},
		},
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
	],

	formatter: function (value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);

		const fn = column.fieldname;
		value = default_formatter(value, row, column, data);

		if (data.is_total) {
			if (fn === "description") return `<b>${value}</b>`;
			if (fn === "income")  return `<b style="color:var(--green-600)">${value}</b>`;
			if (fn === "expense") return `<b style="color:var(--red-500)">${value}</b>`;
			if (fn === "net") {
				const raw = parseFloat(data.net) || 0;
				const color = raw >= 0 ? "var(--green-600)" : "var(--red-500)";
				return `<b style="color:${color}">${value}</b>`;
			}
			return "";
		}

		if (fn === "income" && (parseFloat(data.income) || 0) > 0) {
			value = `<span style="color:var(--green-600)">${value}</span>`;
		}
		if (fn === "expense" && (parseFloat(data.expense) || 0) > 0) {
			value = `<span style="color:var(--red-500)">${value}</span>`;
		}
		if (fn === "net") {
			const raw = parseFloat(data.net) || 0;
			if (raw < 0) return `<span style="color:var(--red-500)">${value}</span>`;
			if (raw > 0) return `<span style="color:var(--green-600)">${value}</span>`;
		}
		if (fn === "trip" && value) {
			value = `<b>${value}</b>`;
		}

		return value;
	},
};
