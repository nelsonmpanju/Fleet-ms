# Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
import datetime
import json
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import nowdate, nowtime, cstr, cint, flt, now
from frappe import _, msgprint
from vsd_fleet_ms.utils.dimension import set_dimension
from vsd_fleet_ms.utils.accounting import get_exchange_rate
from vsd_fleet_ms.vsd_fleet_ms.doctype.requested_payment.requested_payment import request_funds


class Trips(Document):
    def before_submit(self):
        self.set_driver()
        self.validate_request_status()

    def on_submit(self):
        if self.transporter_type == "In House":
            # Only require stock_out_entry if fuel source is From Inventory
            if self.fuel_source_type == "From Inventory" and not self.stock_out_entry:
                frappe.throw(_("Stock Out Entry is required when fuel source is From Inventory"))

    def onload(self):
        if not self.fuel_stock_out:
            self.fuel_stock_out = self.total_fuel

    def before_insert(self):
        self.set_route_steps()
        if self.transporter_type == "In House":
            self.set_fuel_stock()
            self.set_expenses()
        elif self.transporter_type == "Sub-Contractor":
            self.requested_fund_accounts_table = []

    def validate(self):
        if self.transporter_type == "In House":
            if self.fuel_source_type == "From Inventory":
                self.ensure_inventory_fuel_row()
            self.validate_fuel_requests()

    def on_update(self):
        """Update Round Trip when trip is modified"""
        if self.round_trip and not self.flags.ignore_round_trip_update:
            self.update_round_trip()

    def update_round_trip(self):
        """Update Round Trip child table with latest trip data"""
        try:
            round_trip = frappe.get_doc("Round Trip", self.round_trip)
            for trip_row in round_trip.trip_details:
                if trip_row.trip_id == self.name:
                    trip_row.trip_driver = self.driver_name
                    trip_row.trip_start_date = self.date
                    trip_row.trip_end_date = self.trip_completed_date
                    break

            round_trip.update_status()
            round_trip.flags.ignore_round_trip_update = True
            round_trip.save()
        except Exception as e:
            frappe.log_error(f"Error updating Round Trip {self.round_trip}: {str(e)}")

    def set_fuel_stock(self):
        self.fuel_stock_out = self.total_fuel

    def set_route_steps(self):
        reference_route = frappe.get_doc("Trip Routes", self.route)
        if len(reference_route.trip_steps) > 0:
            self.main_route_steps = []
            for row in reference_route.trip_steps:
                new_row = self.append("main_route_steps", {})
                new_row.location = row.location
                new_row.distance = row.distance
                new_row.fuel_consumption_qty = row.fuel_consumption_qty
                new_row.location_type = row.location_type

    def set_expenses(self):
        reference_route = frappe.get_doc("Trip Routes", self.route)
        if len(reference_route.fixed_expenses) > 0:
            self.requested_fund_accounts_table = []
            for row in reference_route.fixed_expenses:
                fixed_expense_doc = frappe.get_doc("Fixed Expenses", row.expense)
                expense_account_doc = frappe.get_doc("Account", fixed_expense_doc.expense_account)
                payable_account_currency_doc = frappe.get_doc("Account", fixed_expense_doc.cash_bank_account)
                aday = nowdate()
                new_row = self.append("requested_fund_accounts_table", {})
                new_row.requested_date = aday
                new_row.request_amount = row.amount
                new_row.request_currency = row.currency
                new_row.request_status = "Requested"
                new_row.expense_type = row.expense
                new_row.expense_account = fixed_expense_doc.expense_account
                new_row.expense_account_currency = expense_account_doc.account_currency
                new_row.payable_account_currency = payable_account_currency_doc.account_currency
                new_row.payable_account = fixed_expense_doc.cash_bank_account
                new_row.party_type = row.party_type
                new_row.requested_by = frappe.session.user
                new_row.requested_on = now()
                if row.party_type == "Driver":
                    new_row.party = frappe.db.get_value(
                        "Driver", self.assigned_driver, "name"
                    )

    def set_driver(self):
        driver = None
        if self.transporter_type == "In House":
            if not self.assigned_driver:
                frappe.throw("Driver is not set")
            driver = self.assigned_driver
        elif self.transporter_type == "Sub-Contractor":
            if not self.sub_contactor_driver_name:
                frappe.throw("Driver Name is not set")

        for row in self.requested_fund_accounts_table:
            if row.party_type == "Driver":
                if driver:
                    row.party = driver

    def before_save(self):
        if not self.date:
            self.date = datetime.datetime.now()
        self.validate_main_route_inputs()

    def ensure_inventory_fuel_row(self):
        """For 'From Inventory', auto-create a fuel_request_history row
        from fuel_stock_out so it goes through the Fuel Request approval flow."""
        if not flt(self.fuel_stock_out):
            return

        # Check if there's already a row for this quantity
        existing_rows = self.get("fuel_request_history") or []
        if existing_rows:
            return

        fuel_item = frappe.get_value("Transport Settings", None, "fuel_item")
        if not fuel_item:
            frappe.throw(_("Please set Fuel Item in Transport Settings"))

        item_name = frappe.db.get_value("Item", fuel_item, "item_name")
        stock_uom = frappe.db.get_value("Item", fuel_item, "stock_uom")

        new_row = self.append("fuel_request_history", {})
        new_row.item_code = fuel_item
        new_row.item_name = item_name
        new_row.uom = stock_uom
        new_row.quantity = flt(self.fuel_stock_out)
        new_row.status = "Open"

    def validate_fuel_requests(self):
        make_request = False

        for request in self.get("fuel_request_history"):
            if request.status == "Open":
                make_request = True

        if make_request:
            existing_fuel_request = frappe.db.get_value(
                "Fuel Requests",
                {"reference_doctype": "Trips", "reference_docname": self.name},
            )

            ts = time.time()
            timestamp = datetime.datetime.fromtimestamp(ts).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            if existing_fuel_request:
                doc = frappe.get_doc("Fuel Requests", existing_fuel_request)
                doc.db_set("modified", timestamp)
                if "Fully Processed" == doc.status:
                    doc.db_set("status", "Partially Processed")
            else:
                fuel_request = frappe.new_doc("Fuel Requests")
                fuel_request.update(
                    {
                        "truck_plate_number": self.get("truck_number"),
                        "truck": self.get("truck_number"),
                        "truck_driver": self.get("assigned_driver"),
                        "reference_doctype": "Trips",
                        "reference_docname": self.name,
                        "status": "Waiting Approval",
                    }
                )
                fuel_request.insert(ignore_permissions=True)

            for request in self.get("fuel_request_history"):
                if request.status == "Open":
                    request.set("status", "Requested")
                    request.set("transaction_date", nowdate())

    def validate_main_route_inputs(self):
        loading_date = None
        offloading_date = None

        steps = self.get("main_route_steps")
        for step in steps:
            if step.location_type == "Loading Point":
                loading_date = step.loading_date
            if step.location_type == "Offloading Point":
                offloading_date = step.offloading_date
        if offloading_date and not loading_date:
            frappe.throw("Loading Date must be set before Offloading Date")

    def validate_request_status(self):
        for row in self.fuel_request_history:
            if row.status not in ["Rejected", "Approved"]:
                frappe.throw("<b>All fuel requests must be either approved or rejected before submitting the trip</b>")

        # Payment is handled via Requested Payment / Payment Entry after submission
        # so we only require Approved/Rejected status, not a ledger_entry link

        for row in self.requested_fund_accounts_table:
            if row.request_status not in ["Rejected", "Approved", "Accounts Approved"]:
                frappe.throw("<b>All fund requests must be either approved or rejected before submitting the trip</b>")


