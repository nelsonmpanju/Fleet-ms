from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate


INVOICE_CONFIG = {
    "Sales Invoice": {
        "party_field": "customer",
        "party_type": "Customer",
        "payment_type": "Receive",
    },
    "Purchase Invoice": {
        "party_field": "supplier",
        "party_type": "Supplier",
        "payment_type": "Pay",
    },
}


class PaymentEntry(Document):
    def autoname(self):
        self.name = make_autoname("PE-.#####")

    def validate(self):
        self.set_defaults()
        self.validate_reference()
        self.validate_amount()

    def on_submit(self):
        self.apply_against_reference(is_cancel=False)
        self.db_set("status", "Submitted")

    def on_cancel(self):
        self.apply_against_reference(is_cancel=True)
        self.db_set("status", "Cancelled")

    def set_defaults(self):
        if not self.posting_date:
            self.posting_date = nowdate()
        if not self.status:
            self.status = "Draft"
        if not self.currency:
            self.currency = frappe.db.get_value("Currency", {"enabled": 1}, "name") or "USD"
        self.paid_amount = flt(self.paid_amount)

    def validate_amount(self):
        if flt(self.paid_amount) <= 0:
            frappe.throw("Paid Amount must be greater than zero.")

    def validate_reference(self):
        if bool(self.reference_doctype) != bool(self.reference_name):
            frappe.throw("Reference DocType and Reference Document must both be set.")

        if not self.reference_doctype:
            return

        config = INVOICE_CONFIG.get(self.reference_doctype)
        if not config:
            frappe.throw("Reference DocType must be either Sales Invoice or Purchase Invoice.")

        self.payment_type = config["payment_type"]
        self.party_type = config["party_type"]

        reference = frappe.db.get_value(
            self.reference_doctype,
            self.reference_name,
            [config["party_field"], "currency", "docstatus", "outstanding_amount"],
            as_dict=True,
        )
        if not reference:
            frappe.throw(f"{self.reference_doctype} {self.reference_name} was not found.")
        if cint(reference.docstatus) != 1:
            frappe.throw(f"{self.reference_doctype} {self.reference_name} must be submitted first.")

        reference_party = reference.get(config["party_field"])
        if self.party and self.party != reference_party:
            frappe.throw("Party does not match the selected reference document.")
        self.party = reference_party
        if reference.get("currency"):
            self.currency = reference.currency

        outstanding = flt(reference.outstanding_amount)
        if outstanding <= 0:
            frappe.throw(f"{self.reference_doctype} {self.reference_name} is already fully paid.")
        if flt(self.paid_amount) <= 0:
            self.paid_amount = outstanding
        if flt(self.paid_amount) - outstanding > 1e-9:
            frappe.throw(
                f"Paid Amount cannot exceed outstanding amount ({outstanding}) on "
                f"{self.reference_doctype} {self.reference_name}."
            )

    def apply_against_reference(self, is_cancel: bool):
        if not self.reference_doctype or not self.reference_name:
            return

        invoice = frappe.db.get_value(
            self.reference_doctype,
            self.reference_name,
            ["docstatus", "grand_total", "paid_amount", "outstanding_amount"],
            as_dict=True,
        )
        if not invoice:
            frappe.throw(f"{self.reference_doctype} {self.reference_name} was not found.")

        if cint(invoice.docstatus) != 1 and not is_cancel:
            frappe.throw(f"{self.reference_doctype} {self.reference_name} must be submitted first.")

        delta = flt(self.paid_amount) * (-1 if is_cancel else 1)
        current_paid = flt(invoice.paid_amount)
        grand_total = flt(invoice.grand_total)
        current_outstanding = flt(invoice.outstanding_amount)
        if current_outstanding < 0:
            current_outstanding = max(grand_total - current_paid, 0)

        if not is_cancel and delta - current_outstanding > 1e-9:
            frappe.throw(
                f"Paid Amount cannot exceed outstanding amount ({current_outstanding}) on "
                f"{self.reference_doctype} {self.reference_name}."
            )

        new_paid = current_paid + delta
        if new_paid < -1e-9:
            frappe.throw(
                f"Cannot cancel payment because it would make paid amount negative for "
                f"{self.reference_doctype} {self.reference_name}."
            )
        new_paid = max(new_paid, 0)
        new_outstanding = max(grand_total - new_paid, 0)

        if new_outstanding <= 1e-9:
            new_outstanding = 0
            payment_status = "Paid"
            is_paid = 1
        elif new_paid > 0:
            payment_status = "Partly Paid"
            is_paid = 0
        else:
            payment_status = "Unpaid"
            is_paid = 0

        invoice_status = "Paid" if payment_status == "Paid" and cint(invoice.docstatus) == 1 else "Submitted"

        frappe.db.set_value(
            self.reference_doctype,
            self.reference_name,
            {
                "paid_amount": new_paid,
                "outstanding_amount": new_outstanding,
                "payment_status": payment_status,
                "status": invoice_status,
                "is_paid": is_paid,
            },
            update_modified=False,
        )


@frappe.whitelist()
def create_payment_entry_for_sales_invoice(sales_invoice: str) -> str:
    return _create_payment_entry_for_invoice("Sales Invoice", sales_invoice)


@frappe.whitelist()
def create_payment_entry_for_purchase_invoice(purchase_invoice: str) -> str:
    return _create_payment_entry_for_invoice("Purchase Invoice", purchase_invoice)


def _create_payment_entry_for_invoice(reference_doctype: str, reference_name: str) -> str:
    config = INVOICE_CONFIG[reference_doctype]
    reference = frappe.db.get_value(
        reference_doctype,
        reference_name,
        [config["party_field"], "currency", "docstatus", "outstanding_amount"],
        as_dict=True,
    )
    if not reference:
        frappe.throw(f"{reference_doctype} {reference_name} was not found.")
    if cint(reference.docstatus) != 1:
        frappe.throw(f"{reference_doctype} {reference_name} must be submitted first.")

    outstanding = flt(reference.outstanding_amount)
    if outstanding <= 0:
        frappe.throw(f"{reference_doctype} {reference_name} is already fully paid.")

    payment_entry = frappe.new_doc("Payment Entry")
    payment_entry.payment_type = config["payment_type"]
    payment_entry.posting_date = nowdate()
    payment_entry.mode_of_payment = "Cash"
    payment_entry.party_type = config["party_type"]
    payment_entry.party = reference.get(config["party_field"])
    payment_entry.currency = reference.currency
    payment_entry.allocate_payment_amount = 1
    payment_entry.paid_amount = outstanding
    payment_entry.reference_doctype = reference_doctype
    payment_entry.reference_name = reference_name
    payment_entry.remarks = f"{config['payment_type']} against {reference_doctype} {reference_name}"
    payment_entry.insert(ignore_permissions=True)
    return payment_entry.name


def cint(value) -> int:
    return int(flt(value))
