from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate

from vsd_fleet_ms.vsd_fleet_ms.doctype.account.account import ensure_posting_account
from vsd_fleet_ms.utils.accounting import get_company_currency, get_exchange_rate


def _get_sales_settings():
    """Return (default_income_account, default_receivable_account) from Transport Settings."""
    s = frappe.get_single("Transport Settings")
    return s.default_income_account or None, s.default_receivable_account or None


class SalesInvoice(Document):
    def autoname(self):
        self.name = make_autoname(self.naming_series or "SI-.#####")

    def validate(self):
        self.set_defaults()
        self.set_income_accounts()
        self.validate_income_account()
        self.calculate_totals()

    def on_submit(self):
        self.link_trip_from_cargo()
        self.create_income_ledger_entry()
        self.db_set("status", "Paid" if self.payment_status == "Paid" else "Submitted")

    def link_trip_from_cargo(self):
        """Auto-fill reference_trip from linked Cargo Detail rows if not already set."""
        if self.reference_trip:
            return
        # Find cargo rows that reference this invoice and have a trip
        trip = frappe.db.get_value(
            "Cargo Detail",
            {"invoice": self.name, "created_trip": ["is", "set"]},
            "created_trip",
        )
        if trip:
            self.reference_trip = trip
            self.db_set("reference_trip", trip, update_modified=False)

    def on_cancel(self):
        self.cancel_linked_ledger_entry()
        self.db_set("status", "Cancelled")

    def set_defaults(self):
        if not self.posting_date:
            self.posting_date = nowdate()
        if not self.due_date:
            self.due_date = self.posting_date
        if not self.currency:
            self.currency = get_company_currency()
        self.conversion_rate = get_exchange_rate(
            self.currency, get_company_currency(), self.posting_date
        )
        # Auto-fill receivable account from Customer, then Transport Settings
        if not self.receivable_account and self.customer:
            self.receivable_account = frappe.db.get_value(
                "Customer", self.customer, "receivable_account"
            ) or None
        if not self.receivable_account:
            _, default_recv = _get_sales_settings()
            self.receivable_account = default_recv or None

    def set_income_accounts(self):
        default_income_account = self.income_account or self.get_default_income_account()

        for row in self.items:
            if not row.income_account and row.item_code:
                row.income_account = frappe.db.get_value("Item", row.item_code, "income_account")

            # Fall back to the invoice-level default so every row is always filled
            if not row.income_account:
                row.income_account = default_income_account

            if not row.income_account:
                frappe.throw(f"Income Account is required for row {row.idx}.")

        if self.items and not self.income_account:
            self.income_account = self.items[0].income_account

        for row in self.items:
            if row.income_account != self.income_account:
                frappe.throw(
                    "All Sales Invoice rows must use the same Income Account as the invoice header."
                )

    def get_default_income_account(self):
        # 1. Check Transport Settings first — explicit system-wide default
        default_income, _ = _get_sales_settings()
        if default_income:
            return default_income

        # 2. Fall back to first non-group Income account in the CoA
        fallback = frappe.db.get_value(
            "Account", {"account_type": "Income", "is_group": 0}, "name"
        )
        if not fallback:
            frappe.throw(
                "No Income Account found. Please set a Default Income Account in "
                "Transport Settings or create a non-group Income account."
            )
        return fallback

    def validate_income_account(self):
        if not self.income_account:
            frappe.throw("Income Account is required.")

        details = ensure_posting_account(self.income_account, "Income Account")
        if details.get("account_type") != "Income":
            frappe.throw(
                f"Income Account {self.income_account} must have Account Type Income."
            )

    def create_income_ledger_entry(self):
        amount = flt(self.grand_total)
        if amount <= 0:
            return

        if self.ledger_entry and frappe.db.exists("Ledger Entry", self.ledger_entry):
            existing = frappe.get_doc("Ledger Entry", self.ledger_entry)
            if existing.docstatus == 1:
                return
            if existing.docstatus == 0:
                existing.submit()
                return
            self.db_set("ledger_entry", "", update_modified=False)

        # Contra account = Accounts Receivable / Debtors (DR when invoice is raised)
        # Priority: invoice field (set from customer) → Transport Settings → auto-detect
        receivable_account = self.receivable_account
        if not receivable_account:
            _, receivable_account = _get_sales_settings()
        if not receivable_account:
            receivable_account = (
                frappe.db.get_value(
                    "Account",
                    {"account_name": "Accounts Receivable", "is_group": 0},
                    "name",
                )
                or frappe.db.get_value(
                    "Account", {"account_type": "Receivable", "is_group": 0}, "name"
                )
            )
        if not receivable_account:
            frappe.throw(
                "Receivable Account not found. Please set a Receivable Account on the "
                "Customer record or set a Default Receivable Account in Transport Settings."
            )

        ledger_doc = frappe.get_doc(
            {
                "doctype": "Ledger Entry",
                "posting_date": self.posting_date,
                "entry_type": "Income",
                "source_type": "Sales Invoice",
                "account": self.income_account,
                # contra_account is the AR account — DR AR / CR Income
                "contra_account": receivable_account,
                "party_type": "Customer",
                "party": self.customer,
                "currency": self.currency,
                "conversion_rate": flt(self.conversion_rate) or 1,
                "amount": amount,
                "reference_doctype": "Sales Invoice",
                "reference_name": self.name,
                "reference_trip": self.reference_trip,
                "description": f"Sales Invoice {self.name}",
                "remarks": self.remarks or f"Auto ledger booking for Sales Invoice {self.name}",
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
        self.base_grand_total = flt(self.grand_total) * (flt(self.conversion_rate) or 1)

        grand_total = flt(self.grand_total)

        if flt(self.is_paid) and grand_total > 0:
            self.paid_amount = grand_total
            self.outstanding_amount = 0
            self.payment_status = "Paid"
        else:
            self.outstanding_amount = grand_total - flt(self.paid_amount)
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


@frappe.whitelist()
def get_sales_invoice_defaults():
    """Return default income + receivable accounts for new Sales Invoices."""
    income, receivable = _get_sales_settings()
    return {"income_account": income, "receivable_account": receivable}