@frappe.whitelist()
def start_trip(docname):
    """Set trip status to In Transit, mark truck On Trip and driver in_trip"""
    trip = frappe.get_doc("Trips", docname)
    if trip.trip_status != "Pending":
        frappe.throw(_("Trip can only be started when status is Pending"))

    trip.db_set("trip_status", "In Transit")

    # Mark truck as On Trip so it is excluded from Manifest selection
    if trip.transporter_type == "In House" and trip.truck_number:
        frappe.db.set_value("Truck", trip.truck_number, {
            "status": "On Trip",
            "trans_ms_current_trip": trip.name,
        })

    # Mark driver as on trip so they are excluded from Manifest selection
    if trip.assigned_driver:
        frappe.db.set_value("Driver", trip.assigned_driver, "in_trip", 1)

    frappe.db.commit()
    return "success"


@frappe.whitelist()
def complete_trip(docname):
    """Set trip status to Completed, release truck and driver"""
    trip = frappe.get_doc("Trips", docname)
    if trip.trip_status not in ("Pending", "In Transit"):
        frappe.throw(_("Trip can only be completed when status is Pending or In Transit"))

    trip.db_set("trip_status", "Completed")
    trip.db_set("trip_completed", 1)
    trip.db_set("trip_completed_date", nowdate())

    # Release truck back to Idle
    if trip.transporter_type == "In House" and trip.truck_number:
        frappe.db.set_value("Truck", trip.truck_number, {
            "status": "Idle",
            "trans_ms_current_trip": "",
        })

    # Release driver
    if trip.assigned_driver:
        frappe.db.set_value("Driver", trip.assigned_driver, "in_trip", 0)

    frappe.db.commit()
    return "success"


