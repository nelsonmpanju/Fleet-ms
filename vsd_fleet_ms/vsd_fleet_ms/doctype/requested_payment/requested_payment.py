# Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
import datetime
import json
from frappe.model.document import Document
from frappe.utils import flt, comma_or, nowdate
from frappe import msgprint, _


class RequestedPayment(Document):
    def onload(self):
        pass

    def get_all_children(self, parenttype=None):
        # For getting children
        return self.get("payment_reference") or []

    def update_children(self):
        """update child tables"""
        self.update_child_table("payment_reference")

    def load_from_db(self):
        """Load document and children from database and create properties
        from fields"""
        if not getattr(self, "_metaclass", False) and self.meta.issingle:
            single_doc = frappe.db.get_singles_dict(self.doctype)
            if not single_doc:
                single_doc = frappe.new_doc(self.doctype).as_dict()
                single_doc["name"] = self.doctype
                del single_doc["__islocal"]

            super(Document, self).__init__(single_doc)
            self.init_valid_columns()
            self._fix_numeric_types()

        else:
            d = frappe.db.get_value(self.doctype, self.name, "*", as_dict=1)
            if not d:
                frappe.throw(
                    _("{0} {1} not found").format(_(self.doctype), self.name),
                    frappe.DoesNotExistError,
                )

            super(Document, self).__init__(d)

        if self.name == "DocType" and self.doctype == "DocType":
            from frappe.model.meta import doctype_table_fields

            table_fields = doctype_table_fields
        else:
            table_fields = self.meta.get_table_fields()

        for df in table_fields:
            # Load details for payments already paid
            if df.fieldname == "payment_reference":
                children = frappe.db.get_values(
                    df.options,
                    {
                        "parent": self.name,
                        "parenttype": self.doctype,
                        "parentfield": df.fieldname,
                    },
                    "*",
                    as_dict=True,
                    order_by="idx asc",
                )
                if children:
                    self.set(df.fieldname, children)
                else:
                    self.set(df.fieldname, [])
            elif (
                df.fieldname == "requested_funds"
            ):  # Load requests which are not approved nor rejected
                children = frappe.db.get_values(
                    df.options,
                    {
                        "parent": ["=", self.get("reference_docname")],
                        "parenttype": ["=", self.get("reference_doctype")],
                        "parentfield": [
                            "in",
                            (
                                "requested_funds",
                                "requested_fund_accounts_table",
                                "return_requested_funds",
                                "requested_fund"
                            ),
                        ],
                        "request_status": [
                            "in",
                            ("open", "Requested", "Recommended", "Pre-Approved"),
                        ],
                    },
                    "*",
                    as_dict=True,
                    order_by="idx asc",
                )
                if children:
                    self.set(df.fieldname, children)
                else:
                    self.set(df.fieldname, [])
            elif df.fieldname == "accounts_approval":
                children = frappe.db.get_values(
                    "Requested Fund Details",
                    {
                        "parent": ["=", self.get("reference_docname")],
                        "parenttype": ["=", self.get("reference_doctype")],
                        "parentfield": [
                            "in",
                            (
                                "requested_funds",
                                "requested_fund_accounts_table",
                                "return_requested_funds",
                                "requested_fund"
                            ),
                        ],
                        "request_status": [
                            "in",
                            (
                                "Approved",
                                "Rejected",
                                "Accounts Approved",
                                "Accounts Rejected",
                                "Accounts Cancelled",
                            ),
                        ],
                    },
                    "*",
                    as_dict=True,
                    order_by="idx asc",
                )
                if children:
                    for child in children:
                        child.reference = child.name
                    self.set(df.fieldname, children)
                else:
                    self.set(df.fieldname, [])

        # sometimes __setup__ can depend on child values, hence calling again at the end
        if hasattr(self, "__setup__"):
            self.__setup__()


