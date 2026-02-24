// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.treeview_settings["Account"] = {
	breadcrumb: "Finance",
	title: __("Chart of Accounts"),
	get_tree_root: true,
	root_label: "All Accounts",
	ignore_fields: ["parent_account"],

	// Custom server method returns account_number, account_type, balance_type, balance
	get_tree_nodes: "vsd_fleet_ms.vsd_fleet_ms.doctype.account.account.get_children",

	onrender: function (node) {
		var data = node.data;
		if (!data || !data.value) return;

		var $link = node.$tree_link;
		var $label = $link.find(".tree-label");

		// Make the row a flex container so margin-left:auto can push balance right
		$link.css({ "display": "flex", "align-items": "center", "width": "100%" });

		// ── 1. Account number — monospace prefix, inserted before the label ───
		if (data.account_number) {
			$('<span class="text-muted small">')
				.css({ "margin-right": "6px", "font-family": "monospace", "flex-shrink": "0" })
				.text(data.account_number)
				.insertBefore($label);
		}

		// ── 2. Account type — Frappe's indicator-pill (same classes as List) ──
		var type_color = {
			"Asset":     "blue",
			"Liability": "red",
			"Income":    "green",
			"Expense":   "orange",
			"Equity":    "purple",
		};
		if (data.account_type) {
			var color = type_color[data.account_type] || "gray";
			$('<span class="indicator-pill no-indicator-dot ' + color + '">')
				.text(__(data.account_type))
				.css({ "margin-left": "8px", "flex-shrink": "0" })
				.appendTo($link);
		}

		// ── 3. Balance — format_currency() returns plain text (no HTML markup)
		//    margin-left:auto pushes it to the far right regardless of content width.
		var bal = parseFloat(data.balance) || 0;
		if (Math.abs(bal) >= 0.005) {
			var dr_or_cr = bal > 0 ? __("Dr") : __("Cr");
			var currency = frappe.boot.sysdefaults.currency || "TZS";
			var formatted = format_currency(Math.abs(bal), currency);

			$('<span class="balance-area">')
				.css({ "margin-left": "auto", "padding-left": "16px", "white-space": "nowrap", "flex-shrink": "0" })
				.text(formatted + " " + dr_or_cr)
				.appendTo($link);
		}
	},

	toolbar: [
		{
			label: __("Add Child Account"),
			condition: function (node) {
				return node.expandable && node.label !== "All Accounts";
			},
			click: function (node) {
				frappe.new_doc("Account", { parent_account: node.label });
			},
			btnClass: "hidden-xs",
		},
		{
			label: __("Edit"),
			condition: function (node) {
				return !node.expandable || node.label !== "All Accounts";
			},
			click: function (node) {
				frappe.set_route("Form", "Account", node.label);
			},
		},
	],

	extend_toolbar: true,
};
