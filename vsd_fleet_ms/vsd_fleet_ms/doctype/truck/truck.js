// Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Truck', {
	// refresh: function(frm) {

	// }
	setup: function(frm){
		frm.set_query('trans_ms_driver', function () {
			return{
				filters: {
					"status": "Active"
				}
			}
			
		})
	},
	onload: function (frm) {
		// Select the element with data-fieldname="disabled"
		const element = document.querySelector('[data-fieldname="disabled"]');

		// Set its style color to red
		element.style.color = "red";

		frappe.db.get_single_value("Transport Settings", "vehicle_fuel_parent_warehouse")
		.then(function(value) {
			var default_parent_warehouse = value;

			frm.set_query("trans_ms_fuel_warehouse", function () {
				return {
					"filters": {
						"parent_warehouse": default_parent_warehouse
					}
				};
			});
		})
	},
	trans_ms_maintain_stock: (frm) => {
		frm.doc.trans_ms_fuel_warehouse = "";

	},
	refresh: function(frm){
		if (frm.doc.status != "On Trip"){
			frm.doc.trans_ms_current_trip = ''
			frm.refresh_field("trans_ms_current_trip")
		}

		if (!frm.is_new()) {
			// Compliance sync buttons
			frm.add_custom_button(__('Sync All Compliance'), function() {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.compliance.sync_truck_compliance',
					args: { truck: frm.doc.name },
					freeze: true,
					freeze_message: __('Syncing compliance data...'),
					callback: function(r) {
						if (r.message) {
							frappe.msgprint({
								title: __('Compliance Sync Complete'),
								message: r.message.replace(/\n/g, '<br>'),
								indicator: 'green'
							});
						}
					}
				});
			}, __('Compliance'));

			frm.add_custom_button(__('Parking Bills'), function() {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.compliance.sync_parking_bills',
					args: { truck: frm.doc.name },
					freeze: true,
					freeze_message: __('Fetching parking bills from TARURA...'),
					callback: function(r) {
						if (r.message) frappe.msgprint(r.message);
					}
				});
			}, __('Compliance'));

			frm.add_custom_button(__('Vehicle Fines'), function() {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.compliance.sync_vehicle_fines',
					args: { truck: frm.doc.name },
					freeze: true,
					freeze_message: __('Scraping fines from TPF...'),
					callback: function(r) {
						if (r.message) frappe.msgprint(r.message);
					}
				});
			}, __('Compliance'));

			frm.add_custom_button(__('Insurance'), function() {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.compliance.sync_insurance',
					args: { truck: frm.doc.name },
					freeze: true,
					freeze_message: __('Verifying cover note from TIRA...'),
					callback: function(r) {
						if (r.message) frappe.msgprint(r.message);
					}
				});
			}, __('Compliance'));

			// --- GPS Tracking buttons ---
			frm.add_custom_button(__('Link Traccar Device'), function() {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.traccar.link_truck_to_device',
					args: { truck_name: frm.doc.name },
					freeze: true,
					freeze_message: __('Searching for device in Traccar...'),
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(r.message);
							frm.reload_doc();
						}
					}
				});
			}, __('GPS'));

			if (frm.doc.traccar_device_id) {
				frm.add_custom_button(__('Sync GPS Position'), function() {
					frappe.call({
						method: 'vsd_fleet_ms.vsd_fleet_ms.utils.traccar.sync_vehicle_position',
						args: { truck_name: frm.doc.name },
						freeze: true,
						freeze_message: __('Fetching latest position from Traccar...'),
						callback: function(r) {
							if (r.message) {
								frappe.msgprint(r.message);
								frm.reload_doc();
							}
						}
					});
				}, __('GPS'));
			}

			// Show compliance summary card
			frappe.call({
				method: 'vsd_fleet_ms.vsd_fleet_ms.utils.compliance.get_truck_compliance_summary',
				args: { truck: frm.doc.name },
				callback: function(r) {
					if (!r.message) return;
					var d = r.message;
					var html = `
						<div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0;">
							<div style="background:#fff3cd;border-radius:6px;padding:10px 18px;min-width:120px;text-align:center;">
								<div style="font-size:22px;font-weight:700;color:#856404;">${d.outstanding_bills}</div>
								<div style="font-size:11px;color:#856404;">Parking Bills</div>
							</div>
							<div style="background:#f8d7da;border-radius:6px;padding:10px 18px;min-width:120px;text-align:center;">
								<div style="font-size:22px;font-weight:700;color:#721c24;">${d.unpaid_fines}</div>
								<div style="font-size:11px;color:#721c24;">Unpaid Fines</div>
							</div>
							<div style="background:#d4edda;border-radius:6px;padding:10px 18px;min-width:120px;text-align:center;">
								<div style="font-size:22px;font-weight:700;color:#155724;">${d.active_insurance}</div>
								<div style="font-size:11px;color:#155724;">Active Insurance</div>
							</div>
							<div style="background:#fff3cd;border-radius:6px;padding:10px 18px;min-width:120px;text-align:center;">
								<div style="font-size:22px;font-weight:700;color:#856404;">${d.expiring_insurance}</div>
								<div style="font-size:11px;color:#856404;">Expiring Soon</div>
							</div>
							<div style="background:#f8d7da;border-radius:6px;padding:10px 18px;min-width:120px;text-align:center;">
								<div style="font-size:22px;font-weight:700;color:#721c24;">${d.expired_insurance}</div>
								<div style="font-size:11px;color:#721c24;">Expired Insurance</div>
							</div>
						</div>`;
					frm.dashboard.set_headline_alert(html);
				}
			});
		}
	}
});