@frappe.whitelist()
def create_vehicle_trip_from_manifest(args_array):
    args_dict = json.loads(args_array)
    vehicle_trip = frappe.new_doc("Trips")
    vehicle_trip.manifest = args_dict.get("manifest_name")
    vehicle_trip.transporter_type = args_dict.get("transporter_type")
    vehicle_trip.date = nowdate()
    if vehicle_trip.save():
        manifest = frappe.get_doc("Manifest", args_dict.get("manifest_name"))
        manifest.vehicle_trip = vehicle_trip.name
        manifest.save()
        cargos = frappe.get_all("Cargo Detail", filters={"manifest_number": manifest.name}, fields="*")
        for cargo in cargos:
            cargo_registration = frappe.get_doc("Cargo Registration", cargo.parent)
            for row in cargo_registration.cargo_details:
                if row.manifest_number == manifest.name:
                    row.created_trip = vehicle_trip.name
                    cargo_registration.save()
                    break

        if args_dict.get("transporter_type") == "In House":
            funds_args = {
                "reference_doctype": "Trips",
                "reference_docname": vehicle_trip.name,
                "manifest": args_dict.get("manifest_name"),
                "truck": args_dict.get("truck"),
                "truck_driver": args_dict.get("driver"),
                "trip_route": args_dict.get("trip_route")
            }
            request_funds(**funds_args)

    return vehicle_trip.as_dict()


def _make_expense_ledger_entry(row_doc, approved_by=None):
    """Create and submit a Ledger Entry for an approved Trip expense row.

    Updates row.ledger_entry, row.request_status → "Accounts Approved".
    Returns the submitted Ledger Entry document.
    Can be called from accounts_approval, approve_request, or the JS button.
    """
    if row_doc.ledger_entry:
        return frappe.get_doc("Ledger Entry", row_doc.ledger_entry)

    if not row_doc.expense_account:
        frappe.throw(_("Expense Account is required on expense row {0}.").format(row_doc.name))
    if not row_doc.payable_account:
        frappe.throw(_("Payable Account is required on expense row {0}.").format(row_doc.name))

    amount = flt(row_doc.request_amount)
    if amount <= 0:
        frappe.throw(_("Amount must be greater than zero for expense row {0}.").format(row_doc.name))

    currency = (
        row_doc.request_currency
        or frappe.db.get_value("Currency", {"enabled": 1}, "name")
        or "USD"
    )
    trip_date = frappe.db.get_value("Trips", row_doc.parent, "date")
    posting_date = row_doc.posting_date or row_doc.requested_date or trip_date or nowdate()

    ledger_doc = frappe.new_doc("Ledger Entry")
    ledger_doc.update({
        "posting_date": posting_date,
        "entry_type": "Expense",
        "source_type": "Trip Expense",
        "account": row_doc.expense_account,
        "contra_account": row_doc.payable_account,
        "party_type": row_doc.party_type or "",
        "party": row_doc.party or "",
        "currency": currency,
        "amount": amount,
        "reference_doctype": "Trips",
        "reference_name": row_doc.parent,
        "reference_trip": row_doc.parent,
        "reference_trip_expense": row_doc.name,
        "remarks": (
            row_doc.request_description
            or row_doc.expense_type
            or "Trip Expense for {0}".format(row_doc.parent)
        ),
    })
    ledger_doc.flags.ignore_permissions = True
    ledger_doc.insert(ignore_permissions=True)
    ledger_doc.submit()

    update_fields = {
        "ledger_entry": ledger_doc.name,
        "request_status": "Accounts Approved",
        "request_hidden_status": "1",
        "accounts_approved_on": now(),
    }
    if approved_by:
        update_fields["accounts_approved_by"] = approved_by
    frappe.db.set_value("Requested Fund Details", row_doc.name, update_fields)

    return ledger_doc


