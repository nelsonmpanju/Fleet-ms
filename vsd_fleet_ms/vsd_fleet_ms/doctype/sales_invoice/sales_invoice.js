// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice", {
	setup(frm) {
		frm.set_query("income_account", function () {
			return {
				filters: {
					is_group: 0,
					account_type: "Income",
				},
			};
		});

		frm.set_query("income_account", "items", function () {
			return {
				filters: {
					is_group: 0,
					account_type: "Income",
				},
			};
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) {
			return;
		}

		if (frm.doc.ledger_entry) {
			frm.add_custom_button(__("Ledger Entry"), () => {
				frappe.set_route("Form", "Ledger Entry", frm.doc.ledger_entry);
			}, __("View"));
		}

		const outstanding = parseFloat(frm.doc.outstanding_amount || 0);
		if (outstanding > 0) {
			frm.add_custom_button(__("Receive Payment"), () => {
				frappe.call({
					method: "vsd_fleet_ms.vsd_fleet_ms.doctype.payment_entry.payment_entry.create_payment_entry_for_sales_invoice",
					args: { sales_invoice: frm.doc.name },
					callback: function (r) {
						if (r.message) {
							frappe.set_route("Form", "Payment Entry", r.message);
						}
					}
				});
			}, __("Create"));
		}

		frm.add_custom_button(__("View Payments"), () => {
			frappe.set_route("List", "Payment Entry", {
				reference_doctype: "Sales Invoice",
				reference_name: frm.doc.name
			});
		}, __("View"));
	}
});

frappe.ui.form.on("Sales Invoice Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code || row.income_account) {
			return;
		}

		frappe.db.get_value("Item", row.item_code, "income_account").then((r) => {
			const account = r.message && r.message.income_account;
			if (!account) {
				return;
			}
			frappe.model.set_value(cdt, cdn, "income_account", account);
			if (!frm.doc.income_account) {
				frm.set_value("income_account", account);
			}
		});
	},
});
