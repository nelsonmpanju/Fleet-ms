# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def after_install():
	create_default_chart_of_accounts()


def create_default_chart_of_accounts():
	"""
	Create a default Chart of Accounts for Fleet MS.

	Tree structure
	==============
	Assets (1000)
	  Bank (1100)
	    Main Bank Account (1110)
	  Petty Cash (1200)
	    Cash on Hand (1210)
	  Accounts Receivable (1300)
	    Debtors (1310)
	  Other Current Assets (1400)

	Liabilities (2000)
	  Accounts Payable (2100)
	    Creditors (2110)
	  Tax Liabilities (2200)
	    VAT Payable (2210)
	  Other Current Liabilities (2300)

	Equity (3000)
	  Owner's Capital (3100)
	  Retained Earnings (3200)

	Income (4000)
	  Freight Income (4100)
	    Transport Revenue (4110)
	  Other Income (4200)
	    Miscellaneous Income (4210)

	Expenses (5000)
	  Fuel Expenses (5100)
	    Diesel Fuel (5110)
	    Fuel Additives (5120)
	  Driver Expenses (5200)
	    Driver Allowances (5210)
	    Driver Accommodation (5220)
	  Maintenance and Repairs (5300)
	    Vehicle Maintenance (5310)
	    Tyres and Parts (5320)
	  Administrative Expenses (5400)
	    Office Expenses (5410)
	    Insurance Premiums (5420)
	    Licensing and Permits (5430)
	  Other Expenses (5500)
	    Fines and Penalties (5510)
	    Miscellaneous Expenses (5520)
	"""

	# (account_number, account_name, parent_account, is_group, account_type, description)
	accounts = [
		# ── Root groups ──────────────────────────────────────────────────────────
		("1000", "Assets",      None, 1, "Asset",     "All asset accounts"),
		("2000", "Liabilities", None, 1, "Liability", "All liability accounts"),
		("3000", "Equity",      None, 1, "Equity",    "Owner equity and retained earnings"),
		("4000", "Income",      None, 1, "Income",    "All revenue and income accounts"),
		("5000", "Expenses",    None, 1, "Expense",   "All expense accounts"),

		# ── Assets ───────────────────────────────────────────────────────────────
		("1100", "Bank",                 "Assets", 1, "Asset", "Bank and financial institution accounts"),
		("1200", "Petty Cash",           "Assets", 1, "Asset", "Cash on hand and petty cash funds"),
		("1300", "Accounts Receivable",  "Assets", 1, "Asset", "Amounts owed by customers"),
		("1400", "Other Current Assets", "Assets", 1, "Asset", "Prepayments and other short-term assets"),

		# Bank children
		("1110", "Main Bank Account", "Bank", 0, "Asset", "Primary operating bank account"),

		# Petty Cash children
		("1210", "Cash on Hand", "Petty Cash", 0, "Asset", "Cash kept for day-to-day expenses"),

		# Accounts Receivable children
		("1310", "Debtors", "Accounts Receivable", 0, "Asset", "Customer balances outstanding"),

		# ── Liabilities ──────────────────────────────────────────────────────────
		("2100", "Accounts Payable",          "Liabilities", 1, "Liability", "Amounts owed to suppliers"),
		("2200", "Tax Liabilities",           "Liabilities", 1, "Liability", "VAT and other tax payable"),
		("2300", "Other Current Liabilities", "Liabilities", 1, "Liability", "Accruals and other payables"),

		# Accounts Payable children
		("2110", "Creditors", "Accounts Payable", 0, "Liability", "Supplier balances outstanding"),

		# Tax Liabilities children
		("2210", "VAT Payable", "Tax Liabilities", 0, "Liability", "Output VAT due to tax authority"),

		# ── Equity ───────────────────────────────────────────────────────────────
		("3100", "Owner's Capital",        "Equity", 0, "Equity", "Capital invested by owners"),
		("3200", "Retained Earnings",      "Equity", 0, "Equity", "Accumulated profits retained in business"),
		("3300", "Opening Balance Equity", "Equity", 0, "Equity", "System account — absorbs opening balance entries during initial setup."),

		# ── Income ───────────────────────────────────────────────────────────────
		("4100", "Freight Income", "Income", 1, "Income", "Revenue from transport and freight services"),
		("4200", "Other Income",   "Income", 1, "Income", "Non-freight revenue"),

		# Freight Income children
		("4110", "Transport Revenue", "Freight Income", 0, "Income", "Income from cargo transportation"),

		# Other Income children
		("4210", "Miscellaneous Income", "Other Income", 0, "Income", "Other non-operating income"),

		# ── Expenses ─────────────────────────────────────────────────────────────
		("5100", "Fuel Expenses",           "Expenses", 1, "Expense", "All fuel and lubricant costs"),
		("5200", "Driver Expenses",         "Expenses", 1, "Expense", "Driver wages, allowances and accommodation"),
		("5300", "Maintenance and Repairs", "Expenses", 1, "Expense", "Vehicle maintenance and repair costs"),
		("5400", "Administrative Expenses", "Expenses", 1, "Expense", "Office, insurance and licensing costs"),
		("5500", "Other Expenses",          "Expenses", 1, "Expense", "Fines, penalties and miscellaneous costs"),

		# Fuel Expenses children
		("5110", "Diesel Fuel",    "Fuel Expenses", 0, "Expense", "Diesel purchased for fleet vehicles"),
		("5120", "Fuel Additives", "Fuel Expenses", 0, "Expense", "Oils, lubricants and fuel additives"),

		# Driver Expenses children
		("5210", "Driver Allowances",   "Driver Expenses", 0, "Expense", "Per-diem and trip allowances for drivers"),
		("5220", "Driver Accommodation", "Driver Expenses", 0, "Expense", "Hotel and accommodation costs for drivers"),

		# Maintenance and Repairs children
		("5310", "Vehicle Maintenance", "Maintenance and Repairs", 0, "Expense", "Scheduled and preventive maintenance"),
		("5320", "Tyres and Parts",     "Maintenance and Repairs", 0, "Expense", "Tyres, spare parts and consumables"),

		# Administrative Expenses children
		("5410", "Office Expenses",       "Administrative Expenses", 0, "Expense", "Stationery and general office costs"),
		("5420", "Insurance Premiums",    "Administrative Expenses", 0, "Expense", "Vehicle and fleet insurance"),
		("5430", "Licensing and Permits", "Administrative Expenses", 0, "Expense", "Road licences, permits and fitness fees"),

		# Other Expenses children
		("5510", "Fines and Penalties",    "Other Expenses", 0, "Expense", "Traffic fines and regulatory penalties"),
		("5520", "Miscellaneous Expenses", "Other Expenses", 0, "Expense", "Sundry expenses not classified elsewhere"),
	]

	created = 0
	skipped = 0
	for account_number, account_name, parent_account, is_group, account_type, description in accounts:
		if frappe.db.exists("Account", account_name):
			continue

		# Verify parent exists and is a group before inserting children
		if parent_account:
			parent_is_group = frappe.db.get_value("Account", parent_account, "is_group")
			if parent_is_group is None:
				frappe.log_error(
					f"Skipping account '{account_name}': parent '{parent_account}' not found.",
					"Chart of Accounts Setup",
				)
				skipped += 1
				continue
			if not parent_is_group:
				frappe.log_error(
					f"Skipping account '{account_name}': parent '{parent_account}' exists but is not a group.",
					"Chart of Accounts Setup",
				)
				skipped += 1
				continue

		doc = frappe.get_doc({
			"doctype": "Account",
			"account_name": account_name,
			"account_number": account_number,
			"parent_account": parent_account,
			"is_group": is_group,
			"account_type": account_type,
			"description": description,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()  # commit after each account so children can verify parent.is_group
		created += 1

	if created or skipped:
		msg = _("Chart of Accounts: {0} accounts created.").format(created)
		if skipped:
			msg += " " + _("{0} skipped (parent conflicts with existing data).").format(skipped)
		frappe.msgprint(msg, alert=True)


def seed_ob_equity_account():
	"""Create the Opening Balance Equity account if it does not yet exist.

	Run once via:  bench --site <site> execute vsd_fleet_ms.install.seed_ob_equity_account
	"""
	name = "Opening Balance Equity"
	if frappe.db.exists("Account", name):
		print(f"{name} already exists — nothing to do.")
		return

	if not frappe.db.exists("Account", "Equity"):
		print("ERROR: 'Equity' group account not found. Please create it first.")
		return

	frappe.get_doc({
		"doctype":        "Account",
		"account_name":   name,
		"account_number": "3300",
		"parent_account": "Equity",
		"is_group":       0,
		"account_type":   "Equity",
		"description":    "System account — absorbs opening balance entries during initial setup.",
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"Created '{name}' successfully.")
