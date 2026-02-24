// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.pages["fleet-finance-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Fleet Finance"),
		single_column: true,
	});

	const dash = new FleetFinanceDashboard(page);
	dash.init();
};

class FleetFinanceDashboard {
	constructor(page) {
		this.page = page;
		this.from_date = frappe.datetime.month_start();
		this.to_date   = frappe.datetime.get_today();
	}

	init() {
		this._add_filter_bar();
		this._render_skeleton();
		this.refresh();
	}

	// ── date filter bar ────────────────────────────────────────────────────────

	_add_filter_bar() {
		const bar = $(`
			<div class="fleet-filter-bar">
				<button class="btn btn-sm btn-default fleet-date-btn active" data-range="month">${__("This Month")}</button>
				<button class="btn btn-sm btn-default fleet-date-btn" data-range="last_month">${__("Last Month")}</button>
				<button class="btn btn-sm btn-default fleet-date-btn" data-range="quarter">${__("This Quarter")}</button>
				<button class="btn btn-sm btn-default fleet-date-btn" data-range="year">${__("This Year")}</button>
				<span style="margin:0 8px;color:#aaa">|</span>
				<input type="date" class="fleet-date-input" id="fin-from" value="${this.from_date}">
				<span style="margin:0 4px">—</span>
				<input type="date" class="fleet-date-input" id="fin-to" value="${this.to_date}">
				<button class="btn btn-sm btn-primary" id="fin-apply">${__("Apply")}</button>
			</div>
		`).appendTo(this.page.main);

		bar.on("click", ".fleet-date-btn", (e) => {
			bar.find(".fleet-date-btn").removeClass("active");
			$(e.currentTarget).addClass("active");
			const range = $(e.currentTarget).data("range");
			const dates = this._date_range(range);
			this.from_date = dates[0];
			this.to_date   = dates[1];
			$("#fin-from").val(this.from_date);
			$("#fin-to").val(this.to_date);
			this.refresh();
		});

		$("#fin-apply", bar).on("click", () => {
			this.from_date = $("#fin-from").val();
			this.to_date   = $("#fin-to").val();
			bar.find(".fleet-date-btn").removeClass("active");
			this.refresh();
		});
	}

	_date_range(range) {
		const today = frappe.datetime.get_today();
		if (range === "month") return [frappe.datetime.month_start(), today];
		if (range === "last_month") {
			const d = new Date(today);
			d.setDate(1); d.setMonth(d.getMonth() - 1);
			const s = frappe.datetime.obj_to_str(d);
			const last = new Date(new Date(frappe.datetime.month_start()) - 1);
			return [s, frappe.datetime.obj_to_str(last)];
		}
		if (range === "quarter") {
			const m = new Date().getMonth();
			const q = Math.floor(m / 3);
			const qs = new Date(new Date().getFullYear(), q * 3, 1);
			return [frappe.datetime.obj_to_str(qs), today];
		}
		if (range === "year") return [today.slice(0, 4) + "-01-01", today];
		return [frappe.datetime.month_start(), today];
	}

	// ── skeleton ───────────────────────────────────────────────────────────────

	_render_skeleton() {
		$(this.page.main).append(`
			<div id="fin-dashboard">
				<div class="fleet-section-title">${__("Cash Position")}</div>
				<div id="fin-kpi-row0" class="fleet-kpi-row"></div>

				<div class="fleet-section-title">${__("Revenue & Receivables")}</div>
				<div id="fin-kpi-row1" class="fleet-kpi-row"></div>

				<div class="fleet-section-title">${__("Purchases & Payables")}</div>
				<div id="fin-kpi-row2" class="fleet-kpi-row"></div>

				<div class="fleet-section-title">${__("Profitability")}</div>
				<div id="fin-kpi-row3" class="fleet-kpi-row"></div>

				<div class="fleet-charts-grid">
					<div class="fleet-chart-card fleet-chart-wide">
						<div class="fleet-card-header">${__("Revenue vs Expenses (Monthly)")}</div>
						<div id="fin-monthly-chart"></div>
					</div>
					<div class="fleet-chart-card fleet-chart-wide">
						<div class="fleet-card-header">${__("Cash Flow — Payments In vs Out (Monthly)")}</div>
						<div id="fin-cashflow-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("AR Aging (Overdue Receivables)")}</div>
						<div id="fin-aging-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Trip Expense by Type")}</div>
						<div id="fin-expense-type-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Sales Payment Status")}</div>
						<div id="fin-si-status-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Purchase Payment Status")}</div>
						<div id="fin-pi-status-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Top 10 Customers")}</div>
						<div id="fin-customers-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Top 10 Suppliers")}</div>
						<div id="fin-suppliers-chart"></div>
					</div>
				</div>

				<div class="fleet-two-col">
					<div>
						<div class="fleet-section-title">${__("Unpaid Sales Invoices")}</div>
						<div id="fin-si-table"></div>
					</div>
					<div>
						<div class="fleet-section-title">${__("Unpaid Purchase Invoices")}</div>
						<div id="fin-pi-table"></div>
					</div>
				</div>
			</div>
		`);
	}

