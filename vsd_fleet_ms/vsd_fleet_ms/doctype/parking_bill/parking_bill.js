// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Parking Bill', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Sync from TARURA'), function() {
				if (!frm.doc.truck) {
					frappe.msgprint(__('Please select a Truck first.'));
					return;
				}
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.compliance.sync_parking_bills',
					args: { truck: frm.doc.truck },
					freeze: true,
					freeze_message: __('Fetching parking bills from TARURA...'),
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
});
