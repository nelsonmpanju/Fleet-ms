from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.nestedset import NestedSet, rebuild_tree, update_nsm


class Account(NestedSet):
    nsm_parent_field = "parent_account"

    def autoname(self):
        if not self.account_name:
            frappe.throw(_("Account Name is required."))
        self.name = self.account_name

    def validate(self):
        self.ensure_parent_is_group()
        self.set_defaults()
        self.ensure_account_type_consistency()

    def on_update(self):
        NestedSet.on_update(self)

    def on_trash(self):
        NestedSet.validate_if_child_exists(self)
        update_nsm(self)

    def ensure_parent_is_group(self):
        if not self.parent_account:
            return

        parent_is_group = cint(frappe.db.get_value("Account", self.parent_account, "is_group") or 0)
        if not parent_is_group:
            frappe.throw(_("Parent Account must be a group account."))

    def set_defaults(self):
        if not self.account_currency:
            self.account_currency = frappe.db.get_value("Currency", {"enabled": 1}, "name") or "USD"

    def ensure_account_type_consistency(self):
        if not self.parent_account:
            if not self.account_type:
                frappe.throw(_("Account Type is required for root accounts."))
            return

        parent_type = frappe.db.get_value("Account", self.parent_account, "account_type")
        if parent_type:
            if not self.account_type:
                self.account_type = parent_type
            elif self.account_type != parent_type:
                frappe.throw(
                    _("Account Type must match parent account type ({0}).").format(parent_type)
                )


def get_account_details(account: str):
    if not account:
        return frappe._dict()

    data = frappe.db.get_value(
        "Account", account, ["name", "is_group", "account_type", "account_currency"], as_dict=True
    )
    if not data:
        frappe.throw(_("Account {0} was not found.").format(account))
    return frappe._dict(data)


def ensure_posting_account(account: str, label: str = "Account"):
    details = get_account_details(account)
    if cint(details.get("is_group")):
        frappe.throw(_("{0} {1} is a group account and cannot be used for posting.").format(label, account))
    return details


@frappe.whitelist()
def get_children(doctype, parent=None, account=None, is_root=False):
    if parent in (None, "All Accounts"):
        parent = ""

    return frappe.db.sql(
        """
        select
            name as value,
            is_group as expandable
        from `tabAccount`
        where ifnull(parent_account, '') = %(parent)s
        order by account_name asc
        """,
        {"parent": parent},
        as_dict=1,
    )


@frappe.whitelist()
def add_node():
    from frappe.desk.treeview import make_tree_args

    args = make_tree_args(**frappe.form_dict)
    if args.parent_account == "All Accounts":
        args.parent_account = None

    frappe.get_doc(args).insert()


def on_doctype_update():
    frappe.db.add_index("Account", ["lft", "rgt"])
    rebuild_tree("Account")
