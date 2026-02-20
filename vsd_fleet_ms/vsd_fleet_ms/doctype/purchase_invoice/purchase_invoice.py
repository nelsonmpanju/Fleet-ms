from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate

from vsd_fleet_ms.utils.inventory import post_purchase_invoice_stock


class PurchaseInvoice(Document):
    def autoname(self):
        self.name = make_autoname(self.naming_series or "PINV-.#####")

    def validate(self):
        self.set_defaults()
        self.calculate_totals()
        self.validate_stock_rows()

    def on_submit(self):
        self.db_set("status", "Paid" if self.payment_status == "Paid" else "Submitted")
        post_purchase_invoice_stock(self, is_cancel=False)

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        post_purchase_invoice_stock(self, is_cancel=True)

    def set_defaults(self):
        if not self.posting_date:
            self.posting_date = nowdate()
        if not self.due_date:
            self.due_date = self.posting_date
        if not self.currency:
            self.currency = frappe.db.get_value("Currency", {"enabled": 1}, "name")
        if not self.conversion_rate:
            self.conversion_rate = 1

    def calculate_totals(self):
        total = 0
        line_discount_total = 0
        line_tax_total = 0

        for row in self.items:
            row.qty = flt(row.qty)
            row.rate = flt(row.rate)
            row.amount = row.qty * row.rate

            if flt(row.discount_percentage) and not flt(row.discount_amount):
                row.discount_amount = row.amount * flt(row.discount_percentage) / 100
            else:
                row.discount_amount = flt(row.discount_amount)

            taxable_line = row.amount - row.discount_amount
            row.tax_amount = taxable_line * flt(row.tax_rate) / 100
            row.net_amount = taxable_line + row.tax_amount

            total += row.amount
            line_discount_total += row.discount_amount
            line_tax_total += row.tax_amount

        header_discount = flt(self.discount_amount)
        header_tax = flt(self.tax_amount)
        total_discount = line_discount_total + header_discount

        self.total = total
        self.taxable_amount = total - total_discount
        self.tax_amount = line_tax_total + header_tax
        self.grand_total = self.taxable_amount + self.tax_amount

        if flt(self.is_paid):
            self.paid_amount = self.grand_total
            self.outstanding_amount = 0
            self.payment_status = "Paid"
        else:
            self.outstanding_amount = self.grand_total - flt(self.paid_amount)
            if self.outstanding_amount <= 0:
                self.outstanding_amount = 0
                self.payment_status = "Paid"
            elif flt(self.paid_amount) > 0:
                self.payment_status = "Partly Paid"
            else:
                self.payment_status = "Unpaid"

        if self.payment_status == "Paid" and self.docstatus == 1:
            self.status = "Paid"
        elif self.docstatus == 1:
            self.status = "Submitted"
        elif self.docstatus == 2:
            self.status = "Cancelled"

    def validate_stock_rows(self):
        for row in self.items:
            is_stock_item = frappe.db.get_value("Item", row.item_code, "is_stock_item")
            if not is_stock_item:
                continue
            if not row.warehouse:
                row.warehouse = self.get("set_warehouse")
            if not row.warehouse:
                frappe.throw(
                    f"Warehouse is required for stock item {row.item_code} in row {row.idx}."
                )
