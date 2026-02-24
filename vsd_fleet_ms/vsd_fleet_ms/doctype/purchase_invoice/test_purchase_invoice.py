# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, nowdate, nowtime

from vsd_fleet_ms.vsd_fleet_ms.doctype.payment_entry.payment_entry import (
	create_payment_entry_for_purchase_invoice,
)


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestPurchaseInvoice(IntegrationTestCase):
	"""
	Integration tests for PurchaseInvoice.
	Use this class for testing interactions between multiple components.
	"""

	def test_stock_posting_and_cancel_reversal(self):
		uom = ensure_uom()
		supplier = ensure_supplier()
		warehouse = ensure_warehouse()
		stock_item = ensure_item(is_stock_item=1, stock_uom=uom, standard_rate=10)

		purchase_invoice = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"posting_date": nowdate(),
				"posting_time": nowtime(),
				"set_warehouse": warehouse,
				"items": [
					{
						"item_code": stock_item,
						"qty": 5,
						"uom": uom,
						"rate": 10,
						"warehouse": warehouse,
					}
				],
			}
		)
		purchase_invoice.insert()
		purchase_invoice.submit()

		stock_key = f"{stock_item}::{warehouse}"
		stock_balance = frappe.get_doc("Stock Balance", stock_key)
		self.assertEqual(flt(stock_balance.actual_qty), 5)
		self.assertEqual(flt(stock_balance.stock_value), 50)

		purchase_invoice.cancel()
		stock_balance.reload()
		self.assertEqual(flt(stock_balance.actual_qty), 0)
		self.assertEqual(flt(stock_balance.stock_value), 0)

	def test_purchase_payment_submit_and_cancel_updates_invoice(self):
		uom = ensure_uom()
		supplier = ensure_supplier()
		service_item = ensure_item(is_stock_item=0, stock_uom=uom, standard_rate=120)

		purchase_invoice = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"posting_date": nowdate(),
				"posting_time": nowtime(),
				"items": [
					{
						"item_code": service_item,
						"qty": 1,
						"uom": uom,
						"rate": 120,
					}
				],
			}
		)
		purchase_invoice.insert()
		purchase_invoice.submit()
		purchase_invoice.reload()
		self.assertEqual(flt(purchase_invoice.outstanding_amount), flt(purchase_invoice.grand_total))

		payment_name = create_payment_entry_for_purchase_invoice(purchase_invoice.name)
		payment_entry = frappe.get_doc("Payment Entry", payment_name)
		payment_entry.submit()

		purchase_invoice.reload()
		self.assertEqual(flt(purchase_invoice.outstanding_amount), 0)
		self.assertEqual(purchase_invoice.payment_status, "Paid")

		payment_entry.cancel()
		purchase_invoice.reload()
		self.assertEqual(flt(purchase_invoice.outstanding_amount), flt(purchase_invoice.grand_total))
		self.assertEqual(purchase_invoice.payment_status, "Unpaid")


def unique_name(prefix):
	return f"{prefix}-{frappe.generate_hash(length=6).upper()}"


def ensure_uom():
	uom_name = f"UOM-{frappe.generate_hash(length=6).upper()}"
	doc = frappe.get_doc({"doctype": "UOM", "uom_name": uom_name, "enabled": 1})
	doc.insert()
	return doc.name


def ensure_supplier():
	name = unique_name("SUP")
	doc = frappe.get_doc({"doctype": "Supplier", "supplier_name": name})
	doc.insert()
	return doc.name


def ensure_warehouse():
	name = unique_name("WH")
	doc = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": name, "is_group": 0})
	doc.insert()
	return doc.name


def ensure_item(*, is_stock_item: int, stock_uom: str, standard_rate: float):
	code = unique_name("ITEM")
	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": code,
			"is_stock_item": is_stock_item,
			"stock_uom": stock_uom,
			"standard_rate": standard_rate,
		}
	)
	doc.insert()
	return doc.name
