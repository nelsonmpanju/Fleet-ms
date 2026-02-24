// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Supplier", {
	refresh(frm) {
		if (frm.doc.name && !frm.is_new()) {
			render_supplier_stats(frm);
		}
	},
});

function render_supplier_stats(frm) {
	let wrapper = frm.fields_dict.html_xhuu.$wrapper;
	wrapper.html('<div class="fleet-loading">Loading statistics...</div>');

	frappe.xcall(
		"vsd_fleet_ms.vsd_fleet_ms.utils.stats.get_supplier_stats",
		{ supplier: frm.doc.name }
	).then((data) => {
		if (!data || !data.invoice_count) {
			wrapper.html(
				'<div class="fleet-stats-container"><p style="color:#b2bec3;text-align:center;padding:20px;">No transaction data yet</p></div>'
			);
			return;
		}
		let html = `<div class="fleet-stats-container">
			<div class="fleet-stats-header">Supplier Statistics</div>
			<div class="fleet-kpi-row">
				${skpi(data.invoice_count, "Invoices", null, "blue")}
				${skpi(sfmt(data.spend), "Total Spend", null, "red")}
				${skpi(sfmt(data.paid), "Paid", null, "green")}
				${skpi(sfmt(data.outstanding), "Outstanding", null, "orange")}
				${skpi(sfmt(data.fuel_spend), "Fuel Spend", null, "purple")}
				${skpi(sfmt(data.fuel_litres) + " L", "Fuel Litres", null, "teal")}
			</div>`;

		if (data.recent_invoices && data.recent_invoices.length) {
			html += `<div class="fleet-stats-table">
				<div class="fleet-chart-title">Recent Purchase Invoices</div>
				<div class="fleet-table-card">
					<table>
						<thead><tr>
							<th>Invoice</th><th>Date</th><th>Type</th><th>Total</th>
							<th>Paid</th><th>Outstanding</th><th>Status</th>
						</tr></thead><tbody>`;
			data.recent_invoices.forEach((r) => {
				let badge = spayment_badge(r.payment_status);
				html += `<tr>
					<td><a href="/app/purchase-invoice/${r.name}">${r.name}</a></td>
					<td>${frappe.datetime.str_to_user(r.posting_date) || ""}</td>
					<td>${r.invoice_type || ""}</td>
					<td>${sfmt(r.grand_total)}</td>
					<td>${sfmt(r.paid_amount)}</td>
					<td>${sfmt(r.outstanding_amount)}</td>
					<td>${badge}</td>
				</tr>`;
			});
			html += "</tbody></table></div></div>";
		}
		html += "</div>";
		wrapper.html(html);
	});
}

function skpi(value, label, sub, color) {
	return `<div class="fleet-kpi-card fleet-kpi-${color}">
		<div class="fleet-kpi-value">${value}</div>
		<div class="fleet-kpi-label">${label}</div>
		${sub ? `<div class="fleet-kpi-sub">${sub}</div>` : ""}
	</div>`;
}

function sfmt(n) {
	return format_number(n);
}

function spayment_badge(status) {
	let map = { Paid: "green", "Partly Paid": "orange", Unpaid: "red" };
	let c = map[status] || "gray";
	return `<span class="fleet-badge fleet-badge-${c}">${status}</span>`;
}