def process_gl_map(gl_map, merge_entries=True):
    if not merge_entries:
        return gl_map

    merged = {}
    for entry in gl_map:
        key = (
            entry.get("account"),
            entry.get("party_type"),
            entry.get("party"),
            entry.get("cost_center"),
            entry.get("against_voucher_type"),
            entry.get("against_voucher"),
            entry.get("voucher_type"),
            entry.get("voucher_no"),
        )
        if key not in merged:
            merged[key] = frappe._dict(entry.copy())
        else:
            merged[key].debit = flt(merged[key].get("debit")) + flt(entry.get("debit"))
            merged[key].credit = flt(merged[key].get("credit")) + flt(entry.get("credit"))
            merged[key].debit_in_account_currency = flt(
                merged[key].get("debit_in_account_currency")
            ) + flt(entry.get("debit_in_account_currency"))
            merged[key].credit_in_account_currency = flt(
                merged[key].get("credit_in_account_currency")
            ) + flt(entry.get("credit_in_account_currency"))
    return list(merged.values())


def save_entries(gl_map, adv_adj=False, update_outstanding="Yes", from_repost=False):
    for entry in gl_map:
        gl_entry = frappe.new_doc("GL Entry")
        gl_entry.update(entry)
        gl_entry.flags.ignore_permissions = True
        gl_entry.insert(ignore_permissions=True)


def get_fiscal_years(posting_date, company=None):
    year = str(getattr(posting_date, "year", None) or str(posting_date)[:4])
    return [(year, posting_date, posting_date)]


def get_account_currency(account):
    if account:
        currency = frappe.db.get_value("Account", account, "account_currency")
        if currency:
            return currency
    return frappe.db.get_value("Currency", {"enabled": 1}, "name") or "USD"


def set_balance_in_account_currency(gl_dict, account_currency, conversion_rate, company_currency):
    conversion_rate = flt(conversion_rate) or 1
    if account_currency == company_currency:
        if not gl_dict.get("debit_in_account_currency"):
            gl_dict.debit_in_account_currency = flt(gl_dict.get("debit"))
        if not gl_dict.get("credit_in_account_currency"):
            gl_dict.credit_in_account_currency = flt(gl_dict.get("credit"))
        return

    if gl_dict.get("debit") and not gl_dict.get("debit_in_account_currency"):
        gl_dict.debit_in_account_currency = flt(gl_dict.get("debit")) / conversion_rate
    if gl_dict.get("credit") and not gl_dict.get("credit_in_account_currency"):
        gl_dict.credit_in_account_currency = flt(gl_dict.get("credit")) / conversion_rate


def validate_expense_against_budget(entry):
    return


def validate_balance_type(account, adv_adj=False):
    return


def check_freezing_date(posting_date, adv_adj=False):
    return


def update_outstanding_amt(
    account, party_type, party, against_voucher_type, against_voucher, on_cancel=False
):
    return


def validate_frozen_account(account, adv_adj=False):
    return


def get_outstanding_payments(self, account_currency):
    # Timestamp
    ts = time.time()

    # Initialize values
    total_amount = outstanding_amount = 0
    due_date = datetime.datetime.now().date()

    requested_from = frappe.get_doc(self.reference_doctype, self.reference_docname)
    if self.reference_doctype == "Trips":
        for request in requested_from.requested_fund_accounts_table:
            if (
                request.request_status == "Approved"
                and request.request_currency == account_currency
            ):
                total_amount = total_amount + request.request_amount
                # request_date = datetime.datetime.strptime(request.request_date, '%Y-%m-%d')
                if request.requested_date < due_date:
                    due_date = request.requested_date

        for request in requested_from.return_requested_funds:
            if (
                request.request_status == "Approved"
                and request.request_currency == account_currency
            ):
                total_amount = total_amount + request.request_amount
                if request.requested_date < due_date:
                    due_date = request.requested_date
    else:
        for request in requested_from.requested_funds:
            if (
                request.request_status == "Approved"
                and request.request_currency == account_currency
            ):
                total_amount = total_amount + request.request_amount
                if request.requested_date < due_date:
                    due_date = request.requested_date

    paid_amount = frappe.db.sql(
        """SELECT (CASE WHEN SUM(debit_in_account_currency) > 0 THEN SUM(debit_in_account_currency) ELSE 0 END) AS paid_amount 
					FROM `tabGL Entry` WHERE debit_in_account_currency > 0 AND account_currency = %s 
						AND voucher_type = 'Requested Payment' AND voucher = %s""",
        (account_currency, self.name),
        as_dict=True,
    )
    # frappe.msgprint(paid_amount[0].paid_amount)
    outstanding_amount = total_amount - float(paid_amount[0].paid_amount)

    return frappe._dict(
        {
            "due_date": due_date,
            "total_amount": total_amount,
            "outstanding_amount": outstanding_amount,
            "exchange_rate": 1,
        }
    )


