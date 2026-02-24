# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, nowtime

from vsd_fleet_ms.vsd_fleet_ms.report.profit_and_loss_summary.profit_and_loss_summary import (
	execute,
)


EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestProfitAndLossSummary(IntegrationTestCase):
	def test_report_includes_ledger_and_stock_values(self):
		test_date = "2099-01-01"
		currency = ensure_currency()
		uom = ensure_uom()
		customer = ensure_customer()
		supplier = ensure_supplier()
		warehouse = ensure_warehouse()
		stock_item = ensure_item(is_stock_item=1, stock_uom=uom, standard_rate=10)
		service_item = ensure_item(is_stock_item=0, stock_uom=uom, standard_rate=200)
		income_account = ensure_account("Income", currency)
		expense_account = ensure_account("Expense", currency)

		purchase_invoice = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"posting_date": test_date,
				"posting_time": "10:00:00",
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

		stock_entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"posting_date": test_date,
				"posting_time": "11:00:00",
				"stock_entry_type": "Material Issue",
				"purpose": "Material Issue",
				"from_warehouse": warehouse,
				"items": [
					{
						"item_code": stock_item,
						"qty": 2,
						"s_warehouse": warehouse,
						"basic_rate": 10,
					}
				],
			}
		)
		stock_entry.insert()
		stock_entry.submit()

		sales_invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"posting_date": test_date,
				"posting_time": nowtime(),
				"items": [
					{
						"item_code": service_item,
						"qty": 1,
						"uom": uom,
						"rate": 200,
					}
				],
			}
		)
		sales_invoice.insert()
		sales_invoice.submit()

		ledger_income = frappe.get_doc(
			{
				"doctype": "Ledger Entry",
				"posting_date": test_date,
				"entry_type": "Income",
				"source_type": "Manual",
				"account": income_account,
				"currency": currency,
				"amount": 30,
				"description": "Extra income",
			}
		)
		ledger_income.insert()
		ledger_income.submit()

		ledger_expense = frappe.get_doc(
			{
				"doctype": "Ledger Entry",
				"posting_date": test_date,
				"entry_type": "Expense",
				"source_type": "Manual",
				"account": expense_account,
				"currency": currency,
				"amount": 12,
				"description": "Other expense",
			}
		)
		ledger_expense.insert()
		ledger_expense.submit()

		_, data, _, _, _ = execute({"from_date": test_date, "to_date": test_date})
		metrics = data[0]

		self.assertEqual(flt(metrics.get("sales_total")), 200)
		self.assertEqual(flt(metrics.get("purchase_total")), 50)
		self.assertEqual(flt(metrics.get("ledger_income")), 30)
		self.assertEqual(flt(metrics.get("ledger_expense")), 12)
		self.assertEqual(flt(metrics.get("stock_receipt_value")), 50)
		self.assertEqual(flt(metrics.get("stock_issue_value")), 20)
		self.assertEqual(flt(metrics.get("net_profit")), 148)


def unique_name(prefix):
	return f"{prefix}-{frappe.generate_hash(length=6).upper()}"


def ensure_currency():
	currency = "USD"
	if not frappe.db.exists("Currency", currency):
		frappe.get_doc(
			{"doctype": "Currency", "currency_name": currency, "symbol": "$", "enabled": 1}
		).insert()
	return currency


def ensure_uom():
	uom_name = unique_name("UOM")
	frappe.get_doc({"doctype": "UOM", "uom_name": uom_name, "enabled": 1}).insert()
	return uom_name


def ensure_customer():
	name = unique_name("CUS")
	frappe.get_doc({"doctype": "Customer", "customer_name": name}).insert()
	return name


def ensure_supplier():
	name = unique_name("SUP")
	frappe.get_doc({"doctype": "Supplier", "supplier_name": name}).insert()
	return name


def ensure_warehouse():
	name = unique_name("WH")
	frappe.get_doc({"doctype": "Warehouse", "warehouse_name": name, "is_group": 0}).insert()
	return name


def ensure_item(*, is_stock_item: int, stock_uom: str, standard_rate: float):
	code = unique_name("ITEM")
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": code,
			"is_stock_item": is_stock_item,
			"stock_uom": stock_uom,
			"standard_rate": standard_rate,
		}
	).insert()
	return code


def ensure_account(account_type: str, currency: str):
	name = unique_name("ACC")
	frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": name,
			"account_type": account_type,
			"account_currency": currency,
			"is_group": 0,
		}
	).insert()
	return name
