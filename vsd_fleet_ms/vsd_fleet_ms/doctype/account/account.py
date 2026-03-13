from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.nestedset import NestedSet, rebuild_tree, update_nsm

BALANCE_TYPE_MAP = {
	"Asset": "Debit",
	"Expense": "Debit",
	"Liability": "Credit",
	"Income": "Credit",
	"Equity": "Credit",
}


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
		self.set_balance_type()

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
			from vsd_fleet_ms.utils.accounting import get_company_currency
			self.account_currency = get_company_currency()

	def set_balance_type(self):
		if self.account_type:
			self.balance_type = BALANCE_TYPE_MAP.get(self.account_type, "Debit")

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
		"Account",
		account,
		["name", "is_group", "account_type", "account_currency", "balance_type", "account_number"],
		as_dict=True,
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
def get_children(doctype=None, parent=None, account=None, is_root=False):
	if parent in (None, "All Accounts"):
		parent = ""

	return frappe.db.sql(
		"""
		SELECT
			a.name          AS value,
			a.is_group      AS expandable,
			a.account_type,
			a.account_number,
			a.balance_type,
			IFNULL((
				SELECT SUM(gle.debit - gle.credit)
				FROM   `tabGL Entry` gle
				INNER JOIN `tabAccount` la ON la.name = gle.account
				WHERE  la.lft >= a.lft AND la.rgt <= a.rgt
			), 0) AS balance
		FROM  `tabAccount` a
		WHERE IFNULL(a.parent_account, '') = %(parent)s
		ORDER BY
			CAST(NULLIF(IFNULL(a.account_number, ''), '') AS UNSIGNED) ASC,
			a.account_name ASC
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


@frappe.whitelist()
def get_next_account_number(parent_account):
	"""
	Return the next available account_number for a new child of parent_account.

	Logic:
	  1. Get the parent's own account_number (e.g. "5100").
	  2. Find the maximum numeric child number under that parent.
	  3. Return max + 1, or parent + 1 if no children have numbers yet.
	"""
	if not parent_account or not frappe.db.exists("Account", parent_account):
		return None

	parent_number = frappe.db.get_value("Account", parent_account, "account_number")
	if not parent_number:
		return None

	try:
		parent_int = int(parent_number)
	except (ValueError, TypeError):
		return None

	result = frappe.db.sql(
		"""
		SELECT MAX(CAST(account_number AS UNSIGNED)) AS max_num
		FROM `tabAccount`
		WHERE parent_account = %s
		  AND account_number REGEXP '^[0-9]+$'
		""",
		parent_account,
		as_dict=True,
	)

	max_child = result[0].max_num if result else None
	if max_child:
		return str(int(max_child) + 1)
	return str(parent_int + 1)


def on_doctype_update():
	frappe.db.add_index("Account", ["lft", "rgt"])
	frappe.db.add_index("Account", ["account_number"])
	rebuild_tree("Account")
