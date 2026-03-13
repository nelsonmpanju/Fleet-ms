// Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Transport Settings', {
	onload: function (frm) {
		frm.set_query("expense_account_group", function () {
			return {
				"filters": {
					"root_type": "Expense",
					"is_group": 1
				}
			};
		});
		frm.set_query("vehicle_fuel_parent_warehouse", function () {
			return {
				"filters": {
					"is_group": 1
				}
			};
		});
		frm.set_query("cash_or_bank_account_group", function () {
			return {
				"filters": {
					"root_type": "Asset",
					"is_group": 1
				}
			};
		});
	},

	refresh: function (frm) {
		if (frm.doc.traccar_enabled) {
			frm.add_custom_button(__('Test Connection'), function () {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.traccar.get_devices',
					freeze: true,
					freeze_message: __('Connecting to Traccar...'),
					callback: function (r) {
						if (r.message !== undefined) {
							var count = (r.message || []).length;
							frappe.msgprint({
								title: __('Connection Successful'),
								message: __('Found {0} device(s) in Traccar.', [count]),
								indicator: 'green'
							});
						}
					},
					error: function () {
						frappe.msgprint({
							title: __('Connection Failed'),
							message: __('Could not connect to Traccar. Check server URL and credentials.'),
							indicator: 'red'
						});
					}
				});
			}, __('Traccar'));

			frm.add_custom_button(__('Link All Unlinked Trucks'), function () {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.traccar.sync_all_device_links',
					freeze: true,
					freeze_message: __('Linking trucks to Traccar devices...'),
					callback: function (r) {
						if (r.message) {
							frappe.msgprint({
								title: __('Device Linking Complete'),
								message: r.message.replace(/\n/g, '<br>'),
								indicator: 'green'
							});
						}
					}
				});
			}, __('Traccar'));
		}
	},
});