	// ── main refresh ───────────────────────────────────────────────────────────

	refresh() {
		const M    = "vsd_fleet_ms.vsd_fleet_ms.page.fleet_finance_dashboard.fleet_finance_dashboard";
		const args = { from_date: this.from_date, to_date: this.to_date };
		Promise.all([
			frappe.xcall(`${M}.get_finance_kpis`, args),
			frappe.xcall(`${M}.get_revenue_vs_expense_monthly`, args),
			frappe.xcall(`${M}.get_top_customers`, {...args, limit: 10}),
			frappe.xcall(`${M}.get_top_suppliers`, {...args, limit: 10}),
			frappe.xcall(`${M}.get_unpaid_invoices`, {doctype: "Sales Invoice", limit: 20}),
			frappe.xcall(`${M}.get_unpaid_invoices`, {doctype: "Purchase Invoice", limit: 20}),
			frappe.xcall(`${M}.get_payment_status_breakdown`, args),
			frappe.xcall(`${M}.get_expense_by_type`, args),
			frappe.xcall(`${M}.get_cash_flow_monthly`, args),
			frappe.xcall(`${M}.get_ar_aging`),
		]).then(([kpis, monthly, customers, suppliers, si_unpaid, pi_unpaid, payment_status, exp_types, cashflow, aging]) => {
			this._render_cash_position_kpis(kpis);
			this._render_revenue_kpis(kpis);
			this._render_purchase_kpis(kpis);
			this._render_profit_kpis(kpis);
			this._render_monthly_chart(monthly);
			this._render_cashflow_chart(cashflow);
			this._render_aging_chart(aging);
			this._render_payment_status_charts(payment_status);
			this._render_expense_type_chart(exp_types);
			this._render_customers_chart(customers);
			this._render_suppliers_chart(suppliers);
			this._render_unpaid_table("#fin-si-table", si_unpaid, "Sales Invoice");
			this._render_unpaid_table("#fin-pi-table", pi_unpaid, "Purchase Invoice");
		});
	}

	// ── KPI rows ───────────────────────────────────────────────────────────────

	_render_cash_position_kpis(d) {
		const row = $("#fin-kpi-row0").empty();
		[
			{label: __("Cash Balance"),  value: format_currency(d.cash_balance),  color: d.cash_balance >= 0 ? "blue" : "red",    icon: "🏦", hint: __("All cash & bank accounts")},
			{label: __("Payments In"),   value: format_currency(d.payments_in),   color: "green",  icon: "⬇️", hint: __("Period received")},
			{label: __("Payments Out"),  value: format_currency(d.payments_out),  color: "orange", icon: "⬆️", hint: __("Period paid out")},
			{label: __("Net Cash Flow"), value: format_currency(d.net_cash),      color: d.net_cash >= 0 ? "green" : "red", icon: "💱"},
		].forEach(i => row.append(this._kpi_card(i)));
	}

