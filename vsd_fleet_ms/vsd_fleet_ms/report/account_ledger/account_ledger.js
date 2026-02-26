// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.query_reports["Account Ledger"] = {
	filters: [
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "Link",
			options: "Account",
			reqd: 1,
			get_query: function () {
				return { filters: { is_group: 0 } };
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
		// ── Party filters (optional — for receivable / payable drill-down) ────
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Select",
			options: "\nCustomer\nSupplier\nDriver",
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
			depends_on: "eval: doc.party_type",
		},
	],

	// ── Suppress certain columns in footer rows ────────────────────────────────
	_FOOTER_BLANK: ["posting_date", "voucher_no", "entry_type", "party", "balance"],

	// ── Visual config per footer row type ─────────────────────────────────────
	_FOOTER_STYLE: {
		opening:      { color: "var(--text-muted)",  bold: false },
		period_total: { color: "var(--blue-500)",    bold: true  },
		closing:      { color: "var(--green-600)",   bold: true  },
	},

	formatter: function (value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);

		const fn = column.fieldname;

		// ── Opening balance row prepended at the top of the table ─────────────
		if (data.is_opening) {
			const v = default_formatter(value, row, column, data);
			return fn === "balance"
				? `<span style="color:var(--text-muted);font-style:italic;">${v}</span>`
				: `<span style="color:var(--text-muted);">${v}</span>`;
		}

		// ── Tally-style footer rows at the bottom of the table ────────────────
		if (data.is_footer) {
			const cfg = frappe.query_reports["Account Ledger"]._FOOTER_STYLE[data.is_footer] || {};

			// Blank out irrelevant columns
			if (frappe.query_reports["Account Ledger"]._FOOTER_BLANK.includes(fn)) {
				return "";
			}

			// Description: label with styling
			if (fn === "description") {
				const label = value || "";
				const prefix = data.is_footer === "opening"
					? '<span style="display:inline-block;width:8px;border-top:2px solid var(--border-color);margin-right:6px;vertical-align:middle;"></span>'
					: "";
				return cfg.bold
					? `${prefix}<b style="color:${cfg.color};">${label}</b>`
					: `${prefix}<span style="color:${cfg.color};">${label}</span>`;
			}

			// Debit / credit: show bold only when non-zero
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

		// ── Normal transaction rows ────────────────────────────────────────────
		value = default_formatter(value, row, column, data);

		// Party column: bold when a party is present
		if (fn === "party" && value) {
			value = `<b>${value}</b>`;
		}

		// Balance: green for positive (we are owed / we have), red for negative
		if (fn === "balance") {
			const raw = parseFloat(data.balance) || 0;
			if (raw < 0) return `<span style="color:var(--red-500)">${value}</span>`;
			if (raw > 0) return `<span style="color:var(--green-600)">${value}</span>`;
		}

		return value;
	},
};
