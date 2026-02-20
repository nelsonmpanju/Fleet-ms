frappe.listview_settings['Fixed Expenses'] = {
	onload: function(listview) {
		// After list renders, color the fixed_value based on account type
		listview.page.wrapper.on('render-complete', function() {
			apply_list_colors(listview);
		});
	},
	refresh: function(listview) {
		apply_list_colors(listview);
	}
};

function apply_list_colors(listview) {
	// Fetch account types for all visible expense accounts
	var accounts = [];
	(listview.data || []).forEach(function(d) {
		if (d.expense_account && accounts.indexOf(d.expense_account) === -1) {
			accounts.push(d.expense_account);
		}
	});
	if (!accounts.length) return;

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Account",
			filters: { name: ["in", accounts] },
			fields: ["name", "account_type"],
			limit_page_length: 0
		},
		async: false,
		callback: function(r) {
			if (!r.message) return;
			var account_map = {};
			r.message.forEach(function(a) {
				account_map[a.name] = a.account_type;
			});
			listview.$result.find('.list-row').each(function() {
				var $row = $(this);
				var name = $row.data('name');
				var row_data = (listview.data || []).find(function(d) { return d.name === name; });
				if (row_data && row_data.expense_account) {
					var acc_type = account_map[row_data.expense_account];
					var color = acc_type === "Income" ? "green" : (acc_type === "Expense" ? "red" : "");
					if (color) {
						$row.find('.list-row-col[data-field="fixed_value"]').css({
							"color": color,
							"font-weight": "bold"
						});
					}
				}
			});
		}
	});
}
