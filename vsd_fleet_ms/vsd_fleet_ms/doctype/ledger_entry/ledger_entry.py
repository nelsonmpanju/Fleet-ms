from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate

from vsd_fleet_ms.vsd_fleet_ms.doctype.account.account import ensure_posting_account
from vsd_fleet_ms.utils.accounting import get_company_currency, get_exchange_rate

# Account type expected for each entry type (Income/Expense only)
_ACCOUNT_TYPE_BY_ENTRY = {
	"Income": "Income",
	"Expense": "Expense",
}

# Account types that carry a Debit (normal) balance
_DEBIT_BALANCE_TYPES = {"Asset", "Expense"}

# The equity account used to absorb opening-balance entries
_OB_EQUITY_ACCOUNT = "Opening Balance Equity"


class LedgerEntry(Document):
	def autoname(self):
		self.name = make_autoname("LED-.#####")

	# ── lifecycle ──────────────────────────────────────────────────────────────

	def validate(self):
		self.set_defaults()
		self.validate_amount()
		self.validate_accounts()
		self.validate_reference()
		self.validate_trip_expense_link()

	def on_submit(self):
		self.db_set("status", "Submitted")
		self._post_gl_entries()

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		self._cancel_gl_entries()

	# ── validation helpers ─────────────────────────────────────────────────────

	def set_defaults(self):
		if not self.posting_date:
			self.posting_date = nowdate()
		if not self.currency:
			self.currency = get_company_currency()
		if not self.source_type:
			self.source_type = "Manual"
		if not self.status:
			self.status = "Draft"
		self.amount = flt(self.amount)
		company_currency = get_company_currency()
		if not flt(self.conversion_rate):
			self.conversion_rate = get_exchange_rate(
				self.currency, company_currency, self.posting_date
			)

	def validate_amount(self):
		if self.amount <= 0:
			frappe.throw(_("Amount must be greater than zero."))

	def validate_accounts(self):
		if not self.account:
			return

		# Main account must be a posting (non-group) account
		main = ensure_posting_account(self.account, _("Account"))
		account_type = main.get("account_type")

		if self.entry_type in ("Income", "Expense"):
			expected = _ACCOUNT_TYPE_BY_ENTRY[self.entry_type]
			if account_type and account_type != expected:
				frappe.throw(
					_("{0} is a {1} account. {2} entries require a {3} account.").format(
						frappe.bold(self.account), account_type,
						self.entry_type, expected,
					)
				)
			if not self.contra_account:
				frappe.throw(
					_("Contra Account is required. Select the cash/bank account for this {0} entry.").format(
						self.entry_type.lower()
					)
				)
			ensure_posting_account(self.contra_account, _("Contra Account"))

		elif self.entry_type == "Payment":
			# Payment: account = Cash/Bank, contra_account = AR (Receive) or AP (Pay)
			# debit_credit = "Debit" → Receive (DR Cash/Bank, CR AR)
			# debit_credit = "Credit" → Pay (DR AP, CR Cash/Bank)
			if not self.contra_account:
				frappe.throw(_("Contra Account is required for Payment entries."))
			ensure_posting_account(self.contra_account, _("Contra Account"))
			if not self.debit_credit:
				frappe.throw(_("Direction (Debit/Credit) is required for Payment entries."))

		elif self.entry_type == "Opening Balance":
			# Auto-set Debit/Credit flag based on account type
			if not self.debit_credit:
				self.debit_credit = "Debit" if account_type in _DEBIT_BALANCE_TYPES else "Credit"
			self._ensure_ob_equity_account()

	def validate_reference(self):
		if bool(self.reference_doctype) != bool(self.reference_name):
			frappe.throw(_("Reference DocType and Reference Document must both be set."))

	def validate_trip_expense_link(self):
		if not self.reference_trip_expense:
			return

		expense_row = frappe.db.get_value(
			"Requested Fund Details",
			self.reference_trip_expense,
			["parenttype", "parent", "request_status", "request_currency"],
			as_dict=True,
		)
		if not expense_row:
			frappe.throw(_("Trip expense row {0} was not found.").format(self.reference_trip_expense))
		if expense_row.parenttype != "Trips":
			frappe.throw(_("Trip expense link must point to a row inside Trips."))

		if self.reference_trip and self.reference_trip != expense_row.parent:
			frappe.throw(
				_("Trip expense row {0} belongs to trip {1}, not {2}.").format(
					self.reference_trip_expense, expense_row.parent, self.reference_trip
				)
			)

		self.reference_trip = expense_row.parent
		self.reference_doctype = "Trips"
		self.reference_name = expense_row.parent

		if self.entry_type != "Expense":
			frappe.throw(_("Only Expense entries can be linked to Trip Expenses."))
		if expense_row.request_status not in ("Approved", "Accounts Approved"):
			frappe.throw(_("Trip expense row must be Approved before creating a ledger entry."))
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
				_("Ledger Entry {0} is already linked to Trip Expense {1}.").format(
					existing[0], self.reference_trip_expense
				)
			)

	# ── double-entry GL posting ────────────────────────────────────────────────

	def _post_gl_entries(self):
		"""Create the two GL Entry records that complete the double-entry."""
		if frappe.db.exists("GL Entry", {"voucher_type": "Ledger Entry", "voucher_no": self.name}):
			return  # Already posted (safety guard against duplicate submission)

		# Sync the GLE-. series counter with the actual table max.
		# Prevents "Duplicate Name" errors when the counter falls behind
		# (e.g. after manual row deletions during testing/setup).
		max_num = (
			frappe.db.sql(
				"SELECT IFNULL(MAX(CAST(REPLACE(name,'GLE-','') AS UNSIGNED)), 0) AS mx"
				" FROM `tabGL Entry` WHERE name REGEXP '^GLE-[0-9]+$'",
			)[0][0]
			or 0
		)
		frappe.db.sql(
			"INSERT INTO `tabSeries` (name, current) VALUES ('GLE-.', %s)"
			" ON DUPLICATE KEY UPDATE current = GREATEST(current, %s)",
			(max_num, max_num),
		)

		debit_acct, credit_acct = self._resolve_debit_credit_accounts()
		party_acct = self._resolve_party_account()
		txn_amount = flt(self.amount)          # amount in transaction (document) currency
		company_currency = get_company_currency()
		txn_currency = self.currency or company_currency
		conversion_rate = flt(self.conversion_rate) or 1

		# GL debit/credit are ALWAYS in company currency
		if txn_currency == company_currency:
			company_amount = txn_amount
		else:
			company_amount = txn_amount * conversion_rate

		for acct, debit, credit in [
			(debit_acct,  company_amount, 0.0),
			(credit_acct, 0.0, company_amount),
		]:
			is_party_acct = party_acct and acct == party_acct
			acct_currency = frappe.db.get_value("Account", acct, "account_currency") or company_currency

			# debit/credit_in_account_currency depends on the account's own currency
			if acct_currency == company_currency:
				# Account is in company currency — same as GL amount
				debit_in_acc = debit
				credit_in_acc = credit
			else:
				# Account is in foreign currency (e.g. USD) — use original txn amount
				debit_in_acc = txn_amount if debit else 0.0
				credit_in_acc = txn_amount if credit else 0.0

			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": acct,
				"debit": debit,
				"credit": credit,
				"debit_in_account_currency": debit_in_acc,
				"credit_in_account_currency": credit_in_acc,
				"account_currency": acct_currency,
				"voucher_type": "Ledger Entry",
				"voucher_no": self.name,
				"against": credit_acct if debit else debit_acct,
				"party_type": self.party_type if is_party_acct else "",
				"party": self.party if is_party_acct else "",
			}).insert(ignore_permissions=True)

	def _cancel_gl_entries(self):
		"""Delete the GL entries posted for this voucher on cancellation."""
		frappe.db.delete("GL Entry", {
			"voucher_type": "Ledger Entry",
			"voucher_no": self.name,
		})

	def _resolve_debit_credit_accounts(self):
		"""
		Determine (debit_account, credit_account) for the double-entry.

		Expense:                DR Expense account   / CR Contra (cash paid from)
		Income:                 DR Contra (received)  / CR Income account
		Opening Balance Debit:  DR Account            / CR Opening Balance Equity
		Opening Balance Credit: DR Opening Balance Equity / CR Account
		"""
		if self.entry_type == "Expense":
			return self.account, self.contra_account

		if self.entry_type == "Income":
			return self.contra_account, self.account

		if self.entry_type == "Payment":
			# Debit  (Receive / Sales Invoice):  DR account (Cash/Bank) / CR contra (AR)
			# Credit (Pay    / Purchase Invoice): DR contra (Payable)   / CR account (Cash/Bank)
			if self.debit_credit == "Debit":
				return self.account, self.contra_account
			return self.contra_account, self.account

		if self.entry_type == "Opening Balance":
			if self.debit_credit == "Debit":
				return self.account, _OB_EQUITY_ACCOUNT
			return _OB_EQUITY_ACCOUNT, self.account

		frappe.throw(_("Unknown entry type: {0}").format(self.entry_type))

	def _resolve_party_account(self):
		"""
		Determine which account should carry the party_type/party.

		Party belongs on the main business account (expense, income, payable,
		receivable) — never on the cash/bank contra account.  This ensures
		GL analysis by party (per driver, per supplier, etc.) only appears
		on the correct account.

		Returns the account name that should get the party, or None if no
		party is set on this Ledger Entry.
		"""
		if not self.party_type and not self.party:
			return None

		if self.entry_type in ("Expense", "Income", "Opening Balance"):
			return self.account
		if self.entry_type == "Payment":
			# Payment: party goes on the receivable/payable (contra_account)
			return self.contra_account
		return None

	def _ensure_ob_equity_account(self):
		"""Auto-create Opening Balance Equity account if missing."""
		if frappe.db.exists("Account", _OB_EQUITY_ACCOUNT):
			return
		if not frappe.db.exists("Account", "Equity"):
			frappe.throw(
				_("Please create an 'Equity' group account before posting opening balances.")
			)
		frappe.get_doc({
			"doctype": "Account",
			"account_name": _OB_EQUITY_ACCOUNT,
			"account_number": "3300",
			"parent_account": "Equity",
			"is_group": 0,
			"account_type": "Equity",
			"description": "System account — absorbs opening balance entries during initial setup.",
		}).insert(ignore_permissions=True)
		frappe.db.commit()
