// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) {
			return;
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
