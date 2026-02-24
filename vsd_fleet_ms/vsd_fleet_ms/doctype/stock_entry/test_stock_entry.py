# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, nowdate, nowtime


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestStockEntry(IntegrationTestCase):
	"""
	Integration tests for StockEntry.
	Use this class for testing interactions between multiple components.
	"""
	doctype = None

	def test_material_issue_and_cancel_updates_stock(self):
		uom = ensure_uom()
		supplier = ensure_supplier()
		warehouse = ensure_warehouse()
		stock_item = ensure_item(is_stock_item=1, stock_uom=uom, standard_rate=20)

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
						"qty": 6,
						"uom": uom,
						"rate": 20,
						"warehouse": warehouse,
					}
				],
			}
		)
		purchase_invoice.insert()
		purchase_invoice.submit()

		stock_entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"purpose": "Material Issue",
				"posting_date": nowdate(),
				"posting_time": nowtime(),
				"from_warehouse": warehouse,
				"items": [
					{
						"item_code": stock_item,
						"qty": 2,
						"uom": uom,
						"s_warehouse": warehouse,
						"basic_rate": 20,
					}
				],
			}
		)
		stock_entry.insert()
		stock_entry.submit()

		stock_balance = frappe.get_doc("Stock Balance", f"{stock_item}::{warehouse}")
		self.assertEqual(flt(stock_balance.actual_qty), 4)

		stock_entry.cancel()
		stock_balance.reload()
		self.assertEqual(flt(stock_balance.actual_qty), 6)

		purchase_invoice.cancel()
		stock_balance.reload()
		self.assertEqual(flt(stock_balance.actual_qty), 0)


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
