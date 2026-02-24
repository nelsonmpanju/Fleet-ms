import frappe
from frappe.utils.nestedset import NestedSet


class Warehouse(NestedSet):
    nsm_parent_field = "parent_warehouse"

    def autoname(self):
        # Keep tree nodes human-readable while enforcing uniqueness.
        if not self.warehouse_name:
            frappe.throw("Warehouse Name is required")
        self.name = self.warehouse_name