	_render_revenue_kpis(d) {
		const row = $("#fin-kpi-row1").empty();
		[
			{label: __("Revenue"),      value: format_currency(d.revenue),            color: "blue",   icon: "💰", hint: d.si_count + " " + __("invoice(s)")},
			{label: __("Collected"),    value: format_currency(d.collected),          color: "green",  icon: "✅", hint: d.collection_rate + "% " + __("collected")},
			{label: __("Outstanding"),  value: format_currency(d.receivables),        color: d.receivables > 0 ? "orange" : "green", icon: "⏳"},
			{label: __("Overdue >30d"), value: format_currency(d.overdue_si_amount), color: d.overdue_si_count > 0 ? "red" : "green", icon: "⚠️", hint: d.overdue_si_count + " " + __("invoice(s)")},
		].forEach(i => row.append(this._kpi_card(i)));
	}

	_render_purchase_kpis(d) {
		const row = $("#fin-kpi-row2").empty();
		[
			{label: __("Purchases"),    value: format_currency(d.purchases),          color: "blue",   icon: "🛒", hint: d.pi_count + " " + __("invoice(s)")},
			{label: __("Paid"),         value: format_currency(d.paid),               color: "green",  icon: "✅", hint: d.payment_rate + "% " + __("paid")},
			{label: __("Payables"),     value: format_currency(d.payables),           color: d.payables > 0 ? "orange" : "green", icon: "⏳"},
			{label: __("Overdue >30d"), value: format_currency(d.overdue_pi_amount), color: d.overdue_pi_count > 0 ? "red" : "green", icon: "⚠️", hint: d.overdue_pi_count + " " + __("invoice(s)")},
		].forEach(i => row.append(this._kpi_card(i)));
	}

	_render_profit_kpis(d) {
		const row = $("#fin-kpi-row3").empty();
		[
			{label: __("Gross Profit"),  value: format_currency(d.gross_profit),  color: d.gross_profit >= 0 ? "green" : "red",  icon: "📈"},
			{label: __("Net Profit"),    value: format_currency(d.net_profit),    color: d.net_profit >= 0 ? "green" : "red",    icon: "💹", hint: d.profit_margin + "% " + __("margin")},
			{label: __("Trip Expenses"), value: format_currency(d.trip_expense),  color: "orange", icon: "🚛"},
		].forEach(i => row.append(this._kpi_card(i)));
	}

	_kpi_card({label, value, color, icon, hint}) {
		return `
			<div class="fleet-kpi-card fleet-kpi-${color}">
				<div class="fleet-kpi-icon">${icon}</div>
				<div class="fleet-kpi-value">${value}</div>
				<div class="fleet-kpi-label">${label}</div>
				${hint ? `<div class="fleet-kpi-hint">${hint}</div>` : ""}
			</div>`;
	}

	// ── charts ─────────────────────────────────────────────────────────────────

	_render_monthly_chart(data) {
		if (!data) return;
		const rev = data.revenue || [];
		const exp = data.expense || [];

		// Merge all periods
		const periods = [...new Set([...rev.map(r => r.period), ...exp.map(r => r.period)])].sort();
		if (!periods.length) return;

		const rev_map = Object.fromEntries(rev.map(r => [r.period, r.amount]));
		const exp_map = Object.fromEntries(exp.map(r => [r.period, r.amount]));

		this._frappe_chart("#fin-monthly-chart", {
			data: {
				labels: periods,
				datasets: [
					{ name: __("Revenue"),   values: periods.map(p => flt(rev_map[p] || 0)) },
					{ name: __("Purchases"), values: periods.map(p => flt(exp_map[p] || 0)) },
				],
			},
			type: "bar",
			height: 240,
			colors: ["#4e79a7","#e15759"],
		});
	}

	_render_payment_status_charts(data) {
		if (!data) return;

		const _render = (selector, rows) => {
			if (!rows || !rows.length) return;
			const labels = rows.map(r => r.payment_status || "Unknown");
			const values = rows.map(r => flt(r.amount || 0));
			this._frappe_chart(selector, {
				data: { labels, datasets: [{ values }] },
				type: "donut",
				height: 200,
				colors: ["#dc3545","#fd7e14","#28a745"],
			});
		};

		_render("#fin-si-status-chart", data.sales);
		_render("#fin-pi-status-chart", data.purchases);
	}

	_render_expense_type_chart(rows) {
		if (!rows || !rows.length) return;
		this._frappe_chart("#fin-expense-type-chart", {
			data: {
				labels: rows.map(r => r.expense_type || "Other"),
				datasets: [{ values: rows.map(r => flt(r.amount || 0)) }],
			},
			type: "pie",
			height: 200,
		});
	}

