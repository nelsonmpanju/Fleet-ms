from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate, nowtime

from vsd_fleet_ms.utils.inventory import post_stock_entry


class StockEntry(Document):
    def autoname(self):
        self.name = make_autoname("STE-.#####")

    def validate(self):
        self.set_defaults()
        self.validate_rows()

    def on_submit(self):
        post_stock_entry(self, is_cancel=False)

    def on_cancel(self):
        post_stock_entry(self, is_cancel=True)

    def set_defaults(self):
        if not self.posting_date:
            self.posting_date = nowdate()
        if not self.posting_time:
            self.posting_time = nowtime()

    def validate_rows(self):
        for row in self.items:
            row.qty = flt(row.qty)
            row.basic_rate = flt(getattr(row, "basic_rate", 0))
            if not row.basic_rate:
                row.basic_rate = flt(frappe.db.get_value("Item", row.item_code, "standard_rate"))
            row.amount = row.qty * row.basic_rate

            if self.stock_entry_type == "Material Issue":
                if not (row.s_warehouse or self.from_warehouse):
                    frappe.throw(f"Source Warehouse is required in row {row.idx}")
            elif self.stock_entry_type == "Material Receipt":
                if not (row.t_warehouse or self.to_warehouse):
                    frappe.throw(f"Target Warehouse is required in row {row.idx}")
            else:
                if not (row.s_warehouse or self.from_warehouse):
                    frappe.throw(f"Source Warehouse is required in row {row.idx}")
                if not (row.t_warehouse or self.to_warehouse):
                    frappe.throw(f"Target Warehouse is required in row {row.idx}")