@frappe.whitelist()
def create_trip_expense_ledger_entry(doc, row):
    """Called from the 'Create Ledger Entry' button on the Trip expense child row."""
    row_dict = frappe._dict(json.loads(row))
    row_doc = frappe.get_doc("Requested Fund Details", row_dict.name)

    if row_doc.ledger_entry:
        frappe.msgprint(_("Ledger Entry already exists: {0}").format(row_doc.ledger_entry))
        return frappe.get_doc("Ledger Entry", row_doc.ledger_entry)

    if row_doc.request_status not in ("Approved", "Accounts Approved"):
        frappe.throw(_("Trip expense must be Approved before creating a ledger entry."))

    ledger_doc = _make_expense_ledger_entry(row_doc)
    ledger_url = frappe.utils.get_url_to_form("Ledger Entry", ledger_doc.name)
    frappe.msgprint(
        _("Ledger Entry Created: <a href='{0}'>{1}</a>").format(ledger_url, ledger_doc.name)
    )
    return ledger_doc


@frappe.whitelist()
def create_fund_jl(doc, row):
    doc = frappe.get_doc(json.loads(doc))
    row = frappe._dict(json.loads(row))
    if row.journal_entry:
        frappe.throw("Journal Entry Already Created")

    if row.request_status != "Approved":
        frappe.throw("Fund Request is not Approved")

    accounts = []

    company_currency = frappe.db.get_value(
        "Currency",
        {"enabled": 1},
        "name",
    )

    if company_currency != row.request_currency:
        multi_currency = 1
        exchange_rate = get_exchange_rate(row.request_currency, company_currency)
    else:
        multi_currency = 0
        exchange_rate = 1

    if row.request_currency != row.expense_account_currency:
        debit_amount = row.request_amount * exchange_rate
        debit_exchange_rate = exchange_rate
    else:
        debit_amount = row.request_amount
        debit_exchange_rate = 1

    if row.request_currency != row.payable_account_currency:
        credit_amt = row.request_amount * exchange_rate
        credit_exchange_rate = exchange_rate
    else:
        credit_amt = row.request_amount
        credit_exchange_rate = 1

    debit_row = dict(
        account=row.expense_account,
        exchange_rate=debit_exchange_rate,
        debit_in_account_currency=debit_amount,
        cost_center=row.cost_center,
    )
    accounts.append(debit_row)

    credit_row = dict(
        account=row.payable_account,
        exchange_rate=credit_exchange_rate,
        credit_in_account_currency=credit_amt,
        cost_center=row.cost_center,
    )
    accounts.append(credit_row)

    user_remark = "ref Document: {0}".format(doc.name)
    if row.requested_date:
        date = row.requested_date
    else:
        date = nowdate()

    jv_doc = frappe.get_doc(
        dict(
            doctype="Journal Entry",
            posting_date=date,
            accounts=accounts,
            multi_currency=multi_currency,
            user_remark=user_remark,
        )
    )
    jv_doc.flags.ignore_permissions = True
    frappe.flags.ignore_account_permission = True
    set_dimension(doc, jv_doc)
    for account_row in jv_doc.accounts:
        set_dimension(doc, jv_doc, tr_child=account_row)
    jv_doc.save()
    jv_url = frappe.utils.get_url_to_form(jv_doc.doctype, jv_doc.name)
    si_msgprint = "Journal Entry Created <a href='{0}'>{1}</a>".format(
        jv_url, jv_doc.name
    )
    frappe.msgprint(_(si_msgprint))
    frappe.set_value(row.doctype, row.name, "journal_entry", jv_doc.name)
    return jv_doc


@frappe.whitelist()
def make_vehicle_inspection(source_name, target_doc=None, ignore_permissions=False):
    docs = get_mapped_doc(
        "Trips",
        source_name,
        {
            "Trips": {
                "doctype": "Vehicle Inspection",
                "field_map": {
                    "driver_name": "driver_name",
                    "truck_number": "vehicle_plate_number",
                    "name": "trip_reference",
                },
                "validation": {
                    "docstatus": ["=", 0],
                },
            }
        },
        target_doc,
        postprocess=None,
        ignore_permissions=ignore_permissions,
    )
    return docs