def validate_requested_funds(doc):
    make_request = False
    open_requests = []
    for requested_fund in doc.requested_funds:
        if requested_fund.request_status == "open":
            make_request = True
            open_requests.append(requested_fund)

    if make_request:
        args = {
            "reference_doctype": doc.doctype,
            "reference_docname": doc.name,
        }
        request_status = request_funds(
            reference_doctype=doc.doctype,
            reference_docname=doc.name,
        )
        if request_status == "Request Inserted" or request_status == "Request Updated":
            for open_request in open_requests:
                open_request.set("request_status", "Requested")


@frappe.whitelist(allow_guest=True)
def request_funds(**args):
    args = frappe._dict(args)
    existing_payment_request = frappe.db.get_value(
        "Requested Payment",
        {
            "reference_doctype": args.reference_doctype,
            "reference_docname": args.reference_docname,
        },
    )

    # Timestamp
    ts = time.time()
    timestamp = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    if existing_payment_request:
        # Mark the request as open
        doc = frappe.get_doc("Requested Payment", existing_payment_request)
        doc.db_set("approval_status", "Waiting Approval")
        doc.db_set("modified", timestamp)
        return "Request Updated"
    else:
        request = frappe.new_doc("Requested Payment")
        request.update(
            {
                "reference_doctype": args.reference_doctype,
                "reference_docname": args.reference_docname,
                "manifest": args.manifest,
                "truck_no": args.truck,
                "truck_driver": args.truck_driver,
                "trip_route": args.trip_route,
                "approval_status": "Waiting Approval",
                "payment_status": "Waiting Approval",
            }
        )
        request.insert(ignore_permissions=True)
        return "Request Inserted"


@frappe.whitelist(allow_guest=True)
def recommend_request(**args):
    args = frappe._dict(args)

    # frappe.db.sql("UPDATE `tabRequested Funds Details` SET request_status = 'Recommended', request_hidden_status = 0 WHERE name = %s", args.request_docname)
    # return args.request_docname
    # Mark the request as open
    doc = frappe.get_doc("Requested Fund Details", args.request_docname)
    doc.db_set("request_status", "Recommended")
    doc.db_set("request_hidden_status", "0")
    doc.db_set("recommended_by", args.user)
    return "Request Updated"


@frappe.whitelist(allow_guest=True)
def recommend_against_request(**args):
    args = frappe._dict(args)

    # frappe.db.sql("UPDATE `tabRequested Funds Details` SET request_status = 'Recommended', request_hidden_status = 0 WHERE name = %s", args.request_docname)
    # return args.request_docname
    # Mark the request as open
    doc = frappe.get_doc("Requested Fund Details", args.request_docname)
    doc.db_set("request_status", "Recommended Against")
    doc.db_set("request_hidden_status", "0")
    doc.db_set("recommended_by", args.user)
    return "Request Updated"


