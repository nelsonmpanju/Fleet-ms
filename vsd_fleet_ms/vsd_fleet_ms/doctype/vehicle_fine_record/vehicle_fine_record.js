// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Vehicle Fine Record', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Update Fine Status'), function() {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.compliance.update_fine_status',
					args: { reference: frm.doc.reference },
					freeze: true,
					freeze_message: __('Checking fine status from TPF...'),
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(__(r.message));
							frm.reload_doc();
						}
					}
				});
			}, __('Actions'));

			if (frm.doc.truck) {
				frm.add_custom_button(__('Sync All Fines for Truck'), function() {
					frappe.call({
						method: 'vsd_fleet_ms.vsd_fleet_ms.utils.compliance.sync_vehicle_fines',
						args: { truck: frm.doc.truck },
						freeze: true,
						freeze_message: __('Scraping fines from TPF...'),
						callback: function(r) {
							if (r.message) {
								frappe.msgprint(__(r.message));
								frm.reload_doc();
							}
						}
					});
				}, __('Actions'));
			}
		}
	}
});
