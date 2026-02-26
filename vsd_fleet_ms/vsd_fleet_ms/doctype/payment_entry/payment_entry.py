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
		if self.reference_doctype == "Requested Payment":
			self._create_gl_entries_for_fund_payment(cancel=False)
			self._mark_fund_rows_paid()
		else:
			self.apply_against_reference(is_cancel=False)
			self._create_payment_ledger_entry()
		self.db_set("status", "Submitted")

	def on_cancel(self):
		if self.reference_doctype == "Requested Payment":
			self._create_gl_entries_for_fund_payment(cancel=True)
			self._unmark_fund_rows_paid()
		else:
			self._cancel_payment_ledger_entry()
			self.apply_against_reference(is_cancel=True)
		self.db_set("status", "Cancelled")

	def set_defaults(self):
		if not self.posting_date:
			self.posting_date = nowdate()
		if not self.status:
			self.status = "Draft"
		if not self.currency:
			self.currency = frappe.db.get_value("Currency", {"enabled": 1}, "name") or "TZS"
		self.paid_amount = flt(self.paid_amount)

	def validate_amount(self):
		if flt(self.paid_amount) <= 0:
			frappe.throw("Paid Amount must be greater than zero.")

	def validate_reference(self):
		if bool(self.reference_doctype) != bool(self.reference_name):
			frappe.throw("Reference DocType and Reference Document must both be set.")

		if not self.reference_doctype:
			return

		# Fund payment via Requested Payment
		if self.reference_doctype == "Requested Payment":
			if not frappe.db.exists("Requested Payment", self.reference_name):
				frappe.throw(f"Requested Payment {self.reference_name} was not found.")
			if not self.payable_account:
				frappe.throw("Payable Account is required for fund payment.")
			if not self.cash_bank_account:
				frappe.throw("Cash / Bank Account is required for fund payment.")
			return

		config = INVOICE_CONFIG.get(self.reference_doctype)
		if not config:
			frappe.throw("Reference DocType must be Sales Invoice, Purchase Invoice, or Requested Payment.")

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

	# ─── GL entries for fund disbursement ───────────────────────────────────────

	def _create_gl_entries_for_fund_payment(self, cancel=False):
		"""
		On submit: Payable Dr / Cash Cr  (clearing the payable recognised at accounts-approval)
		On cancel: reverse the above
		"""
		if not self.payable_account or not self.cash_bank_account:
			return

		posting_date = str(self.posting_date)
		fiscal_year = posting_date[:4]

		def _make_entry(account, debit, credit, party_type=None, party=None):
			return frappe._dict({
				"posting_date": posting_date,
				"fiscal_year": fiscal_year,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"account": account,
				"party_type": party_type,
				"party": party,
				"debit": flt(debit),
				"credit": flt(credit),
				"debit_in_account_currency": flt(debit),
				"credit_in_account_currency": flt(credit),
				"against_voucher_type": self.reference_doctype,
				"against_voucher": self.reference_name,
				"remarks": self.remarks or f"Payment against {self.reference_name}",
				"is_opening": "No",
			})

		amount = flt(self.paid_amount)

		if not cancel:
			entries = [
				# Debit the payable account (clear the liability created on accounts approval)
				_make_entry(self.payable_account, amount, 0, self.party_type, self.party),
				# Credit the cash/bank account (actual outflow)
				_make_entry(self.cash_bank_account, 0, amount),
			]
		else:
			# Reverse on cancel
			entries = [
				_make_entry(self.payable_account, 0, amount, self.party_type, self.party),
				_make_entry(self.cash_bank_account, amount, 0),
			]

		for entry in entries:
			gl = frappe.new_doc("GL Entry")
			gl.update(entry)
			gl.flags.ignore_permissions = True
			gl.insert(ignore_permissions=True)

		# Trigger payment status recalculation on the parent Requested Payment
		try:
			from vsd_fleet_ms.vsd_fleet_ms.doctype.requested_payment.requested_payment import (
				update_payment_status,
			)
			req_pay = frappe.get_doc("Requested Payment", self.reference_name)
			update_payment_status(req_pay)
		except Exception:
			pass

	def _mark_fund_rows_paid(self):
		"""Link this Payment Entry back to the fund rows it pays for."""
		# Find rows with this PE linked via payment_entry field or update by parent
		frappe.db.sql(
			"""UPDATE `tabRequested Fund Details`
			SET journal_entry = %s
			WHERE parent = %s
			  AND parenttype IN ('Trips','Manifest')
			  AND request_status = 'Accounts Approved'
			  AND (journal_entry IS NULL OR journal_entry = '')""",
			(self.name, self._get_reference_docname()),
		)

	def _unmark_fund_rows_paid(self):
		frappe.db.sql(
			"""UPDATE `tabRequested Fund Details`
			SET journal_entry = NULL
			WHERE journal_entry = %s""",
			(self.name,),
		)

	def _get_reference_docname(self):
		"""Return the trip/manifest name that the Requested Payment points to."""
		ref = frappe.db.get_value(
			"Requested Payment", self.reference_name, "reference_docname"
		)
		return ref or self.reference_name

	# ─── Invoice reference (original logic, unchanged) ──────────────────────────

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

	# ─── Payment Ledger Entry (GL posting for invoice payments) ─────────────────

	def _create_payment_ledger_entry(self):
		"""
		Create a Ledger Entry of type 'Payment' that posts the two GL entries:
		  Sales Invoice (Receive):  DR Cash/Bank  /  CR Receivable (AR)
		  Purchase Invoice (Pay):   DR Payable     /  CR Cash/Bank
		"""
		if self.reference_doctype not in ("Sales Invoice", "Purchase Invoice"):
			return

		if not self.cash_bank_account:
			frappe.throw(
				"Cash / Bank Account is required on the Payment Entry to post GL entries. "
				"Please set the Cash / Bank Account field."
			)
		if not self.payable_account:
			frappe.throw(
				"Receivable / Payable Account is required on the Payment Entry to post GL entries. "
				"Please set the Payable Account field."
			)

		amount = flt(self.paid_amount)
		if amount <= 0:
			return

		# Receive (Sales Invoice):  Debit  → DR account (Cash/Bank) / CR contra (AR)
		# Pay    (Purchase Invoice): Credit → DR contra (Payable)   / CR account (Cash/Bank)
		is_receive = self.reference_doctype == "Sales Invoice"
		debit_credit = "Debit" if is_receive else "Credit"
		party_type = "Customer" if is_receive else "Supplier"

		ledger_doc = frappe.get_doc({
			"doctype": "Ledger Entry",
			"posting_date": self.posting_date,
			"entry_type": "Payment",
			"source_type": "Payment Entry",
			"account": self.cash_bank_account,
			"contra_account": self.payable_account,
			"debit_credit": debit_credit,
			"party_type": party_type,
			"party": self.party,
			"currency": self.currency,
			"amount": amount,
			"reference_doctype": "Payment Entry",
			"reference_name": self.name,
			"reference_trip": self.trip or None,
			"remarks": self.remarks or f"Payment against {self.reference_doctype} {self.reference_name}",
		})
		ledger_doc.flags.ignore_permissions = True
		ledger_doc.insert(ignore_permissions=True)
		ledger_doc.submit()
		self.db_set("ledger_entry", ledger_doc.name, update_modified=False)

	def _cancel_payment_ledger_entry(self):
		"""Cancel the Ledger Entry linked to this Payment Entry (reverses GL entries)."""
		if not self.ledger_entry:
			return
		if not frappe.db.exists("Ledger Entry", self.ledger_entry):
			self.db_set("ledger_entry", "", update_modified=False)
			return
		ledger_doc = frappe.get_doc("Ledger Entry", self.ledger_entry)
		ledger_doc.flags.ignore_permissions = True
		if ledger_doc.docstatus == 1:
			ledger_doc.cancel()


