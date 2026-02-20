// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payment Entry", {
	setup(frm) {
		frm.set_query("reference_name", function (doc) {
			if (!doc.reference_doctype) {
				return {};
			}

			return {
				filters: {
					docstatus: 1,
					outstanding_amount: [">", 0]
				}
			};
		});
	},

	reference_doctype(frm) {
		frm.set_value("reference_name", null);
	},

	reference_name(frm) {
		if (!frm.doc.reference_doctype || !frm.doc.reference_name) {
			return;
		}

		frappe.db.get_doc(frm.doc.reference_doctype, frm.doc.reference_name).then((ref) => {
			if (frm.doc.reference_doctype === "Sales Invoice") {
				frm.set_value("payment_type", "Receive");
				frm.set_value("party_type", "Customer");
				frm.set_value("party", ref.customer);
			} else if (frm.doc.reference_doctype === "Purchase Invoice") {
				frm.set_value("payment_type", "Pay");
				frm.set_value("party_type", "Supplier");
				frm.set_value("party", ref.supplier);
			}

			frm.set_value("currency", ref.currency);
			if (!frm.doc.paid_amount || frm.doc.paid_amount <= 0) {
				frm.set_value("paid_amount", ref.outstanding_amount);
			}
			if (!frm.doc.remarks) {
				frm.set_value(
					"remarks",
					`${frm.doc.payment_type} against ${frm.doc.reference_doctype} ${frm.doc.reference_name}`
				);
			}
		});
	},

	refresh(frm) {
		if (frm.doc.reference_doctype && frm.doc.reference_name) {
			frm.add_custom_button(__("Open Reference"), () => {
				frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
			}, __("View"));
		}
	}
});
