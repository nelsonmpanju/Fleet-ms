frappe.ui.form.on("Exchange Rate", {
    setup(frm) {
        frm.set_query("to_currency", function () {
            return {
                filters: {
                    name: ["!=", frm.doc.from_currency],
                },
            };
        });
    },
});
