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

		if (frm.doc.reference_doctype === "Requested Payment") {
			// Auto-fill trip link
			frappe.db.get_value("Requested Payment", frm.doc.reference_name,
				["reference_doctype", "reference_docname", "truck_driver"])
				.then((r) => {
					if (r.message && r.message.reference_doctype === "Trips") {
						frm.set_value("trip", r.message.reference_docname);
					}
				});
			if (!frm.doc.remarks) {
				frm.set_value("remarks", `Payment against ${frm.doc.reference_name}`);
			}
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

		if (frm.doc.trip) {
			frm.add_custom_button(__("Open Trip"), () => {
				frappe.set_route("Form", "Trips", frm.doc.trip);
			}, __("View"));
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("View Ledger"), () => {
				frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "GL Entry",
						filters: { voucher_type: "Payment Entry", voucher_no: frm.doc.name },
						fields: ["posting_date", "account", "party", "debit", "credit"],
						order_by: "posting_date asc",
						limit_page_length: 50,
					},
					callback: function(r) {
						if (!r.message || !r.message.length) {
							frappe.msgprint(__("No GL entries found for this Payment Entry."));
							return;
						}
						var html = '<table class="table table-bordered" style="font-size:12px"><thead>'
							+ '<tr><th>Date</th><th>Account</th><th>Party</th>'
							+ '<th class="text-right">Debit</th><th class="text-right">Credit</th></tr>'
							+ '</thead><tbody>';
						r.message.forEach(function(e) {
							html += '<tr><td>' + e.posting_date + '</td><td>' + e.account + '</td>'
								+ '<td>' + (e.party || '') + '</td>'
								+ '<td class="text-right">' + (e.debit > 0 ? e.debit.toLocaleString() : '') + '</td>'
								+ '<td class="text-right">' + (e.credit > 0 ? e.credit.toLocaleString() : '') + '</td>'
								+ '</tr>';
						});
						html += '</tbody></table>';
						new frappe.ui.Dialog({
							title: __("GL Entries — {0}", [frm.doc.name]),
							fields: [{ fieldtype: "HTML", fieldname: "gl", options: html }],
							size: "large",
						}).show();
					},
				});
			}, __("View"));
		}
	}
});
