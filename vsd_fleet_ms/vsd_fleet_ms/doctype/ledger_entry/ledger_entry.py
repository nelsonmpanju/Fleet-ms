from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate

from vsd_fleet_ms.vsd_fleet_ms.doctype.account.account import ensure_posting_account

ACCOUNT_TYPE_BY_ENTRY = {
	"Income": "Income",
	"Expense": "Expense",
}


class LedgerEntry(Document):
	def autoname(self):
		self.name = make_autoname("LED-.#####")

	def validate(self):
		self.set_defaults()
		self.validate_amount()
		self.validate_reference()
		self.validate_account_type()
		self.validate_trip_expense_link()

	def on_submit(self):
		self.db_set("status", "Submitted")

	def on_cancel(self):
		self.db_set("status", "Cancelled")

	def set_defaults(self):
		if not self.posting_date:
			self.posting_date = nowdate()

		if not self.currency:
			self.currency = frappe.db.get_value("Currency", {"enabled": 1}, "name") or "USD"

		if not self.source_type:
			self.source_type = "Manual"

		if not self.status:
			self.status = "Draft"

		self.amount = flt(self.amount)

	def validate_amount(self):
		if self.amount <= 0:
			frappe.throw("Amount must be greater than zero.")

	def validate_account_type(self):
		if not self.account:
			return

		account_details = ensure_posting_account(self.account, "Account")
		account_type = account_details.get("account_type")
		if not account_type:
			return

		expected_type = ACCOUNT_TYPE_BY_ENTRY.get(self.entry_type)
		if expected_type and account_type != expected_type:
			frappe.throw(
				f"Account {self.account} is {account_type}. "
				f"{self.entry_type} entries require an {expected_type} account."
			)

	def validate_reference(self):
		if bool(self.reference_doctype) != bool(self.reference_name):
			frappe.throw("Reference DocType and Reference Document must both be set.")

	def validate_trip_expense_link(self):
		if not self.reference_trip_expense:
			return

		expense_row = frappe.db.get_value(
			"Requested Fund Details",
			self.reference_trip_expense,
			["parenttype", "parent", "request_status", "request_amount", "request_currency"],
			as_dict=True,
		)
		if not expense_row:
			frappe.throw(f"Trip expense row {self.reference_trip_expense} was not found.")
		if expense_row.parenttype != "Trips":
			frappe.throw("Trip expense link must point to a row inside Trips.")

		if self.reference_trip and self.reference_trip != expense_row.parent:
			frappe.throw(
				f"Trip expense row {self.reference_trip_expense} belongs to trip "
				f"{expense_row.parent}, not {self.reference_trip}."
			)
		self.reference_trip = expense_row.parent
		self.reference_doctype = "Trips"
		self.reference_name = expense_row.parent

		if self.entry_type != "Expense":
			frappe.throw("Only Expense ledger entries can be linked to Trip Expenses.")

		if expense_row.request_status != "Approved":
			frappe.throw("Trip expense row must be Approved before creating a ledger entry.")

		if not self.currency:
			self.currency = expense_row.request_currency

		existing = frappe.get_all(
			"Ledger Entry",
			filters={
				"reference_trip_expense": self.reference_trip_expense,
				"docstatus": ["!=", 2],
				"name": ["!=", self.name],
			},
			pluck="name",
			limit=1,
		)
		if existing:
			frappe.throw(
				f"Ledger Entry {existing[0]} is already linked to Trip Expense "
				f"{self.reference_trip_expense}."
			)