@frappe.whitelist()
def create_payment_entry_for_sales_invoice(sales_invoice: str) -> str:
	return _create_payment_entry_for_invoice("Sales Invoice", sales_invoice)


@frappe.whitelist()
def create_payment_entry_for_purchase_invoice(purchase_invoice: str) -> str:
	return _create_payment_entry_for_invoice("Purchase Invoice", purchase_invoice)


def _create_payment_entry_for_invoice(reference_doctype: str, reference_name: str) -> str:
	config = INVOICE_CONFIG[reference_doctype]
	fetch_fields = [config["party_field"], "currency", "docstatus", "outstanding_amount"]
	# Fetch payable/receivable account if the field exists on the invoice
	if reference_doctype == "Purchase Invoice":
		fetch_fields.append("payable_account")
	elif reference_doctype == "Sales Invoice":
		fetch_fields.append("receivable_account")

	reference = frappe.db.get_value(
		reference_doctype,
		reference_name,
		fetch_fields,
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
	# Pre-fill the ledger account so the user can see it on the Payment Entry form
	if reference_doctype == "Purchase Invoice" and reference.get("payable_account"):
		payment_entry.payable_account = reference.payable_account
	elif reference_doctype == "Sales Invoice" and reference.get("receivable_account"):
		payment_entry.payable_account = reference.receivable_account
	payment_entry.insert(ignore_permissions=True)
	return payment_entry.name


def _do_accounts_approval_gl(row, parent_doc):
	"""
	Inline accounts-approval step: create Expense Dr / Payable Cr entries and
	mark the row as Accounts Approved. Called when a row is only manager-
	Approved (accounts team hasn't clicked the separate Accounts Approval button).

	Trip rows use a Ledger Entry document (proper audit trail).
	Non-Trip legacy rows create GL entries directly.
	"""
	if row.parenttype == "Trips":
		# Trip expense rows: create a Ledger Entry for full traceability
		from vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips import _make_expense_ledger_entry
		_make_expense_ledger_entry(row)
	else:
		from vsd_fleet_ms.vsd_fleet_ms.doctype.requested_payment.requested_payment import (
			get_gl_entries,
			make_gl_entries,
		)
		gl_entries = get_gl_entries(row, parent_doc.doctype, parent_doc.name)
		make_gl_entries(gl_entries)
		row.db_set("request_status", "Accounts Approved")
		row.db_set("request_hidden_status", "1")


@frappe.whitelist()
def create_fund_payment_entry(
	parent_docname: str,
	row_names: str,
	cash_bank_account: str,
	mode_of_payment: str = "Cash",
) -> dict:
	"""
	Create one Payment Entry per approved fund row and submit it.
	Called from the 'Make Payment' dialog on Requested Payment.
	"""
	row_names = frappe.parse_json(row_names) if isinstance(row_names, str) else row_names
	parent_doc = frappe.get_doc("Requested Payment", parent_docname)

	# Determine the trip reference (if the Requested Payment is linked to a Trip)
	trip_name = (
		parent_doc.reference_docname
		if parent_doc.reference_doctype == "Trips"
		else None
	)

	created = []
	errors = []

	for row_name in row_names:
		row = frappe.get_doc("Requested Fund Details", row_name)

		if row.request_status not in ("Approved", "Accounts Approved"):
			errors.append(f"{row_name}: status is '{row.request_status}', must be Approved or Accounts Approved")
			continue
		if row.journal_entry:
			errors.append(f"{row_name}: already has a payment entry ({row.journal_entry})")
			continue
		if not row.payable_account:
			errors.append(f"{row_name}: Payable Account is not set — please fill it in the Accounts Approval tab")
			continue

		try:
			# If only manager-Approved (accounts step not done yet), run it inline
			if row.request_status == "Approved":
				if not row.expense_account:
					errors.append(f"{row_name}: Expense Account is not set — please fill it in the Accounts Approval tab")
					continue
				_do_accounts_approval_gl(row, parent_doc)

			pe = frappe.new_doc("Payment Entry")
			pe.payment_type = "Pay"
			pe.posting_date = nowdate()
			pe.mode_of_payment = mode_of_payment
			pe.party_type = row.party_type or "Driver"
			pe.party = row.party
			pe.currency = row.request_currency or (frappe.db.get_value("Currency", {"enabled": 1}, "name") or "TZS")
			pe.paid_amount = flt(row.request_amount)
			pe.payable_account = row.payable_account
			pe.cash_bank_account = cash_bank_account
			pe.reference_doctype = "Requested Payment"
			pe.reference_name = parent_docname
			pe.trip = trip_name
			pe.allocate_payment_amount = 1
			pe.remarks = (
				f"Payment for {row.expense_type or row.request_description or row_name}"
				+ (f" | Trip: {trip_name}" if trip_name else "")
			)
			pe.insert(ignore_permissions=True)
			pe.submit()

			# Link back to the fund row
			frappe.db.set_value("Requested Fund Details", row_name, "journal_entry", pe.name)
			created.append(pe.name)

		except Exception as e:
			errors.append(f"{row_name}: {str(e)}")
			frappe.log_error(frappe.get_traceback(), f"Fund Payment Entry creation failed: {row_name}")

	return {
		"created": len(created),
		"payment_entries": created,
		"errors": errors,
	}


def cint(value) -> int:
	return int(flt(value))