@frappe.whitelist(allow_guest=True)
def accounts_approval(**args):
    args = frappe._dict(args)
    local = json.loads(args.local)

    if args.reference:
        reference = frappe.get_doc("Requested Fund Details", args.reference)
        if reference.request_status in ["Requested", "Recommended", "Pre-Approved", "Approved", "Accounts Cancelled"]:
            to_validate = [
                {"fieldname": "posting_date", "label": "Posting Date"},
                {"fieldname": "cost_center", "label": "Cost Center"},
                {"fieldname": "expense_account", "label": "Expense Account"},
                {"fieldname": "payable_account", "label": "Payable Account"},
                {"fieldname": "party_type", "label": "Party Type"},
                {"fieldname": "party", "label": "Party"},
            ]
            for field in to_validate:
                if not local.get(field["fieldname"]):
                    frappe.throw(
                        "Error: Please enter " + field["label"] + " for all rows"
                    )

            # Save changes made to accounts info
            to_save = [
                "expense_account",
                "payable_account",
                "party_type",
                "expense_type",
                "party",
                "invoice_number",
                "expense_account_currency",
                "conversion_rate",
                "payable_account_currency",
                "cost_center",
                "posting_date",
                "accounts_approved_by",
                "accounts_approved_on",
                "accounts_approver_comment",
            ]
            for field in to_save:
                reference.db_set(field, local.get(field))

            # Create Ledger Entry (Trip rows) or GL entries (non-Trip legacy)
            if reference.parenttype == "Trips":
                from vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips import _make_expense_ledger_entry
                _make_expense_ledger_entry(reference, approved_by=args.user)
                # _make_expense_ledger_entry already sets request_status + accounts_approved_by
            else:
                gl_entries = get_gl_entries(
                    reference, args.parent_doctype, args.parent_docname
                )
                make_gl_entries(gl_entries)
                reference.db_set("request_status", "Accounts Approved")
                reference.db_set("request_hidden_status", "1")
                reference.db_set("accounts_approved_by", args.user)

            parent = frappe.get_doc("Requested Payment", args.parent_docname)
            update_payment_status(parent)
            return "Request Updated"


@frappe.whitelist(allow_guest=True)
def accounts_cancel(**args):
    args = frappe._dict(args)
    local = json.loads(args.local)

    if args.reference:
        reference = frappe.get_doc("Requested Fund Details", args.reference)

        if reference.request_status == "Accounts Approved":
            in_account_currency = flt(reference.request_amount) * flt(reference.conversion_rate or 1)

            if reference.ledger_entry:
                # Ledger Entry path: block only if a Payment Entry has already been made
                paid_amount_pe = flt(frappe.db.sql(
                    """SELECT IFNULL(SUM(debit_in_account_currency), 0) as amt
                    FROM `tabGL Entry`
                    WHERE against_voucher_type = 'Requested Payment' AND against_voucher = %s
                      AND voucher_type = 'Payment Entry'""",
                    (args.parent_docname,),
                    as_dict=1,
                )[0].amt)
                if paid_amount_pe > 0:
                    frappe.throw(
                        _("Unable to cancel. A payment of {0} has already been made. "
                          "Please cancel the payment entry first.").format(paid_amount_pe)
                    )
                # Cancel the Ledger Entry (reverses its GL entries)
                le = frappe.get_doc("Ledger Entry", reference.ledger_entry)
                if le.docstatus == 1:
                    le.cancel()
                reference.db_set("ledger_entry", None)
            else:
                # GL entry path (non-Trip legacy rows)
                paid_amount = get_paid_amount(
                    args.parent_doctype, args.parent_docname,
                    reference.party_type, reference.party, reference.payable_account,
                )
                total_approved = get_total_approved(
                    args.parent_doctype, args.parent_docname,
                    reference.party_type, reference.party, reference.payable_account,
                )
                if (total_approved - (paid_amount + in_account_currency)) < 0:
                    frappe.throw(
                        "Unable to cancel. Payment has already been made against the account. "
                        "Please cancel the payment entry first. "
                        "Paid: " + str(paid_amount) +
                        " Total Approved: " + str(total_approved) +
                        " Account Currency: " + str(in_account_currency)
                    )
                gl_entries = get_gl_entries(reference, args.parent_doctype, args.parent_docname)
                make_gl_entries(gl_entries, True)

            reference.db_set("request_status", "Accounts Cancelled")
            reference.db_set("request_hidden_status", "1")
            reference.db_set("accounts_approved_by", args.user)
            parent = frappe.get_doc("Requested Payment", args.parent_docname)
            update_payment_status(parent)
            return "Request Updated"


