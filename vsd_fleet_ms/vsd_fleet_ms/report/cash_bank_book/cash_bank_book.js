// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.query_reports["Cash Bank Book"] = {
	filters: [
		{
			fieldname: "account",
			label: __("Cash / Bank Account"),
			fieldtype: "Link",
			options: "Account",
			reqd: 1,
			get_query: function () {
				return { filters: { is_group: 0, account_sub_type: ["in", ["Cash", "Bank"]] } };
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

	_FOOTER_BLANK: ["posting_date", "voucher_no", "txn_type", "party", "balance"],

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
			const cfg = frappe.query_reports["Cash Bank Book"]._FOOTER_STYLE[data.is_footer] || {};
			if (frappe.query_reports["Cash Bank Book"]._FOOTER_BLANK.includes(fn)) return "";
			if (fn === "description") {
				const label = value || "";
				return cfg.bold
					? `<b style="color:${cfg.color};">${label}</b>`
					: `<span style="color:${cfg.color};">${label}</span>`;
			}
			if (fn === "money_in" || fn === "money_out") {
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

		if (fn === "party" && value) value = `<b>${value}</b>`;

		if (fn === "money_in" && (parseFloat(data.money_in) || 0) > 0) {
			value = `<span style="color:var(--green-600)">${value}</span>`;
		}
		if (fn === "money_out" && (parseFloat(data.money_out) || 0) > 0) {
			value = `<span style="color:var(--red-500)">${value}</span>`;
		}
		if (fn === "balance") {
			const raw = parseFloat(data.balance) || 0;
			if (raw < 0) return `<span style="color:var(--red-500)">${value}</span>`;
			if (raw > 0) return `<span style="color:var(--green-600)">${value}</span>`;
		}

		return value;
	},
};