@frappe.whitelist()
def create_stock_out_entry(doc, fuel_stock_out):
    doc = frappe.get_doc(json.loads(doc))
    if doc.stock_out_entry:
        return frappe.get_doc("Stock Entry", doc.stock_out_entry)
    fuel_item = frappe.get_value("Transport Settings", None, "fuel_item")
    if not fuel_item:
        frappe.throw(_("Please Set Fuel Item in Transport Settings"))
    warehouse = frappe.get_value("Truck", doc.truck_number, "trans_ms_fuel_warehouse")
    if not warehouse:
        frappe.throw(_("Please Set Fuel Warehouse in Vehicle"))
    item_rate = flt(frappe.get_value("Item", fuel_item, "standard_rate") or 0)
    item = {
        "item_code": fuel_item,
        "qty": float(fuel_stock_out),
        "s_warehouse": warehouse,
        "basic_rate": item_rate,
    }
    stock_entry_doc = frappe.get_doc(
        dict(
            doctype="Stock Entry",
            from_bom=0,
            posting_date=nowdate(),
            posting_time=nowtime(),
            items=[item],
            stock_entry_type="Material Issue",
            purpose="Material Issue",
            from_warehouse=warehouse,
            reference_trip=doc.name,
            remarks="Transfer for {0} in truck {1}".format(
                doc.assigned_driver,
                doc.truck_number,
            ),
        )
    )
    set_dimension(doc, stock_entry_doc)
    set_dimension(doc, stock_entry_doc, tr_child=stock_entry_doc.items[0])
    stock_entry_doc.insert(ignore_permissions=True)
    stock_entry_doc.flags.ignore_permissions = True
    stock_entry_doc.submit()
    doc.stock_out_entry = stock_entry_doc.name
    doc.save()
    return stock_entry_doc


@frappe.whitelist()
def create_purchase_invoice(request_doc, item):
    item = frappe._dict(json.loads(item))
    request_doc = frappe._dict(json.loads(request_doc))
    set_warehouse = frappe.get_value(
        "Truck", request_doc.truck_number, "trans_ms_fuel_warehouse"
    )
    if not set_warehouse:
        frappe.throw(_("Fuel Stock Warehouse not set in Truck"))
    existing_invoice = item.get("purchase_invoice") or item.get("purchase_order")
    if existing_invoice:
        frappe.throw(_("Purchase Invoice already exists"))
    doc = frappe.new_doc("Purchase Invoice")
    doc.supplier = item.supplier
    doc.currency = item.currency
    doc.set_warehouse = set_warehouse
    doc.reference_trip = request_doc.name
    if item.transaction_date:
        doc.posting_date = item.transaction_date
        doc.due_date = item.transaction_date
    else:
        doc.posting_date = nowdate()
    doc.posting_time = now().split(" ")[1]
    new_item = doc.append("items", {})
    new_item.item_code = item.item_code
    new_item.qty = item.quantity
    new_item.rate = item.cost_per_litre
    new_item.warehouse = set_warehouse
    set_dimension(request_doc, doc)
    set_dimension(request_doc, doc, tr_child=new_item)
    doc.insert(ignore_permissions=True)
    doc.flags.ignore_permissions = True
    doc.submit()
    frappe.msgprint(_("Purchase Invoice {0} is created").format(doc.name))
    table_meta = frappe.get_meta(item.doctype)
    target_field = "purchase_invoice" if table_meta.has_field("purchase_invoice") else "purchase_order"
    frappe.set_value(item.doctype, item.name, target_field, doc.name)
    return doc.name


@frappe.whitelist()
def create_purchase_order(request_doc, item):
    # Backward-compatible alias
    return create_purchase_invoice(request_doc, item)


@frappe.whitelist()
def get_fuel_approval_preview(trip_name):
    """Return trip-level fuel settings so the JS dialog can tell the user
    what will happen when they approve a fuel row (stock deduction vs expense booking)."""
    trip = frappe.get_doc("Trips", trip_name)
    result = frappe._dict(
        fuel_source_type=trip.fuel_source_type or "",
        warehouse=None,
        fuel_item=None,
        expense_account=None,
        cash_account=None,
    )

    if trip.fuel_source_type == "From Inventory":
        result.fuel_item = frappe.get_value("Transport Settings", None, "fuel_item")
        if trip.truck_number:
            result.warehouse = frappe.get_value("Truck", trip.truck_number, "trans_ms_fuel_warehouse")
    else:
        settings = frappe.get_single("Transport Settings")
        result.expense_account = settings.fuel_expense_account
        result.cash_account = settings.fuel_cash_account

    return result


