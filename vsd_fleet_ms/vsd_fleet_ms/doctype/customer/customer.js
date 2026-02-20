// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.doc.name && !frm.is_new()) {
			render_customer_stats(frm);
		}
	},
});

function render_customer_stats(frm) {
	let wrapper = frm.fields_dict.html_yytc.$wrapper;
	wrapper.html('<div class="fleet-loading">Loading statistics...</div>');

	frappe.xcall(
		"vsd_fleet_ms.vsd_fleet_ms.utils.stats.get_customer_stats",
		{ customer: frm.doc.name }
	).then((data) => {
		if (!data || !data.invoice_count) {
			wrapper.html(
				'<div class="fleet-stats-container"><p style="color:#b2bec3;text-align:center;padding:20px;">No transaction data yet</p></div>'
			);
			return;
		}
		let html = `<div class="fleet-stats-container">
			<div class="fleet-stats-header">Customer Statistics</div>
			<div class="fleet-kpi-row">
				${kpi(data.invoice_count, "Invoices", null, "blue")}
				${kpi(fmt(data.billed), "Total Billed", null, "green")}
				${kpi(fmt(data.collected), "Collected", null, "teal")}
				${kpi(fmt(data.outstanding), "Outstanding", null, "orange")}
				${kpi(data.total_trips, "Trips", null, "purple")}
				${kpi(data.completed_trips, "Completed Trips", null, "green")}
			</div>`;

		if (data.recent_invoices && data.recent_invoices.length) {
			html += `<div class="fleet-stats-table">
				<div class="fleet-chart-title">Recent Invoices</div>
				<div class="fleet-table-card">
					<table>
						<thead><tr>
							<th>Invoice</th><th>Date</th><th>Total</th>
							<th>Paid</th><th>Outstanding</th><th>Status</th>
						</tr></thead><tbody>`;
			data.recent_invoices.forEach((r) => {
				let badge = payment_badge(r.payment_status);
				html += `<tr>
					<td><a href="/app/sales-invoice/${r.name}">${r.name}</a></td>
					<td>${frappe.datetime.str_to_user(r.posting_date) || ""}</td>
					<td>${fmt(r.grand_total)}</td>
					<td>${fmt(r.paid_amount)}</td>
					<td>${fmt(r.outstanding_amount)}</td>
					<td>${badge}</td>
				</tr>`;
			});
			html += "</tbody></table></div></div>";
		}
		html += "</div>";
		wrapper.html(html);
	});
}

function kpi(value, label, sub, color) {
	return `<div class="fleet-kpi-card fleet-kpi-${color}">
		<div class="fleet-kpi-value">${value}</div>
		<div class="fleet-kpi-label">${label}</div>
		${sub ? `<div class="fleet-kpi-sub">${sub}</div>` : ""}
	</div>`;
}

function fmt(n) {
	return format_number(n);
}

function payment_badge(status) {
	let map = { Paid: "green", "Partly Paid": "orange", Unpaid: "red" };
	let c = map[status] || "gray";
	return `<span class="fleet-badge fleet-badge-${c}">${status}</span>`;
}