def get_paid_amount(dt, dn, party_type, party, account):
    if party_type == "Customer":
        dr_or_cr = "credit_in_account_currency - debit_in_account_currency"
    else:
        dr_or_cr = "debit_in_account_currency - credit_in_account_currency"

    paid_amount = frappe.db.sql(
        """
		select ifnull(sum({dr_or_cr}), 0) as paid_amount
		from `tabGL Entry`
		where against_voucher_type = %s
			and against_voucher = %s
			and party_type = %s
			and party = %s
			and account = %s
			and {dr_or_cr} > 0
	""".format(
            dr_or_cr=dr_or_cr
        ),
        (dt, dn, party_type, party, account),
    )

    return paid_amount[0][0] if paid_amount else 0


def get_total_approved(dt, dn, party_type, party, account):
    total_approved = frappe.db.sql(
        """
		select ifnull(sum(credit_in_account_currency), 0) as total_approved
		from `tabGL Entry`
		where against_voucher_type = %s
			and against_voucher = %s
			and party_type = %s
			and party = %s
			and account = %s
	""",
        (dt, dn, party_type, party, account),
    )

    return total_approved[0][0] if total_approved else 0


def get_gl_entries(data, reference_doctype, reference_docname):
    gl_entry = []
    doc = frappe.get_doc(reference_doctype, reference_docname)
    company_currency = frappe.db.get_value("Currency", {"enabled": 1}, "name") or "USD"

    # payable entry
    payable_account_currency = get_account_currency(data.payable_account)
    gl_entry.append(
        get_gl_dict(
            doc,
            data,
            {
                "account": data.payable_account,
                "credit": data.request_amount,
                "credit_in_account_currency": data.request_amount
                if payable_account_currency == company_currency
                else data.request_amount / data.conversion_rate,
                "against": data.name,
                "party_type": data.party_type,
                "party": data.party,
                "against_voucher_type": doc.doctype,
                "against_voucher": doc.name,
            },
        )
    )

    # expense entries
    expense_account_currency = get_account_currency(data.expense_account)
    gl_entry.append(
        get_gl_dict(
            doc,
            data,
            {
                "account": data.expense_account,
                "debit": data.request_amount,
                "debit_in_account_currency": data.request_amount
                if expense_account_currency == company_currency
                else data.request_amount / data.conversion_rate,
                "against": data.name,
                "cost_center": data.cost_center,
                "against_voucher_type": doc.doctype,
                "against_voucher": doc.name,
            },
        )
    )

    return gl_entry


def get_gl_dict(doc, data, args, account_currency=None):
    """this method populates the common properties of a gl entry record"""

    fiscal_years = get_fiscal_years(data.request_date)
    if len(fiscal_years) > 1:
        frappe.throw(
            _(
                "Multiple fiscal years exist for the date {0}."
            ).format(data.posting_date)
        )
    else:
        fiscal_year = fiscal_years[0][0]

    gl_dict = frappe._dict(
        {
            "posting_date": data.posting_date,
            "fiscal_year": fiscal_year,
            "voucher_type": doc.doctype,
            "voucher_no": doc.name,
            "remarks": data.get("remarks"),
            "debit": 0,
            "credit": 0,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": 0,
            "is_opening": "No",
            "party_type": None,
            "party": None,
            "project": data.get("project"),
        }
    )
    gl_dict.update(args)

    company_currency = frappe.db.get_value("Currency", {"enabled": 1}, "name") or "USD"

    if not account_currency:
        account_currency = get_account_currency(gl_dict.account)

    if gl_dict.account and doc.doctype not in [
        "Journal Entry",
        "Period Closing Voucher",
        "Payment Entry",
    ]:

        # self.validate_account_currency(gl_dict.account, account_currency)
        set_balance_in_account_currency(
            gl_dict, account_currency, data.get("conversion_rate"), company_currency
        )

    return gl_dict


def make_gl_entries(
    gl_map,
    cancel=False,
    adv_adj=False,
    merge_entries=True,
    update_outstanding="Yes",
    from_repost=False,
):
    if gl_map:
        if not cancel:
            gl_map = process_gl_map(gl_map, merge_entries)
            if gl_map and len(gl_map) > 1:
                save_entries(gl_map, adv_adj, update_outstanding, from_repost)
            else:
                frappe.throw(
                    _(
                        "Incorrect number of General Ledger Entries found. You might have selected a wrong Account in the transaction."
                    )
                )
        else:
            delete_gl_entries(
                gl_map, adv_adj=adv_adj, update_outstanding=update_outstanding
            )