@frappe.whitelist()
def auto_process_fuel_approval(fuel_row_name):
    """Auto-process an approved fuel request row.
    Called from fuel_requests.py after approval.
    - From Inventory: auto-create Stock Entry
    - Cash Purchase / From Supplier: auto-create Purchase Invoice
    """
    fuel_row = frappe.get_doc("Fuel Requests Table", fuel_row_name)
    trip = frappe.get_doc("Trips", fuel_row.parent)

    if trip.fuel_source_type == "From Inventory":
        # Auto-create stock deduction if not already done
        if not trip.stock_out_entry:
            try:
                fuel_item = frappe.get_value("Transport Settings", None, "fuel_item")
                if not fuel_item:
                    frappe.msgprint(
                        _("Fuel Item not set in Transport Settings. Stock entry not created for trip {0}.").format(trip.name),
                        indicator="orange", title=_("Transport Settings Missing")
                    )
                    return

                warehouse = frappe.get_value("Truck", trip.truck_number, "trans_ms_fuel_warehouse")
                if not warehouse:
                    frappe.msgprint(
                        _("Fuel warehouse not set for truck {0}. Stock entry not created for trip {1}.").format(
                            trip.truck_number, trip.name
                        ),
                        indicator="orange", title=_("Truck Configuration Missing")
                    )
                    return

                item_rate = flt(frappe.get_value("Item", fuel_item, "standard_rate") or 0)
                item = {
                    "item_code": fuel_item,
                    "qty": float(fuel_row.quantity),
                    "s_warehouse": warehouse,
                    "basic_rate": item_rate,
                }
                stock_entry_doc = frappe.get_doc(
                    dict(
                        doctype="Stock Entry",
                        from_bom=0,
                        posting_date=nowdate(),
                        posting_time=nowtime(),
                        items=[item],
                        stock_entry_type="Material Issue",
                        purpose="Material Issue",
                        from_warehouse=warehouse,
                        reference_trip=trip.name,
                        remarks="Auto fuel deduction for trip {0}".format(trip.name),
                    )
                )
                set_dimension(trip, stock_entry_doc)
                set_dimension(trip, stock_entry_doc, tr_child=stock_entry_doc.items[0])
                stock_entry_doc.insert(ignore_permissions=True)
                stock_entry_doc.flags.ignore_permissions = True
                stock_entry_doc.submit()
                trip.db_set("stock_out_entry", stock_entry_doc.name)
            except Exception as e:
                frappe.log_error(f"Auto stock entry failed for trip {trip.name}: {str(e)}", "Auto Fuel Process")

    else:
        # Cash Purchase: add a fund request row on the Trip → goes through Requested Payment flow
        if not fuel_row.ledger_entry:
            try:
                settings = frappe.get_single("Transport Settings")
                expense_account = settings.fuel_expense_account
                cash_account = settings.fuel_cash_account
                if not expense_account:
                    frappe.msgprint(
                        _("Fuel Expense Account not set in Transport Settings. Fuel expense row not created for trip {0}.").format(trip.name),
                        indicator="orange", title=_("Transport Settings Missing")
                    )
                    return
                if not cash_account:
                    frappe.msgprint(
                        _("Fuel Cash/Bank Account not set in Transport Settings. "
                          "Please configure it under Transport Settings → Fuel Cash Account. "
                          "Fuel expense row not created for trip {0}.").format(trip.name),
                        indicator="orange", title=_("Transport Settings Missing")
                    )
                    return

                amount = flt(fuel_row.total_cost) or (flt(fuel_row.quantity) * flt(fuel_row.cost_per_litre))
                currency = fuel_row.currency or frappe.db.get_value("Currency", {"enabled": 1}, "name") or "USD"
                expense_account_doc = frappe.get_doc("Account", expense_account)
                cash_account_doc = frappe.get_doc("Account", cash_account)

                fuel_name = fuel_row.item_name or frappe.db.get_value("Item", fuel_row.item_code, "item_name") or fuel_row.item_code

                new_row = trip.append("requested_fund_accounts_table", {})
                new_row.requested_date = nowdate()
                new_row.request_amount = amount
                new_row.request_currency = currency
                new_row.request_status = "Requested"
                new_row.expense_type = "Fuel - {0}".format(fuel_name)
                new_row.request_description = "Fuel purchase: {0} litres of {1}".format(
                    fuel_row.quantity, fuel_name
                )
                new_row.expense_account = expense_account
                new_row.expense_account_currency = expense_account_doc.account_currency
                new_row.payable_account = cash_account
                new_row.payable_account_currency = cash_account_doc.account_currency
                new_row.party_type = "Supplier" if fuel_row.supplier else "Driver"
                new_row.party = fuel_row.supplier or trip.assigned_driver
                new_row.requested_by = frappe.session.user
                new_row.requested_on = now()

                trip.flags.ignore_validate = True
                trip.save(ignore_permissions=True)

                # Link the fund request row back to the fuel row
                fuel_row.db_set("ledger_entry", new_row.name)

                # Create/update the Requested Payment document
                request_funds(
                    reference_doctype="Trips",
                    reference_docname=trip.name,
                    truck=trip.truck_number,
                    truck_driver=trip.assigned_driver,
                    trip_route=trip.route,
                )
            except Exception as e:
                frappe.log_error(f"Auto fund request failed for trip {trip.name}: {str(e)}", "Auto Fuel Process")


