# Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from operator import mul
import frappe
import time
import datetime
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
import json
from frappe.utils import nowdate, cstr, cint, flt, comma_or, now
from frappe import _, msgprint
from vsd_fleet_ms.utils.dimension import set_dimension
from vsd_fleet_ms.vsd_fleet_ms.doctype.requested_payment.requested_payment import request_funds

class CargoRegistration(Document):
    def before_save(self):
        if self.get('requested_fund'):
            for row in self.get('requested_fund'):
                if row.request_status == "Requested":
                    funds_args = {
                        "reference_doctype": 'Cargo Registration',
                        "reference_docname": self.name,
                    }
                    request_funds(**funds_args)
                    break 



@frappe.whitelist()
def create_sales_invoice(doc, rows):
    doc = frappe.get_doc(json.loads(doc))
    rows = json.loads(rows)
    if not rows:
        return

    selected_names = []
    for row in rows:
        if isinstance(row, dict):
            selected_names.append(row.get("name"))
        else:
            selected_names.append(row)
    selected_names = [name for name in selected_names if name]
    if not selected_names:
        frappe.throw(_("Please select at least one cargo row to invoice."))

    selected_rows = [row for row in doc.cargo_details if row.name in selected_names]
    if not selected_rows:
        frappe.throw(_("Selected cargo rows were not found in this document."))

    already_invoiced = [row.name for row in selected_rows if row.invoice]
    if already_invoiced:
        frappe.throw(_("Some selected rows already have Sales Invoice: {0}").format(", ".join(already_invoiced)))

    default_currency = (
        frappe.db.get_value("Customer", doc.customer, "default_currency")
        or frappe.db.get_value("Currency", {"enabled": 1}, "name")
        or "USD"
    )

    row_currency = None
    item_row_pairs = []
    for row in selected_rows:
        if not row.service_item:
            frappe.throw(_("Service Item is required for row {0}.").format(row.idx))

        currency = row.currency or default_currency
        if row_currency and currency != row_currency:
            frappe.throw(_("All selected rows must have the same currency."))
        row_currency = currency

        if cint(row.allow_bill_on_weight):
            # Bill by weight: use net_weight_tonne as qty and bill_uom
            if not row.bill_uom:
                frappe.throw(_("Bill UOM is required for row {0} when billing by weight.").format(row.idx))
            qty = flt(row.net_weight_tonne)
            uom = row.bill_uom
        else:
            # Bill per item: qty = 1, use item's stock UOM
            qty = 1
            uom = frappe.db.get_value("Item", row.service_item, "stock_uom") or "Nos"

        if qty <= 0:
            frappe.throw(_("Quantity must be greater than zero for row {0}.").format(row.idx))

        description = ""
        if row.transporter_type == "In House":
            if row.assigned_truck:
                description += "<b>VEHICLE NUMBER: {0}</b>".format(cstr(row.assigned_truck))
            if row.created_trip:
                description += "<br><b>TRIP: {0}</b>".format(cstr(row.created_trip))
        elif row.transporter_type == "Sub-Contractor":
            if row.truck_number:
                description += "<b>VEHICLE NUMBER: {0}</b>".format(cstr(row.truck_number))
            if row.driver_name:
                description += "<br><b>DRIVER NAME: {0}</b>".format(cstr(row.driver_name))

        if row.cargo_route:
            description += "<br>ROUTE: {0}".format(cstr(row.cargo_route))

        item = frappe._dict(
            {
                "item_code": row.service_item,
                "qty": qty,
                "uom": uom,
                "rate": flt(row.rate),
                "description": description,
                "cargo_id": row.name,
                "truck": row.assigned_truck,
                "driver": row.assigned_driver,
                "reference_trip": row.created_trip,
            }
        )
        item_row_pairs.append((row, item))

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = doc.customer
    invoice.currency = row_currency or default_currency
    invoice.posting_date = nowdate()
    invoice.due_date = invoice.posting_date

    set_dimension(doc, invoice)
    for source_row, target_item in item_row_pairs:
        set_dimension(doc, invoice, src_child=source_row, tr_child=target_item)
        invoice.append("items", target_item)

    invoice.insert(ignore_permissions=True)

    for row in selected_rows:
        frappe.db.set_value("Cargo Detail", row.name, "invoice", invoice.name)

    frappe.msgprint(_("Sales Invoice {0} Created").format(invoice.name), alert=True)
    return invoice
