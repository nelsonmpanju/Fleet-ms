// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice", {
	setup(frm) {
		frm.set_query("income_account", function () {
			return { filters: { is_group: 0, account_type: "Income" } };
		});
		frm.set_query("income_account", "items", function () {
			return { filters: { is_group: 0, account_type: "Income" } };
		});
		frm.set_query("receivable_account", function () {
			return { filters: { is_group: 0, account_type: "Receivable" } };
		});
	},

	onload(frm) {
		// Auto-fill accounts from Transport Settings when creating a new invoice
		if (!frm.is_new()) return;

		frappe.xcall(
			"vsd_fleet_ms.vsd_fleet_ms.doctype.sales_invoice.sales_invoice.get_sales_invoice_defaults"
		).then(defaults => {
			if (defaults.income_account && !frm.doc.income_account) {
				frm.set_value("income_account", defaults.income_account);
				// Propagate to any rows that are already present
				(frm.doc.items || []).forEach((row) => {
					if (!row.income_account) {
						frappe.model.set_value(row.doctype, row.name, "income_account", defaults.income_account);
					}
				});
			}
			if (defaults.receivable_account && !frm.doc.receivable_account) {
				frm.set_value("receivable_account", defaults.receivable_account);
			}
		});
	},

	currency(frm) {
		vsd_fleet_ms.fetch_exchange_rate(frm);
	},

	posting_date(frm) {
		vsd_fleet_ms.fetch_exchange_rate(frm);
	},

	customer(frm) {
		if (!frm.doc.customer) return;
		// Fetch receivable account from Customer record first
		frappe.db.get_value("Customer", frm.doc.customer, "receivable_account").then(r => {
			const cust_acc = r.message && r.message.receivable_account;
			if (cust_acc) {
				frm.set_value("receivable_account", cust_acc);
			} else if (!frm.doc.receivable_account) {
				// Fall back to Transport Settings default
				frappe.xcall(
					"vsd_fleet_ms.vsd_fleet_ms.doctype.sales_invoice.sales_invoice.get_sales_invoice_defaults"
				).then(defaults => {
					if (defaults.receivable_account) {
						frm.set_value("receivable_account", defaults.receivable_account);
					}
				});
			}
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

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
					},
				});
			}, __("Create"));
		}

		frm.add_custom_button(__("View Payments"), () => {
			frappe.set_route("List", "Payment Entry", {
				reference_doctype: "Sales Invoice",
				reference_name: frm.doc.name,
			});
		}, __("View"));
	},
});

frappe.ui.form.on("Sales Invoice Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) return;

		frappe.db.get_value("Item", row.item_code, "income_account").then((r) => {
			const item_account = r.message && r.message.income_account;

			if (item_account) {
				// Item has its own income account — use it
				frappe.model.set_value(cdt, cdn, "income_account", item_account);
				if (!frm.doc.income_account) {
					frm.set_value("income_account", item_account);
				}
			} else if (!row.income_account) {
				// Item has no income account — fall back to header default
				const header_account = frm.doc.income_account;
				if (header_account) {
					frappe.model.set_value(cdt, cdn, "income_account", header_account);
				}
			}
		});
	},
});
