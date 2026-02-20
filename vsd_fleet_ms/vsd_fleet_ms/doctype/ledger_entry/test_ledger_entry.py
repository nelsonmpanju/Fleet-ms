# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate


EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestLedgerEntry(IntegrationTestCase):
	doctype = None

	def test_submit_and_cancel_updates_status(self):
		currency = ensure_currency()
		income_account = ensure_account("Income", currency)

		doc = frappe.get_doc(
			{
				"doctype": "Ledger Entry",
				"posting_date": nowdate(),
				"entry_type": "Income",
				"source_type": "Manual",
				"account": income_account,
				"currency": currency,
				"amount": 250,
				"description": "Test Income",
			}
		)
		doc.insert()
		doc.submit()
		doc.reload()
		self.assertEqual(doc.status, "Submitted")

		doc.cancel()
		doc.reload()
		self.assertEqual(doc.status, "Cancelled")

	def test_account_type_must_match_entry_type(self):
		currency = ensure_currency()
		income_account = ensure_account("Income", currency)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Ledger Entry",
					"posting_date": nowdate(),
					"entry_type": "Expense",
					"source_type": "Manual",
					"account": income_account,
					"currency": currency,
					"amount": 10,
				}
			).insert()


def unique_name(prefix):
	return f"{prefix}-{frappe.generate_hash(length=6).upper()}"


def ensure_currency():
	currency = "USD"
	if not frappe.db.exists("Currency", currency):
		frappe.get_doc(
			{"doctype": "Currency", "currency_name": currency, "symbol": "$", "enabled": 1}
		).insert()
	return currency


def ensure_account(account_type: str, currency: str):
	name = unique_name("ACC")
	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": name,
			"account_type": account_type,
			"account_currency": currency,
			"is_group": 0,
		}
	)
	doc.insert()
	return doc.name