	_render_customers_chart(rows) {
		if (!rows || !rows.length) return;
		this._frappe_chart("#fin-customers-chart", {
			data: {
				labels: rows.map(r => r.customer || "—"),
				datasets: [
					{ name: __("Revenue"),   values: rows.map(r => flt(r.revenue || 0)) },
					{ name: __("Collected"), values: rows.map(r => flt(r.collected || 0)) },
				],
			},
			type: "bar",
			height: 220,
			colors: ["#4e79a7","#59a14f"],
		});
	}

	_render_suppliers_chart(rows) {
		if (!rows || !rows.length) return;
		this._frappe_chart("#fin-suppliers-chart", {
			data: {
				labels: rows.map(r => r.supplier || "—"),
				datasets: [
					{ name: __("Purchases"), values: rows.map(r => flt(r.purchases || 0)) },
					{ name: __("Paid"),      values: rows.map(r => flt(r.paid || 0)) },
				],
			},
			type: "bar",
			height: 220,
			colors: ["#e15759","#59a14f"],
		});
	}

	_render_cashflow_chart(rows) {
		if (!rows || !rows.length) return;
		const periods = rows.map(r => r.period);
		this._frappe_chart("#fin-cashflow-chart", {
			data: {
				labels: periods,
				datasets: [
					{ name: __("Cash In"),  values: rows.map(r => flt(r.cash_in  || 0)) },
					{ name: __("Cash Out"), values: rows.map(r => flt(r.cash_out || 0)) },
				],
			},
			type: "bar",
			height: 240,
			colors: ["#59a14f", "#e15759"],
		});
	}

	_render_aging_chart(data) {
		if (!data) return;
		const buckets = ["0-30", "31-60", "61-90", "90+"];
		const values  = buckets.map(b => flt(data[b] || 0));
		if (!values.some(v => v > 0)) return;
		this._frappe_chart("#fin-aging-chart", {
			data: {
				labels: buckets.map(b => b + " " + __("days")),
				datasets: [{ values }],
			},
			type: "bar",
			height: 200,
			colors: ["#59a14f", "#f28e2b", "#e15759", "#b07aa1"],
		});
	}

	_frappe_chart(selector, config) {
		const el = $(selector)[0];
		if (!el) return;
		try {
			new frappe.Chart(el, {
				...config,
				tooltipOptions: { formatTooltipX: d => d },
			});
		} catch(e) {
			console.warn("Chart error:", e);
		}
	}

	// ── unpaid invoice tables ──────────────────────────────────────────────────

	_render_unpaid_table(selector, rows, doctype) {
		const el = $(selector).empty();
		if (!rows || !rows.length) {
			el.html('<p class="text-muted">' + __("All invoices paid.") + '</p>');
			return;
		}

		const slug = doctype === "Sales Invoice" ? "sales-invoice" : "purchase-invoice";
		let html = `<table class="fleet-table">
			<thead><tr>
				<th>${__("Invoice")}</th><th>${__("Date")}</th>
				<th>${__("Party")}</th><th>${__("Total")}</th>
				<th>${__("Outstanding")}</th><th>${__("Status")}</th>
			</tr></thead><tbody>`;

		rows.forEach(r => {
			const days = Math.round((new Date() - new Date(r.posting_date)) / 86400000);
			const age_class = days > 60 ? "red" : days > 30 ? "orange" : "";
			html += `<tr>
				<td><a href="/app/${slug}/${r.name}">${r.name}</a></td>
				<td class="${age_class}">${r.posting_date}</td>
				<td>${r.party || "—"}</td>
				<td>${format_currency(r.grand_total)}</td>
				<td style="color:red;font-weight:bold">${format_currency(r.outstanding_amount)}</td>
				<td>${r.payment_status || "Unpaid"}</td>
			</tr>`;
		});

		el.html(html + "</tbody></table>");
	}
}

function flt(v) { return parseFloat(v || 0); }

function format_currency(v) {
	return parseFloat(v || 0).toLocaleString(undefined, {
		minimumFractionDigits: 0,
		maximumFractionDigits: 0,
	});
}