@frappe.whitelist()
def create_breakdown(docname):
    """Mark trip as Breakdown, update Truck/Driver, create Trip Breakdown doc"""
    trip = frappe.get_doc("Trips", docname)

    if trip.trip_status not in ("Pending", "In Transit"):
        frappe.throw(_("Breakdown can only be recorded for Pending or In Transit trips"))

    # Use db_set to avoid triggering validation hooks
    trip.db_set("trip_status", "Breakdown")
    trip.db_set("status", "Not Re-Assigned")
    trip.db_set("breakdown_date", now())

    # Move truck to Under Maintenance and clear current trip
    if trip.transporter_type == "In House" and trip.truck_number:
        frappe.db.set_value("Truck", trip.truck_number, {
            "status": "Under Maintenance",
            "trans_ms_current_trip": "",
        })

    # Release driver so they can be reassigned
    if trip.assigned_driver:
        frappe.db.set_value("Driver", trip.assigned_driver, "in_trip", 0)

    # Create the Trip Breakdown document
    breakdown = frappe.new_doc("Trip Breakdown")
    breakdown.trip = docname
    breakdown.date = nowdate()
    breakdown.status = "Not Re-Assigned"
    if trip.location:
        breakdown.breakdown_location = trip.location
    breakdown.insert(ignore_permissions=True)

    frappe.db.commit()
    return breakdown.name


@frappe.whitelist()
def create_resumption_trip(docname):
    old_trip = frappe.get_doc("Trips", docname)

    new_trip = frappe.new_doc("Trips")
    new_trip.update(old_trip.as_dict())
    new_trip.location_update = []
    new_trip.trip_status = "Pending"
    new_trip.stock_out_entry = ""

    new_trip.insert()

    if new_trip.transporter_type == "In House":
        funds_args = {
            "reference_doctype": "Trips",
            "reference_docname": new_trip.name,
            "manifest": new_trip.manifest,
            "truck": new_trip.truck_number,
            "truck_driver": new_trip.assigned_driver,
            "trip_route": new_trip.route
        }
        request_funds(**funds_args)

    if new_trip.round_trip:
        round_trip = frappe.get_doc("Round Trip", new_trip.round_trip)
        round_trip.append("trip_details", {
            "trip_id": new_trip.name
        })
        round_trip.save()

    old_trip.resumption_trip = new_trip.name
    old_trip.status = "Re-Assigned"
    old_trip.save()
    return new_trip.as_dict()


# ─── Trip Expense Quick-Action API ────────────────────────────────────────────

@frappe.whitelist()
def get_trip_expense_rows(trip_name, status_filter=None):
    """Return Requested Fund Details rows for a trip, optionally filtered by status."""
    filters = {
        "parent": trip_name,
        "parenttype": "Trips",
        "parentfield": "requested_fund_accounts_table",
    }
    if status_filter:
        if isinstance(status_filter, str):
            try:
                status_filter = frappe.parse_json(status_filter)
            except Exception:
                status_filter = [status_filter]
        filters["request_status"] = ["in", status_filter]

    rows = frappe.get_all(
        "Requested Fund Details",
        filters=filters,
        fields=[
            "name", "expense_type", "request_amount", "request_currency",
            "request_status", "party_type", "party", "expense_account",
            "payable_account", "requested_date", "journal_entry",
        ],
        order_by="idx asc",
    )
    return rows


@frappe.whitelist()
def get_trip_fuel_rows(trip_name, status_filter=None):
    """Return Fuel Requests Table rows for a trip, optionally filtered by status."""
    filters = {
        "parent": trip_name,
        "parenttype": "Trips",
        "parentfield": "fuel_request_history",
    }
    if status_filter:
        if isinstance(status_filter, str):
            try:
                status_filter = frappe.parse_json(status_filter)
            except Exception:
                status_filter = [status_filter]
        filters["status"] = ["in", status_filter]

    rows = frappe.get_all(
        "Fuel Requests Table",
        filters=filters,
        fields=[
            "name", "item_code", "item_name", "quantity", "cost_per_litre",
            "total_cost", "currency", "status", "supplier",
        ],
        order_by="idx asc",
    )
    return rows


