frappe.ui.form.on("Account", {
	setup(frm) {
		frm.set_query("parent_account", function () {
			return {
				filters: {
					is_group: 1,
				},
			};
		});
	},

	parent_account(frm) {
		if (!frm.doc.parent_account) {
			return;
		}

		frappe.db.get_value("Account", frm.doc.parent_account, "account_type").then((r) => {
			const parentType = r.message && r.message.account_type;
			if (parentType && !frm.doc.account_type) {
				frm.set_value("account_type", parentType);
			}
		});
	},
});