def delete_gl_entries(
    gl_entries=None,
    voucher_type=None,
    voucher_no=None,
    adv_adj=False,
    update_outstanding="Yes",
):

    if not gl_entries:
        gl_entries = frappe.db.sql(
            """
			select account, posting_date, party_type, party, cost_center, fiscal_year,voucher_type,
			voucher_no, against_voucher_type, against_voucher, cost_center, company
			from `tabGL Entry`
			where voucher_type=%s and voucher_no=%s""",
            (voucher_type, voucher_no),
            as_dict=True,
        )

    if gl_entries:
        check_freezing_date(gl_entries[0]["posting_date"], adv_adj)

    for entry in gl_entries:
        frappe.db.sql(
            """delete from `tabGL Entry` where voucher_type=%s and voucher_no=%s AND against=%s""",
            (entry.voucher_type, entry.voucher_no, entry.against),
        )

        validate_frozen_account(entry["account"], adv_adj)
        validate_balance_type(entry["account"], adv_adj)
        if not adv_adj:
            validate_expense_against_budget(entry)

        if entry.get("against_voucher") and update_outstanding == "Yes" and not adv_adj:
            update_outstanding_amt(
                entry["account"],
                entry.get("party_type"),
                entry.get("party"),
                entry.get("against_voucher_type"),
                entry.get("against_voucher"),
                on_cancel=True,
            )


def update_payment_status(doc):
    # Total approved: sum from child rows (Ledger Entry path for Trip rows)
    total_from_rows = flt(frappe.db.sql(
        """SELECT IFNULL(SUM(request_amount), 0) as total
        FROM `tabRequested Fund Details`
        WHERE parent = %s AND parenttype = %s AND request_status = 'Accounts Approved'""",
        (doc.reference_docname, doc.reference_doctype),
        as_dict=1,
    )[0].total)

    # Backward compat: GL-entry based total (non-Trip legacy rows)
    total_from_gl = flt(frappe.db.sql(
        """SELECT IFNULL(SUM(credit_in_account_currency), 0) as total
        FROM `tabGL Entry`
        WHERE against_voucher_type = 'Requested Payment' AND against_voucher = %s""",
        (doc.name,),
        as_dict=1,
    )[0].total)

    total_approved = total_from_rows if total_from_rows > 0 else total_from_gl

    # Paid amount from Payment Entry GL entries referencing this Requested Payment
    paid_amount = flt(frappe.db.sql(
        """SELECT IFNULL(SUM(debit_in_account_currency), 0) as amt
        FROM `tabGL Entry`
        WHERE against_voucher_type = 'Requested Payment' AND against_voucher = %s
          AND voucher_type <> 'Requested Payment'""",
        (doc.name,),
        as_dict=1,
    )[0].amt)

    if total_approved <= 0:
        return
    if paid_amount >= total_approved:
        frappe.db.set_value("Requested Payment", doc.name, "payment_status", "Paid")
    else:
        frappe.db.set_value("Requested Payment", doc.name, "payment_status", "Waiting Payment")


@frappe.whitelist(allow_guest=True)
def reference_payment(**args):
    args = frappe._dict(args)

    request = frappe.new_doc("Reference Payments Table")
    request.update(
        {
            "parent": args.parent,
            "parentfield": args.parentfield,
            "parenttype": args.parenttype,
            "date_of_payment": args.date_of_payment,
            "accounting_system": args.accounting_system,
            "amount": args.amount,
            "currency": args.currency,
            "reference_no": args.reference_no,
            "status": "paid",
        }
    )
    request.insert(ignore_permissions=True)

    parent = frappe.get_doc("Requested Payment", args.parent)
    parent.db_set("payment_status", args.payment_status)
    return "inserted"