@frappe.whitelist()
def trip_approve_fuel_rows(trip_name, row_names):
    """Directly approve selected Cash Purchase fuel rows from the Trip form.
    Sets status to Approved and calls auto_process_fuel_approval for each row.
    """
    row_names = frappe.parse_json(row_names) if isinstance(row_names, str) else row_names
    if not row_names:
        frappe.throw("No rows selected")

    approved = []
    errors = []

    for row_name in row_names:
        try:
            row = frappe.get_doc("Fuel Requests Table", row_name)
            if row.parent != trip_name:
                frappe.throw(f"Row {row_name} does not belong to trip {trip_name}")
            if row.status in ("Approved", "Rejected"):
                continue

            frappe.db.set_value("Fuel Requests Table", row_name, "status", "Approved")
            auto_process_fuel_approval(row_name)
            approved.append(row_name)
        except Exception as e:
            errors.append(f"{row_name}: {str(e)}")
            frappe.log_error(frappe.get_traceback(), f"trip_approve_fuel_rows failed: {row_name}")

    return {"approved": approved, "errors": errors}


@frappe.whitelist()
def trip_approve_expense_rows(trip_name, row_names):
    """Directly approve expense rows — collapses manager + accounts approval.
    Posts Expense Dr / Payable Cr GL entries with voucher_type="Trips".
    """
    from vsd_fleet_ms.vsd_fleet_ms.doctype.requested_payment.requested_payment import (
        get_gl_entries, make_gl_entries,
    )

    row_names = frappe.parse_json(row_names) if isinstance(row_names, str) else row_names
    if not row_names:
        frappe.throw("No rows selected")

    approved = []
    errors = []

    for row_name in row_names:
        try:
            row = frappe.get_doc("Requested Fund Details", row_name)
            if row.parent != trip_name:
                frappe.throw(f"Row {row_name} does not belong to trip {trip_name}")
            if row.request_status in ("Accounts Approved", "Rejected"):
                continue
            if not row.expense_account:
                errors.append(f"{row.expense_type or row_name}: Expense Account not set")
                continue
            if not row.payable_account:
                errors.append(f"{row.expense_type or row_name}: Payable Account not set")
                continue

            # Ensure conversion_rate is positive to avoid division-by-zero in GL
            if not flt(row.conversion_rate):
                row.conversion_rate = 1.0

            gl_entries = get_gl_entries(row, "Trips", trip_name)
            make_gl_entries(gl_entries)

            frappe.db.set_value("Requested Fund Details", row_name, {
                "request_status":        "Accounts Approved",
                "approved_by":           frappe.session.user,
                "accounts_approved_by":  frappe.session.user,
                "approved_date":         nowdate(),
                "request_hidden_status": "1",
            })
            approved.append(row_name)
        except Exception as e:
            errors.append(f"{row_name}: {str(e)}")
            frappe.log_error(frappe.get_traceback(), f"trip_approve_expense_rows failed: {row_name}")

    return {"approved": approved, "errors": errors}


@frappe.whitelist()
def trip_make_payment(trip_name, row_names, cash_bank_account, mode_of_payment="Cash"):
    """Create Payment Entry for Accounts Approved expense rows directly from the Trip form.
    Ensures a Requested Payment doc exists for the trip, then delegates to
    create_fund_payment_entry which handles the Payment Entry creation.
    """
    from vsd_fleet_ms.vsd_fleet_ms.doctype.payment_entry.payment_entry import (
        create_fund_payment_entry,
    )

    row_names = frappe.parse_json(row_names) if isinstance(row_names, str) else row_names

    trip = frappe.get_doc("Trips", trip_name)

    # Ensure a Requested Payment doc exists (creates one if missing)
    request_funds(
        reference_doctype="Trips",
        reference_docname=trip_name,
        truck=trip.truck_number,
        truck_driver=trip.assigned_driver,
        trip_route=trip.route,
    )

    rp_name = frappe.db.get_value(
        "Requested Payment",
        {"reference_doctype": "Trips", "reference_docname": trip_name},
        "name",
    )
    if not rp_name:
        frappe.throw("Could not find or create a Requested Payment for this trip")

    return create_fund_payment_entry(rp_name, row_names, cash_bank_account, mode_of_payment)
