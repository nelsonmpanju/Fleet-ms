from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate

from vsd_fleet_ms.utils.inventory import post_purchase_invoice_stock


def _get_expense_account_for_type(invoice_type: str) -> str | None:
    """Return a default expense account based on invoice_type from Transport Settings."""
    if invoice_type == "Fuel":
        return frappe.db.get_single_value("Transport Settings", "fuel_expense_account") or None
    return None


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
        self.create_expense_ledger_entry()

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        post_purchase_invoice_stock(self, is_cancel=True)
        self.cancel_linked_ledger_entry()

    def set_defaults(self):
        if not self.posting_date:
            self.posting_date = nowdate()
        if not self.due_date:
            self.due_date = self.posting_date
        if not self.currency:
            self.currency = frappe.db.get_value("Currency", {"enabled": 1}, "name")
        if not self.conversion_rate:
            self.conversion_rate = 1
        # Auto-fill payable account from Supplier, then Transport Settings
        if not self.payable_account and self.supplier:
            self.payable_account = frappe.db.get_value(
                "Supplier", self.supplier, "payable_account"
            ) or None
        if not self.payable_account:
            self.payable_account = frappe.db.get_single_value(
                "Transport Settings", "default_payable_account"
            ) or None
        # Auto-fill expense account from Transport Settings based on invoice_type
        if not self.expense_account and self.invoice_type:
            self.expense_account = _get_expense_account_for_type(self.invoice_type) or None

    def create_expense_ledger_entry(self):
        amount = flt(self.grand_total)
        if amount <= 0:
            return

        # Reuse existing ledger entry if one was already created
        if self.ledger_entry and frappe.db.exists("Ledger Entry", self.ledger_entry):
            existing = frappe.get_doc("Ledger Entry", self.ledger_entry)
            if existing.docstatus == 1:
                return
            if existing.docstatus == 0:
                existing.submit()
                return
            self.db_set("ledger_entry", "", update_modified=False)

        expense_account = self.expense_account
        if not expense_account:
            # Last-resort auto-detect by invoice_type
            expense_account = _get_expense_account_for_type(self.invoice_type or "")
        if not expense_account:
            frappe.throw(
                "Expense Account is required to post GL entries for this Purchase Invoice. "
                "Please set an Expense Account on the invoice or configure the default in Transport Settings."
            )

        # Payable / Creditors account
        payable_account = self.payable_account
        if not payable_account:
            payable_account = frappe.db.get_single_value(
                "Transport Settings", "default_payable_account"
            )
        if not payable_account:
            payable_account = frappe.db.get_value(
                "Account", {"account_name": "Accounts Payable", "is_group": 0}, "name"
            ) or frappe.db.get_value(
                "Account", {"account_type": "Payable", "is_group": 0}, "name"
            )
        if not payable_account:
            frappe.throw(
                "Payable Account not found. Please set a Payable Account on the Supplier record "
                "or set a Default Payable Account in Transport Settings."
            )

        ledger_doc = frappe.get_doc(
            {
                "doctype": "Ledger Entry",
                "posting_date": self.posting_date,
                "entry_type": "Expense",
                "source_type": "Purchase Invoice",
                # DR Expense / CR Payable
                "account": expense_account,
                "contra_account": payable_account,
                "party_type": "Supplier",
                "party": self.supplier,
                "currency": self.currency,
                "amount": amount,
                "reference_doctype": "Purchase Invoice",
                "reference_name": self.name,
                "reference_trip": self.reference_trip,
                "description": f"Purchase Invoice {self.name}",
                "remarks": self.remarks or f"Auto ledger booking for Purchase Invoice {self.name}",
            }
        )
        ledger_doc.flags.ignore_permissions = True
        ledger_doc.insert(ignore_permissions=True)
        ledger_doc.submit()
        self.db_set("ledger_entry", ledger_doc.name, update_modified=False)

    def cancel_linked_ledger_entry(self):
        if not self.ledger_entry:
            return
        if not frappe.db.exists("Ledger Entry", self.ledger_entry):
            self.db_set("ledger_entry", "", update_modified=False)
            return

        ledger_doc = frappe.get_doc("Ledger Entry", self.ledger_entry)
        ledger_doc.flags.ignore_permissions = True
        if ledger_doc.docstatus == 1:
            ledger_doc.cancel()

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

        grand_total = flt(self.grand_total)

        if flt(self.is_paid) and grand_total > 0:
            # "Fully Paid" checkbox — only valid when there is an actual amount
            self.paid_amount = grand_total
            self.outstanding_amount = 0
            self.payment_status = "Paid"
        else:
            self.outstanding_amount = grand_total - flt(self.paid_amount)
            # Only mark as "Paid" when there is a real amount and it has been covered
            if grand_total > 0 and self.outstanding_amount <= 0:
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