@frappe.whitelist()
def get_expense_claim_account(expense_claim_type=None, company=None):
    account = frappe.db.get_value("Fixed Expenses", expense_claim_type, "expense_account")
    return {"account": account}


@frappe.whitelist(allow_guest=True)
def make_payment(source_name, target_doc=None, ignore_permissions=False):
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Pay"
    pe.posting_date = nowdate()
    pe.mode_of_payment = "Cash"
    pe.party_type = "Driver"
    pe.allocate_payment_amount = 1

    return pe


@frappe.whitelist(allow_guest=True)
def approve_request(**args):
    args = frappe._dict(args)
    ts = time.time()
    timestamp = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    doc = frappe.get_doc("Requested Fund Details", args.request_docname)
    doc.db_set("request_status", "Approved")
    doc.db_set("approved_by", args.user)
    doc.db_set("approved_date", timestamp)

    # Auto-fill expense_account from Fixed Expenses master if missing
    if doc.expense_type and not doc.expense_account:
        fe = frappe.db.get_value(
            "Fixed Expenses", doc.expense_type,
            ["expense_account", "cash_bank_account"], as_dict=True
        )
        if fe and fe.expense_account:
            doc.db_set("expense_account", fe.expense_account)
            doc.expense_account = fe.expense_account

    # Auto-set posting_date to today if missing
    if not doc.posting_date:
        doc.db_set("posting_date", nowdate())
        doc.posting_date = nowdate()

    # If all accounting fields are ready, auto-create the ledger/GL entry immediately
    parent_doctype = args.get("parent_doctype")
    parent_docname = args.get("parent_docname")

    if doc.expense_account and doc.payable_account:
        try:
            if doc.parenttype == "Trips":
                # Trip expense rows: create a proper Ledger Entry document
                from vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips import _make_expense_ledger_entry
                _make_expense_ledger_entry(doc, approved_by=args.user)
            elif parent_doctype and parent_docname:
                # Non-Trip rows (legacy): create GL entries directly
                gl_entries = get_gl_entries(doc, parent_doctype, parent_docname)
                make_gl_entries(gl_entries)
                doc.db_set("request_status", "Accounts Approved")
                doc.db_set("request_hidden_status", "1")
                doc.db_set("accounts_approved_by", args.user)
                doc.db_set("accounts_approved_on", timestamp)

            if parent_doctype == "Requested Payment" and parent_docname:
                parent = frappe.get_doc("Requested Payment", parent_docname)
                update_payment_status(parent)
        except Exception as e:
            error_msg = str(e)
            frappe.log_error(
                "Auto accounting entry failed for {0}: {1}".format(doc.name, error_msg),
                "Approve Request Ledger"
            )
            # Show a visible warning — row stays at "Approved" so accounts team can complete it
            frappe.msgprint(
                _("Expense row <b>{0}</b> approved, but the Ledger Entry could not be created automatically:"
                  "<br><br><i>{1}</i><br><br>"
                  "Please open the Accounts Approval tab to complete the accounting step.").format(
                    doc.name, error_msg
                ),
                indicator="orange",
                title=_("Partial Approval — Accounts Step Pending"),
            )

    return "Request Updated"


@frappe.whitelist(allow_guest=True)
def reject_request(**args):
    args = frappe._dict(args)
    ts = time.time()
    timestamp = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    doc = frappe.get_doc("Requested Fund Details", args.request_docname)
    doc.db_set("request_status", "Rejected")
    doc.db_set("approved_by", args.user)
    doc.db_set("approved_date", timestamp)
    return "Request Updated"


@frappe.whitelist()
def create_payment_for_rows(parent_docname, selected_rows, cash_bank_account, mode_of_payment="Cash"):
    """Create a Payment Entry for each selected Accounts-Approved fund row.
    Delegates to the Payment Entry doctype which creates the GL entries on submit."""
    from vsd_fleet_ms.vsd_fleet_ms.doctype.payment_entry.payment_entry import (
        create_fund_payment_entry,
    )
    return create_fund_payment_entry(
        parent_docname=parent_docname,
        row_names=selected_rows,
        cash_bank_account=cash_bank_account,
        mode_of_payment=mode_of_payment,
    )
