// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.query_reports["Party Ledger"] = {
	filters: [
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Select",
			options: "Customer\nSupplier\nDriver",
			reqd: 1,
			on_change: function () {
				const party_type = frappe.query_report.get_filter_value("party_type");
				frappe.query_report.set_filter_value("party", "");
				// Update party Link field to point to the selected doctype
				frappe.query_report.filters.forEach(function (f) {
					if (f.df.fieldname === "party") {
						f.df.options = party_type || "Customer";
						f.refresh();
					}
				});
			},
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Link",
			options: "Customer",
			reqd: 1,
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

	_FOOTER_BLANK: ["posting_date", "voucher_no", "txn_type", "account", "balance"],

	_FOOTER_STYLE: {
		opening:      { color: "var(--text-muted)",  bold: false },
		period_total: { color: "var(--blue-500)",    bold: true  },
		closing:      { color: "var(--green-600)",   bold: true  },
	},

	formatter: function (value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);

		const fn = column.fieldname;

		if (data.is_opening) {
			const v = default_formatter(value, row, column, data);
			return fn === "balance"
				? `<span style="color:var(--text-muted);font-style:italic;">${v}</span>`
				: `<span style="color:var(--text-muted);">${v}</span>`;
		}

		if (data.is_footer) {
			const cfg = frappe.query_reports["Party Ledger"]._FOOTER_STYLE[data.is_footer] || {};
			if (frappe.query_reports["Party Ledger"]._FOOTER_BLANK.includes(fn)) return "";
			if (fn === "description") {
				const label = value || "";
				return cfg.bold
					? `<b style="color:${cfg.color};">${label}</b>`
					: `<span style="color:${cfg.color};">${label}</span>`;
			}
			if (fn === "debit" || fn === "credit") {
				const raw = parseFloat(data[fn]) || 0;
				if (raw === 0) return "";
				const v = default_formatter(value, row, column, data);
				return cfg.bold
					? `<b style="color:${cfg.color};">${v}</b>`
					: `<span style="color:${cfg.color};">${v}</span>`;
			}
			return "";
		}

		value = default_formatter(value, row, column, data);

		if (fn === "account" && value) value = `<span style="color:var(--text-muted)">${value}</span>`;

		if (fn === "debit" && (parseFloat(data.debit) || 0) > 0) {
			value = `<span style="color:var(--blue-600)">${value}</span>`;
		}
		if (fn === "credit" && (parseFloat(data.credit) || 0) > 0) {
			value = `<span style="color:var(--green-600)">${value}</span>`;
		}
		if (fn === "balance") {
			const raw = parseFloat(data.balance) || 0;
			if (raw < 0) return `<span style="color:var(--red-500)">${value}</span>`;
			if (raw > 0) return `<span style="color:var(--blue-600)">${value}</span>`;
		}

		return value;
	},
};
