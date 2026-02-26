// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
	setup(frm) {
		frm.set_query("payable_account", function () {
			return { filters: { is_group: 0, account_type: "Payable" } };
		});
		frm.set_query("expense_account", function () {
			return { filters: { is_group: 0, account_type: "Expense" } };
		});
	},

	onload(frm) {
		// Auto-fill expense_account for new forms based on invoice_type
		if (!frm.is_new() || frm.doc.expense_account) return;
		if (frm.doc.invoice_type === "Fuel") {
			frappe.db.get_single_value("Transport Settings", "fuel_expense_account").then(acc => {
				if (acc) frm.set_value("expense_account", acc);
			});
		}
	},

	invoice_type(frm) {
		if (!frm.doc.invoice_type || frm.doc.expense_account) return;
		if (frm.doc.invoice_type === "Fuel") {
			frappe.db.get_single_value("Transport Settings", "fuel_expense_account").then(acc => {
				if (acc) frm.set_value("expense_account", acc);
			});
		}
	},

	supplier(frm) {
		if (!frm.doc.supplier) return;
		// Auto-fill payable account from Supplier record first
		frappe.db.get_value("Supplier", frm.doc.supplier, ["payable_account", "default_currency"]).then(r => {
			const v = r.message || {};
			if (v.payable_account && !frm.doc.payable_account) {
				frm.set_value("payable_account", v.payable_account);
			} else if (!frm.doc.payable_account) {
				// Fall back to Transport Settings default
				frappe.db.get_single_value("Transport Settings", "default_payable_account").then(acc => {
					if (acc) frm.set_value("payable_account", acc);
				});
			}
			if (v.default_currency && !frm.doc.currency) {
				frm.set_value("currency", v.default_currency);
			}
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
			frm.add_custom_button(__("Make Payment"), () => {
				frappe.call({
					method: "vsd_fleet_ms.vsd_fleet_ms.doctype.payment_entry.payment_entry.create_payment_entry_for_purchase_invoice",
					args: { purchase_invoice: frm.doc.name },
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
				reference_doctype: "Purchase Invoice",
				reference_name: frm.doc.name
			});
		}, __("View"));
	}
});
