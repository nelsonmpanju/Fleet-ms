frappe.treeview_settings["Warehouse"] = {
	breadcrumb: "Stock",
	title: __("Warehouses"),
	get_tree_root: true,
	root_label: __("All Warehouses"),
	ignore_fields: ["parent_warehouse"],
	onrender: function (node) {
		if (node.data && node.data.disabled) {
			node.$tree_link.addClass("text-muted");
		}
	}
};
