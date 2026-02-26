// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.pages["fleet-operations-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Fleet Operations"),
		single_column: true,
	});

	const dash = new FleetOperationsDashboard(page);
	dash.init();
};

class FleetOperationsDashboard {
	constructor(page) {
		this.page = page;
		this.from_date = frappe.datetime.month_start();
		this.to_date   = frappe.datetime.get_today();
		this.charts    = {};
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
				<input type="date" class="fleet-date-input" id="ops-from" value="${this.from_date}">
				<span style="margin:0 4px">—</span>
				<input type="date" class="fleet-date-input" id="ops-to" value="${this.to_date}">
				<button class="btn btn-sm btn-primary" id="ops-apply">${__("Apply")}</button>
			</div>
		`).appendTo(this.page.main);

		bar.on("click", ".fleet-date-btn", (e) => {
			bar.find(".fleet-date-btn").removeClass("active");
			$(e.currentTarget).addClass("active");
			const range = $(e.currentTarget).data("range");
			const dates = this._date_range(range);
			this.from_date = dates[0];
			this.to_date   = dates[1];
			$("#ops-from").val(this.from_date);
			$("#ops-to").val(this.to_date);
			this.refresh();
		});

		$("#ops-apply", bar).on("click", () => {
			this.from_date = $("#ops-from").val();
			this.to_date   = $("#ops-to").val();
			bar.find(".fleet-date-btn").removeClass("active");
			this.refresh();
		});
	}

	_date_range(range) {
		const today = frappe.datetime.get_today();
		if (range === "month")      return [frappe.datetime.month_start(), today];
		if (range === "last_month") {
			const d = new Date(today);
			d.setDate(1); d.setMonth(d.getMonth() - 1);
			const s = frappe.datetime.obj_to_str(d);
			const e = frappe.datetime.month_start().replace(/-\d{2}$/, "");
			const last = new Date(new Date(frappe.datetime.month_start()) - 1);
			return [s, frappe.datetime.obj_to_str(last)];
		}
		if (range === "quarter") {
			const m = new Date().getMonth();
			const q = Math.floor(m / 3);
			const qs = new Date(new Date().getFullYear(), q * 3, 1);
			return [frappe.datetime.obj_to_str(qs), today];
		}
		if (range === "year")   return [today.slice(0, 4) + "-01-01", today];
		return [frappe.datetime.month_start(), today];
	}

	// ── skeleton ───────────────────────────────────────────────────────────────

	_render_skeleton() {
		$(this.page.main).append(`
			<div id="ops-dashboard">

				<div class="fleet-section-title fleet-section-live">${__("Live Status")} <span class="fleet-live-dot"></span></div>
				<div id="ops-live-row" class="fleet-kpi-row"></div>

				<div class="fleet-section-title">${__("Trip Overview")}</div>
				<div id="ops-kpi-row" class="fleet-kpi-row"></div>

				<div class="fleet-section-title">${__("Efficiency & Performance")}</div>
				<div id="ops-kpi-row3" class="fleet-kpi-row"></div>

				<div class="fleet-section-title">${__("Fleet & Cargo")}</div>
				<div id="ops-kpi-row2" class="fleet-kpi-row"></div>

				<div class="fleet-charts-grid">
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Trip Status")}</div>
						<div id="ops-status-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Trips per Period")}</div>
						<div id="ops-period-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Top Routes")}</div>
						<div id="ops-routes-chart"></div>
					</div>
					<div class="fleet-chart-card">
						<div class="fleet-card-header">${__("Truck Utilisation")}</div>
						<div id="ops-trucks-chart"></div>
					</div>
				</div>

				<div class="fleet-section-title">${__("Recent Trips")}</div>
				<div id="ops-recent-table"></div>

				<div class="fleet-section-title">${__("Driver Performance")}</div>
				<div id="ops-driver-table"></div>
			</div>
		`);
	}

	// ── main refresh ───────────────────────────────────────────────────────────

	refresh() {
		const args = { from_date: this.from_date, to_date: this.to_date };
		const M = "vsd_fleet_ms.vsd_fleet_ms.page.fleet_operations_dashboard.fleet_operations_dashboard";
		Promise.all([
			frappe.xcall(`${M}.get_trip_kpis`, args),
			frappe.xcall(`${M}.get_cargo_kpis`, args),
			frappe.xcall(`${M}.get_fleet_status`),
			frappe.xcall(`${M}.get_trips_by_period`, args),
			frappe.xcall(`${M}.get_top_routes`, {...args, limit: 10}),
			frappe.xcall(`${M}.get_truck_utilisation`, {...args, limit: 12}),
			frappe.xcall(`${M}.get_recent_trips`, {...args, limit: 25}),
			frappe.xcall(`${M}.get_driver_stats`, {...args, limit: 10}),
			frappe.xcall(`${M}.get_live_status`),
		]).then(([kpis, cargo, fleet_status, period, routes, trucks, recent, drivers, live]) => {
			this._render_live_kpis(live);
			this._render_trip_kpis(kpis);
			this._render_efficiency_kpis(kpis);
			this._render_cargo_kpis(cargo, kpis, fleet_status);
			this._render_status_chart(kpis);
			this._render_period_chart(period);
			this._render_routes_chart(routes);
			this._render_truck_chart(trucks);
			this._render_recent_trips(recent);
			this._render_driver_table(drivers);
		});
	}

	// ── KPI rows ───────────────────────────────────────────────────────────────

	_render_live_kpis(d) {
		const row = $("#ops-live-row").empty();
		const items = [
			{
				label: __("In Transit Now"),
				value: d.in_transit_now,
				color: d.in_transit_now > 0 ? "orange" : "gray",
				icon: "🚛",
			},
			{
				label: __("Breakdowns"),
				value: d.breakdown_now,
				color: d.breakdown_now > 0 ? "red" : "green",
				icon: d.breakdown_now > 0 ? "🚨" : "✅",
			},
			{
				label: __("Trucks on Road"),
				value: d.trucks_on_trip,
				color: "blue",
				icon: "🛣️",
			},
			{
				label: __("Overdue Trips"),
				value: d.overdue_trips,
				color: d.overdue_trips > 0 ? "red" : "green",
				icon: d.overdue_trips > 0 ? "⚠️" : "✅",
				hint: __(">5 days in transit"),
			},
			{
				label: __("Pending Expenses"),
				value: d.pending_fund_count,
				color: d.pending_fund_count > 0 ? "orange" : "green",
				icon: "💸",
				hint: fmt_number(d.pending_fund_amount, 0),
			},
			{
				label: __("Pending Trips"),
				value: d.pending_now,
				color: d.pending_now > 0 ? "orange" : "gray",
				icon: "⏳",
			},
		];
		items.forEach(i => row.append(this._kpi_card(i)));
	}

	_render_efficiency_kpis(d) {
		const row = $("#ops-kpi-row3").empty();
		const items = [
			{
				label: __("Completion Rate"),
				value: d.completion_rate + "%",
				color: d.completion_rate >= 80 ? "green" : d.completion_rate >= 60 ? "orange" : "red",
				icon: "🎯",
				hint: `${d.completed} / ${d.total_trips} trips`,
			},
			{
				label: __("Breakdown Rate"),
				value: d.breakdown_rate + "%",
				color: d.breakdown_rate === 0 ? "green" : d.breakdown_rate < 5 ? "orange" : "red",
				icon: "🔧",
				hint: `${d.breakdowns} breakdowns`,
			},
			{
				label: __("Fuel / KM (L)"),
				value: d.fuel_per_km,
				color: d.fuel_per_km > 0 ? (d.fuel_per_km < 0.4 ? "green" : "orange") : "gray",
				icon: "⛽",
				hint: __("Litres per kilometre"),
			},
			{
				label: __("Avg Distance (KM)"),
				value: fmt_number(d.avg_distance, 0),
				color: "blue",
				icon: "📍",
				hint: __("Per trip"),
			},
			{
				label: __("Fleet Utilisation"),
				value: d.utilisation + "%",
				color: d.utilisation >= 70 ? "green" : "orange",
				icon: "📊",
				hint: `${d.active_trucks} / ${d.total_trucks} trucks`,
			},
		];
		items.forEach(i => row.append(this._kpi_card(i)));
	}

	_render_trip_kpis(d) {
		const row = $("#ops-kpi-row").empty();
		const items = [
			{label: __("Total Trips"),    value: d.total_trips,    color: "blue",   icon: "🚛"},
			{label: __("Completed"),      value: d.completed,      color: "green",  icon: "✅"},
			{label: __("In Transit"),     value: d.in_transit,     color: "orange", icon: "🔄"},
			{label: __("Breakdown"),      value: d.breakdowns,     color: d.breakdowns > 0 ? "red" : "gray", icon: "⚠️"},
			{label: __("Pending"),        value: d.pending,        color: "gray",   icon: "⏳"},
			{label: __("In House"),       value: d.in_house,       color: "blue",   icon: "🏠", hint: __("Own fleet")},
			{label: __("Sub-Contractor"), value: d.sub_contractor, color: "gray",   icon: "🤝", hint: __("Outsourced")},
			{label: __("Total Distance"), value: fmt_number(d.total_distance, 0) + " km", color: "green", icon: "📍"},
			{label: __("Total Fuel"),     value: fmt_number(d.total_fuel, 0) + " L",  color: "orange", icon: "⛽"},
		];
		items.forEach(i => row.append(this._kpi_card(i)));
	}

	_render_cargo_kpis(cargo, kpis, fleet_status) {
		const row = $("#ops-kpi-row2").empty();
		const items = [
			{label: __("Bookings"),         value: cargo.bookings,                    color: "blue",   icon: "📦"},
			{label: __("Total Weight (T)"), value: fmt_number(cargo.total_weight, 1), color: "blue",   icon: "⚖️"},
			{label: __("Packages"),         value: cargo.total_packages,              color: "blue",   icon: "📫"},
			{label: __("Distance (KM)"),    value: fmt_number(kpis.total_distance, 0),color: "green",  icon: "📍"},
			{label: __("Fuel Used (L)"),    value: fmt_number(kpis.total_fuel, 0),    color: "orange", icon: "⛽"},
			{label: __("Active Trucks"),    value: kpis.active_trucks + "/" + kpis.total_trucks, color: "blue", icon: "🚚"},
			{label: __("Under Maintenance"),value: fleet_status["Under Maintenance"] || 0, color: "red", icon: "🔧"},
		];
		items.forEach(i => row.append(this._kpi_card(i)));
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

	_render_status_chart(d) {
		const labels = ["Completed","In Transit","Breakdown","Pending"];
		const vals   = [d.completed, d.in_transit, d.breakdowns, d.pending];
		if (vals.every(v => !v)) return;

		this._frappe_chart("#ops-status-chart", {
			data: { labels, datasets: [{ values: vals }] },
			type: "donut",
			height: 200,
			colors: ["#28a745","#fd7e14","#dc3545","#6c757d"],
		});
	}

	_render_period_chart(rows) {
		if (!rows || !rows.length) return;
		this._frappe_chart("#ops-period-chart", {
			data: {
				labels: rows.map(r => r.period),
				datasets: [
					{ name: __("In House"),       values: rows.map(r => r.in_house || 0) },
					{ name: __("Sub-Contractor"), values: rows.map(r => r.sub_contractor || 0) },
				],
			},
			type: "bar",
			height: 200,
			barOptions: { stacked: 1 },
			colors: ["#4e79a7","#f28e2b"],
		});
	}

	_render_routes_chart(rows) {
		if (!rows || !rows.length) return;
		this._frappe_chart("#ops-routes-chart", {
			data: {
				labels: rows.map(r => r.route || "—"),
				datasets: [{ name: __("Trips"), values: rows.map(r => r.trips || 0) }],
			},
			type: "bar",
			height: 200,
			colors: ["#59a14f"],
		});
	}

	_render_truck_chart(rows) {
		if (!rows || !rows.length) return;
		this._frappe_chart("#ops-trucks-chart", {
			data: {
				labels: rows.map(r => r.truck || "—"),
				datasets: [{ name: __("Trips"), values: rows.map(r => r.trips || 0) }],
			},
			type: "bar",
			height: 200,
			colors: ["#4e79a7"],
		});
	}

	_frappe_chart(selector, config) {
		const el = $(selector)[0];
		if (!el) return;
		try {
			new frappe.Chart(el, {
				...config,
				tooltipOptions: { formatTooltipX: d => d, formatTooltipY: d => d },
			});
		} catch(e) {
			console.warn("Chart error:", e);
		}
	}

	// ── tables ─────────────────────────────────────────────────────────────────

	_render_recent_trips(rows) {
		const el = $("#ops-recent-table").empty();
		if (!rows || !rows.length) { el.html('<p class="text-muted">' + __("No trips found.") + '</p>'); return; }

		let html = `<table class="fleet-table">
			<thead><tr>
				<th>${__("Trip")}</th><th>${__("Date")}</th><th>${__("Route")}</th>
				<th>${__("Truck")}</th><th>${__("Driver")}</th>
				<th>${__("Status")}</th><th>${__("Distance")}</th><th>${__("Fuel")}</th>
			</tr></thead><tbody>`;

		rows.forEach(r => {
			const status_class = r.trip_status === "Completed" ? "green" : r.trip_status === "In Transit" ? "orange" : r.trip_status === "Breakdown" ? "red" : "gray";
			html += `<tr>
				<td><a href="/app/trips/${r.name}">${r.name}</a></td>
				<td>${r.date || ""}</td>
				<td>${r.route || "—"}</td>
				<td>${r.truck_number || "—"}</td>
				<td>${r.driver_name || "—"}</td>
				<td><span class="indicator-pill ${status_class}">${r.trip_status || "—"}</span></td>
				<td>${r.total_distance || "—"}</td>
				<td>${fmt_number(r.total_fuel || 0, 0)}</td>
			</tr>`;
		});
		el.html(html + "</tbody></table>");
	}

	_render_driver_table(rows) {
		const el = $("#ops-driver-table").empty();
		if (!rows || !rows.length) { el.html('<p class="text-muted">' + __("No drivers found.") + '</p>'); return; }

		let html = `<table class="fleet-table">
			<thead><tr>
				<th>${__("Driver")}</th><th>${__("Name")}</th>
				<th>${__("Trips")}</th><th>${__("Completed")}</th>
				<th>${__("Breakdowns")}</th><th>${__("Completion %")}</th>
			</tr></thead><tbody>`;

		rows.forEach(r => {
			const pct = r.trips > 0 ? Math.round(r.completed / r.trips * 100) : 0;
			html += `<tr>
				<td><a href="/app/driver/${r.driver}">${r.driver}</a></td>
				<td>${r.driver_name || "—"}</td>
				<td><strong>${r.trips}</strong></td>
				<td>${r.completed}</td>
				<td>${r.breakdowns > 0 ? '<span style="color:red">' + r.breakdowns + '</span>' : 0}</td>
				<td>${pct}%</td>
			</tr>`;
		});
		el.html(html + "</tbody></table>");
	}
}

function fmt_number(v, decimals=0) {
	return parseFloat(v || 0).toLocaleString(undefined, {
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals,
	});
}
