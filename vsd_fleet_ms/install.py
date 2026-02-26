# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def after_install():
	create_default_chart_of_accounts()
	create_seed_accounts()
	create_fixed_expenses()
	create_trip_location_types()
	create_trip_locations()
	create_cargo_types()
	create_fuel_items()
	normalize_account_currencies()


# ── helpers ──────────────────────────────────────────────────────────────────

def _make(doctype, data, unique_field="name"):
	"""Insert if not already exists; return the doc."""
	key = data.get(unique_field) or data.get("name")
	if frappe.db.exists(doctype, key):
		return frappe.get_doc(doctype, key)
	doc = frappe.get_doc({"doctype": doctype, **data})
	doc.insert(ignore_permissions=True)
	return doc


# ── 1. Chart of Accounts ────────────────────────────────────────────────────

def create_default_chart_of_accounts():
	"""
	Create a default Chart of Accounts for Fleet MS.
	All accounts default to TZS currency.

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
			"account_currency": "TZS",
			"description": description,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		created += 1

	if created or skipped:
		msg = _("Chart of Accounts: {0} accounts created.").format(created)
		if skipped:
			msg += " " + _("{0} skipped (parent conflicts with existing data).").format(skipped)
		frappe.msgprint(msg, alert=True)


# ── 2. Seed Accounts (operational accounts under the main chart) ────────────

def create_seed_accounts():
	"""Create additional operational accounts used by fixed expenses and trips."""
	accounts = [
		{"account_name": "Driver Cash Advance",     "account_type": "Asset",   "account_currency": "TZS", "parent_account": "Other Current Assets"},
		{"account_name": "Driver Daily Allowance",   "account_type": "Expense", "account_currency": "TZS", "parent_account": "Driver Expenses"},
		{"account_name": "Driver Subsistence USD",   "account_type": "Expense", "account_currency": "USD", "parent_account": "Driver Expenses"},
		{"account_name": "Road Tolls and Levies",    "account_type": "Expense", "account_currency": "TZS", "parent_account": "Other Expenses"},
		{"account_name": "Border Crossing Fees",     "account_type": "Expense", "account_currency": "TZS", "parent_account": "Other Expenses"},
		{"account_name": "Port Handling Charges",    "account_type": "Expense", "account_currency": "TZS", "parent_account": "Other Expenses"},
		{"account_name": "Weigh Bridge Fees",        "account_type": "Expense", "account_currency": "TZS", "parent_account": "Other Expenses"},
		{"account_name": "Loading and Offloading",   "account_type": "Expense", "account_currency": "TZS", "parent_account": "Other Expenses"},
	]
	for acc in accounts:
		_make("Account", acc, unique_field="account_name")
	frappe.db.commit()


# ── 3. Fixed Expenses ───────────────────────────────────────────────────────

def create_fixed_expenses():
	"""Create standard fixed expense templates linked to accounts."""
	fixed_expenses = [
		{
			"description":       "Driver Daily Allowance (TZS)",
			"currency":          "TZS", "fixed_value": 50000,
			"expense_account":   "Driver Daily Allowance",
			"cash_bank_account": "Petty Cash",
		},
		{
			"description":       "Driver Subsistence (USD)",
			"currency":          "USD", "fixed_value": 20,
			"expense_account":   "Driver Subsistence USD",
			"cash_bank_account": "Driver Cash Advance",
		},
		{
			"description":       "Road Toll (Local Highway)",
			"currency":          "TZS", "fixed_value": 3000,
			"expense_account":   "Road Tolls and Levies",
			"cash_bank_account": "Petty Cash",
		},
		{
			"description":       "Weigh Bridge Fee",
			"currency":          "TZS", "fixed_value": 5000,
			"expense_account":   "Weigh Bridge Fees",
			"cash_bank_account": "Petty Cash",
		},
		{
			"description":       "DSM Port Entry Fee",
			"currency":          "TZS", "fixed_value": 10000,
			"expense_account":   "Port Handling Charges",
			"cash_bank_account": "Petty Cash",
		},
		{
			"description":       "Loading and Offloading Fee",
			"currency":          "TZS", "fixed_value": 20000,
			"expense_account":   "Loading and Offloading",
			"cash_bank_account": "Petty Cash",
		},
		{
			"description":       "Namanga Border Fee",
			"currency":          "TZS", "fixed_value": 20000,
			"expense_account":   "Border Crossing Fees",
			"cash_bank_account": "Petty Cash",
		},
		{
			"description":       "Tunduma Border Fee",
			"currency":          "TZS", "fixed_value": 30000,
			"expense_account":   "Border Crossing Fees",
			"cash_bank_account": "Petty Cash",
		},
		{
			"description":       "Mutukula Border Fee",
			"currency":          "TZS", "fixed_value": 25000,
			"expense_account":   "Border Crossing Fees",
			"cash_bank_account": "Petty Cash",
		},
	]
	for fe in fixed_expenses:
		_make("Fixed Expenses", fe, unique_field="description")
	frappe.db.commit()


# ── 4. Trip Location Types ──────────────────────────────────────────────────

def create_trip_location_types():
	"""Create the standard trip location type categories."""
	location_types = [
		{"location_type": "Loading Point",    "loading_date": 1,    "arrival_date": 1},
		{"location_type": "Offloading Point", "offloading_date": 1, "arrival_date": 1},
		{"location_type": "Border Post",      "arrival_date": 1,    "departure_date": 1},
		{"location_type": "Transit Stop",     "arrival_date": 1,    "departure_date": 1},
		{"location_type": "Destination Port",  "arrival_date": 1,    "offloading_date": 1},
	]
	for lt in location_types:
		_make("Trip Locations Type", lt, unique_field="location_type")
	frappe.db.commit()


# ── 5. Trip Locations ────────────────────────────────────────────────────────

def create_trip_locations():
	"""Create commonly used trip locations in East/Southern Africa."""
	locations = [
		# Tanzania
		{"description": "Dar es Salaam Port",  "country": "Tanzania", "latitude": -6.824,  "longitude": 39.288},
		{"description": "Arusha City",         "country": "Tanzania", "latitude": -3.387,  "longitude": 36.682},
		{"description": "Dodoma City",         "country": "Tanzania", "latitude": -6.173,  "longitude": 35.739},
		{"description": "Mwanza City",         "country": "Tanzania", "latitude": -2.516,  "longitude": 32.900},
		{"description": "Iringa Town",         "country": "Tanzania", "latitude": -7.770,  "longitude": 35.692},
		{"description": "Mbeya City",          "country": "Tanzania", "latitude": -8.900,  "longitude": 33.460},
		{"description": "Tunduma Border",      "country": "Tanzania", "latitude": -9.300,  "longitude": 32.770},
		{"description": "Mutukula Border",     "country": "Tanzania", "latitude": -1.014,  "longitude": 31.372},
		# Kenya
		{"description": "Nairobi CBD",         "country": "Kenya",   "latitude": -1.286,  "longitude": 36.817},
		{"description": "Mombasa Port",        "country": "Kenya",   "latitude": -4.052,  "longitude": 39.666},
		# Uganda
		{"description": "Kampala City",        "country": "Uganda",  "latitude": 0.347,   "longitude": 32.582},
		{"description": "Busia Border",        "country": "Uganda",  "latitude": 0.460,   "longitude": 34.090},
		# Zambia
		{"description": "Lusaka City",         "country": "Zambia",  "latitude": -15.416, "longitude": 28.282},
		{"description": "Nakonde Border",      "country": "Zambia",  "latitude": -9.348,  "longitude": 32.767},
	]
	for loc in locations:
		_make("Trip Locations", loc, unique_field="description")
	frappe.db.commit()


# ── 6. Cargo Types ──────────────────────────────────────────────────────────

def create_cargo_types():
	"""Create standard cargo type categories with required permits."""
	cargo_types = [
		{
			"cargo_name": "Container 20ft",
			"permits": [
				{"permit_name": "TANCIS Clearance Certificate", "mandatory": 1, "permit_type": "Local Import"},
				{"permit_name": "TBS Conformity Certificate",   "mandatory": 1, "permit_type": "Local Import"},
			],
		},
		{
			"cargo_name": "Container 40ft",
			"permits": [
				{"permit_name": "TANCIS Clearance Certificate", "mandatory": 1, "permit_type": "Local Import"},
				{"permit_name": "TBS Conformity Certificate",   "mandatory": 1, "permit_type": "Local Import"},
				{"permit_name": "Oversize Load Permit",          "mandatory": 0, "permit_type": "Transit Import"},
			],
		},
		{
			"cargo_name": "Bulk Cargo",
			"permits": [
				{"permit_name": "Weight Certificate",           "mandatory": 1, "permit_type": "Local Import"},
				{"permit_name": "TANCIS Clearance Certificate", "mandatory": 1, "permit_type": "Transit Import"},
			],
		},
		{
			"cargo_name": "Fuel Tanker",
			"permits": [
				{"permit_name": "EWURA Licence",                "mandatory": 1, "permit_type": "Local Import"},
				{"permit_name": "OSHA Safety Certificate",      "mandatory": 1, "permit_type": "Transit Import"},
				{"permit_name": "TBS Fuel Quality Certificate", "mandatory": 1, "permit_type": "Local Import"},
			],
		},
		{
			"cargo_name": "Livestock",
			"permits": [
				{"permit_name": "Veterinary Health Certificate", "mandatory": 1, "permit_type": "Local Export"},
				{"permit_name": "Movement Permit",               "mandatory": 1, "permit_type": "Local Export"},
			],
		},
		{
			"cargo_name": "General Cargo",
			"permits": [
				{"permit_name": "Packing List", "mandatory": 1, "permit_type": "Local Import"},
			],
		},
		{
			"cargo_name": "Dangerous Goods",
			"permits": [
				{"permit_name": "Dangerous Goods Declaration", "mandatory": 1, "permit_type": "Transit Import"},
				{"permit_name": "OSHA Hazmat Permit",          "mandatory": 1, "permit_type": "Transit Import"},
				{"permit_name": "Emergency Info Sheet (EIS)",  "mandatory": 1, "permit_type": "Transit Export"},
			],
		},
		{
			"cargo_name": "Refrigerated Cargo",
			"permits": [
				{"permit_name": "Temperature Log Sheet",        "mandatory": 1, "permit_type": "Local Import"},
				{"permit_name": "Health Certificate",           "mandatory": 1, "permit_type": "Local Import"},
				{"permit_name": "TANCIS Clearance Certificate", "mandatory": 1, "permit_type": "Transit Import"},
			],
		},
	]
	for ct in cargo_types:
		if not frappe.db.exists("Cargo Types", ct["cargo_name"]):
			doc = frappe.get_doc({"doctype": "Cargo Types", "cargo_name": ct["cargo_name"]})
			for p in ct.get("permits", []):
				doc.append("permits", p)
			doc.insert(ignore_permissions=True)
	frappe.db.commit()


# ── 7. Fuel Items ───────────────────────────────────────────────────────────

def create_fuel_items():
	"""Create default fuel item (Diesel only — no generic 'Fuel' item)."""
	if frappe.db.exists("Item", "Diesel"):
		# Fix item_type if it was created with wrong type
		frappe.db.set_value("Item", "Diesel", "item_type", "Fuel")
	else:
		frappe.get_doc({
			"doctype": "Item",
			"item_code": "Diesel",
			"item_name": "Diesel",
			"item_type": "Fuel",
			"is_stock_item": 0,
		}).insert(ignore_permissions=True)
	frappe.db.commit()


# ── 8. Normalize account currencies ─────────────────────────────────────────

def normalize_account_currencies():
	"""Set TZS as default currency on all accounts that don't have one
	or have a non-TZS/USD currency. USD accounts (e.g. Driver Subsistence)
	are left untouched."""
	usd_accounts = ["Driver Subsistence USD"]
	all_accounts = frappe.get_all("Account", fields=["name", "account_currency"])
	updated = 0
	for acc in all_accounts:
		if acc.name in usd_accounts:
			continue
		if acc.account_currency not in (None, "", "TZS"):
			frappe.db.set_value("Account", acc.name, "account_currency", "TZS")
			updated += 1
	if updated:
		frappe.db.commit()
