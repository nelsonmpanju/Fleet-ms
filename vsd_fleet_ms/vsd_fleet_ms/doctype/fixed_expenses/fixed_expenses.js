// Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fixed Expenses', {
	onload: function (frm) {
		frappe.call({
			method: "vsd_fleet_ms.vsd_fleet_ms.doctype.fixed_expenses.fixed_expenses.expense_account",
			callback: function(response) {
				var expenseAccounts = response.message || [];
				frm.set_query("expense_account", function(doc) {
					var filters = [
						["Account", "is_group", "=", 0]
					];
					if (expenseAccounts.length > 0) {
						filters.push(["Account", "parent_account", "in", expenseAccounts]);
					}
					return { filters: filters };
				});
			}
		});
		frappe.call({
			method: "vsd_fleet_ms.vsd_fleet_ms.doctype.fixed_expenses.fixed_expenses.cash_account",
			callback: function(response) {
				var cash_bank_account = response.message || [];
				frm.set_query("cash_bank_account", function(doc) {
					var filters = [
						["Account", "is_group", "=", 0]
					];
					if (cash_bank_account.length > 0) {
						filters.push(["Account", "parent_account", "in", cash_bank_account]);
					}
					return { filters: filters };
				});
			}
		});
	},
	refresh: function(frm) {
		apply_value_color(frm);
	},
	expense_account: function(frm) {
		// Update color when account changes
		apply_value_color(frm);
	}
});

function apply_value_color(frm) {
	if (!frm.doc.expense_account) return;
	frappe.db.get_value("Account", frm.doc.expense_account, "account_type").then(r => {
		if (!r || !r.message) return;
		var account_type = r.message.account_type;
		var color = "";
		if (account_type === "Income") {
			color = "green";
		} else if (account_type === "Expense") {
			color = "red";
		}
		if (color) {
			frm.get_field("fixed_value").$wrapper
				.find(".control-value, .like-disabled-input, input")
				.css({"color": color, "font-weight": "bold"});
		}
	});
}
