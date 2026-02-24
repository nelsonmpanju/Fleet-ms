# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
Stats utilities for Customer and Supplier dashboard tabs.
"""

import frappe


@frappe.whitelist()
def get_customer_stats(customer):
	"""Return invoice totals and cargo job counts for a Customer."""
	invoices = frappe.db.sql(
		"""
		SELECT name, posting_date, grand_total, paid_amount,
		       outstanding_amount, payment_status
		FROM `tabSales Invoice`
		WHERE customer = %s AND docstatus = 1
		ORDER BY posting_date DESC
		LIMIT 5
		""",
		customer,
		as_dict=True,
	)

	totals = frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS invoice_count,
			SUM(grand_total) AS billed,
			SUM(paid_amount) AS collected,
			SUM(outstanding_amount) AS outstanding
		FROM `tabSales Invoice`
		WHERE customer = %s AND docstatus = 1
		""",
		customer,
		as_dict=True,
	)[0]

	# Trips are linked through Cargo Registration (which has the customer field)
	cargo = frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS total_trips,
			SUM(CASE WHEN docstatus = 1 THEN 1 ELSE 0 END) AS completed_trips
		FROM `tabCargo Registration`
		WHERE customer = %s
		""",
		customer,
		as_dict=True,
	)[0]

	return {
		"invoice_count": totals.invoice_count or 0,
		"billed": totals.billed or 0,
		"collected": totals.collected or 0,
		"outstanding": totals.outstanding or 0,
		"total_trips": cargo.total_trips or 0,
		"completed_trips": cargo.completed_trips or 0,
		"recent_invoices": invoices,
	}


@frappe.whitelist()
def get_supplier_stats(supplier):
	"""Return purchase invoice totals and recent invoices for a Supplier."""
	invoices = frappe.db.sql(
		"""
		SELECT name, posting_date, invoice_type, grand_total,
		       paid_amount, outstanding_amount, payment_status
		FROM `tabPurchase Invoice`
		WHERE supplier = %s AND docstatus = 1
		ORDER BY posting_date DESC
		LIMIT 5
		""",
		supplier,
		as_dict=True,
	)

	totals = frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS invoice_count,
			SUM(grand_total) AS spend,
			SUM(paid_amount) AS paid,
			SUM(outstanding_amount) AS outstanding,
			SUM(CASE WHEN invoice_type = 'Fuel' THEN grand_total ELSE 0 END) AS fuel_spend
		FROM `tabPurchase Invoice`
		WHERE supplier = %s AND docstatus = 1
		""",
		supplier,
		as_dict=True,
	)[0]

	# Fuel litres: sum qty from invoice items for fuel invoices
	fuel_litres_row = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(pii.qty), 0) AS fuel_litres
		FROM `tabPurchase Invoice Item` pii
		JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE pi.supplier = %s AND pi.invoice_type = 'Fuel' AND pi.docstatus = 1
		""",
		supplier,
		as_dict=True,
	)
	fuel_litres = fuel_litres_row[0].fuel_litres if fuel_litres_row else 0

	return {
		"invoice_count": totals.invoice_count or 0,
		"spend": totals.spend or 0,
		"paid": totals.paid or 0,
		"outstanding": totals.outstanding or 0,
		"fuel_spend": totals.fuel_spend or 0,
		"fuel_litres": fuel_litres or 0,
		"recent_invoices": invoices,
	}
