# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, nowdate

from vsd_fleet_ms.vsd_fleet_ms.doctype.payment_entry.payment_entry import (
	create_payment_entry_for_sales_invoice,
)


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestSalesInvoice(IntegrationTestCase):
	"""
	Integration tests for SalesInvoice.
	Use this class for testing interactions between multiple components.
	"""

	def test_sales_payment_submit_and_cancel_updates_invoice(self):
		uom = ensure_uom()
		customer = ensure_customer()
		income_account = ensure_account("Income", "USD")
		service_item = ensure_item(
			is_stock_item=0, stock_uom=uom, standard_rate=150, income_account=income_account
		)

		sales_invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"posting_date": nowdate(),
				"income_account": income_account,
				"items": [
					{
						"item_code": service_item,
						"qty": 1,
						"uom": uom,
						"rate": 150,
						"income_account": income_account,
					}
				],
			}
		)
		sales_invoice.insert()
		sales_invoice.submit()
		sales_invoice.reload()
		self.assertEqual(flt(sales_invoice.outstanding_amount), flt(sales_invoice.grand_total))
		self.assertTrue(sales_invoice.ledger_entry)

		ledger_entry = frappe.get_doc("Ledger Entry", sales_invoice.ledger_entry)
		self.assertEqual(ledger_entry.docstatus, 1)
		self.assertEqual(ledger_entry.source_type, "Sales Invoice")
		self.assertEqual(flt(ledger_entry.amount), flt(sales_invoice.grand_total))

		payment_name = create_payment_entry_for_sales_invoice(sales_invoice.name)
		payment_entry = frappe.get_doc("Payment Entry", payment_name)
		payment_entry.submit()

		sales_invoice.reload()
		self.assertEqual(flt(sales_invoice.outstanding_amount), 0)
		self.assertEqual(sales_invoice.payment_status, "Paid")
		self.assertEqual(sales_invoice.status, "Paid")

		payment_entry.cancel()
		sales_invoice.reload()
		self.assertEqual(flt(sales_invoice.outstanding_amount), flt(sales_invoice.grand_total))
		self.assertEqual(sales_invoice.payment_status, "Unpaid")
		self.assertEqual(sales_invoice.status, "Submitted")

	def test_sales_invoice_cancel_cancels_linked_ledger_entry(self):
		uom = ensure_uom()
		customer = ensure_customer()
		income_account = ensure_account("Income", "USD")
		service_item = ensure_item(
			is_stock_item=0, stock_uom=uom, standard_rate=180, income_account=income_account
		)

		sales_invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"posting_date": nowdate(),
				"income_account": income_account,
				"items": [
					{
						"item_code": service_item,
						"qty": 1,
						"uom": uom,
						"rate": 180,
						"income_account": income_account,
					}
				],
			}
		)
		sales_invoice.insert()
		sales_invoice.submit()
		ledger_name = sales_invoice.ledger_entry
		self.assertTrue(ledger_name)

		sales_invoice.cancel()
		ledger_entry = frappe.get_doc("Ledger Entry", ledger_name)
		self.assertEqual(ledger_entry.docstatus, 2)


def unique_name(prefix):
	return f"{prefix}-{frappe.generate_hash(length=6).upper()}"


def ensure_uom():
	uom_name = f"UOM-{frappe.generate_hash(length=6).upper()}"
	doc = frappe.get_doc({"doctype": "UOM", "uom_name": uom_name, "enabled": 1})
	doc.insert()
	return doc.name


def ensure_customer():
	name = unique_name("CUS")
	doc = frappe.get_doc({"doctype": "Customer", "customer_name": name})
	doc.insert()
	return doc.name


def ensure_item(*, is_stock_item: int, stock_uom: str, standard_rate: float, income_account: str):
	code = unique_name("ITEM")
	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": code,
			"is_stock_item": is_stock_item,
			"stock_uom": stock_uom,
			"standard_rate": standard_rate,
			"income_account": income_account,
		}
	)
	doc.insert()
	return doc.name


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
