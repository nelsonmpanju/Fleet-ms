// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item", {
	setup(frm) {
		frm.set_query("income_account", function () {
			return {
				filters: {
					is_group: 0,
					account_type: "Income",
				},
			};
		});
	},
});
