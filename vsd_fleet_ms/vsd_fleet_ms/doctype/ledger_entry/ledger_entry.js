frappe.ui.form.on("Ledger Entry", {
	setup(frm) {
		frm.set_query("account", function () {
			const filters = { is_group: 0 };
			if (frm.doc.entry_type === "Income") {
				filters.account_type = "Income";
			} else if (frm.doc.entry_type === "Expense") {
				filters.account_type = "Expense";
			}
			return { filters };
		});

		frm.set_query("reference_trip_expense", function () {
			if (!frm.doc.reference_trip) {
				return { filters: { name: "" } };
			}
			return {
				filters: {
					parenttype: "Trips",
					parent: frm.doc.reference_trip,
					request_status: "Approved",
				},
			};
		});
	},
});
