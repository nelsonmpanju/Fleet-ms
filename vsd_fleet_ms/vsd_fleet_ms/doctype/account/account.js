// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Account", {
	setup(frm) {
		frm.set_query("parent_account", function () {
			return { filters: { is_group: 1 } };
		});
	},

	parent_account(frm) {
		if (!frm.doc.parent_account) return;

		// Inherit account_type from parent
		frappe.db.get_value("Account", frm.doc.parent_account, "account_type").then((r) => {
			const parentType = r.message && r.message.account_type;
			if (parentType && !frm.doc.account_type) {
				frm.set_value("account_type", parentType);
			}
		});

		// Auto-suggest next account number (only when creating a new record)
		if (frm.is_new() && !frm.doc.account_number) {
			frappe.call({
				method: "vsd_fleet_ms.vsd_fleet_ms.doctype.account.account.get_next_account_number",
				args: { parent_account: frm.doc.parent_account },
				callback(r) {
					if (r.message) {
						frm.set_value("account_number", r.message);
					}
				},
			});
		}
	},
});
