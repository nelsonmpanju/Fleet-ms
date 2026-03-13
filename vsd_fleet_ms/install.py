# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def after_install():
	create_default_currencies()
	create_default_chart_of_accounts()
	create_seed_accounts()
	create_fixed_expenses()
	create_trip_location_types()
	create_trip_locations()
	create_transport_locations()
	create_trip_routes()
	create_cargo_types()
	create_fuel_items()
	set_transport_settings()
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


# ── 0. Currencies ──────────────────────────────────────────────────────────

def create_default_currencies():
	"""Ensure TZS and USD currency records exist before creating accounts."""
	currencies = [
		{"currency_name": "TZS", "symbol": "TSh", "enabled": 1},
		{"currency_name": "USD", "symbol": "$", "enabled": 1},
	]
	for curr in currencies:
		if not frappe.db.exists("Currency", curr["currency_name"]):
			doc = frappe.get_doc({"doctype": "Currency", **curr})
			doc.insert(ignore_permissions=True)
	frappe.db.commit()


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
			"cash_bank_account": "Cash on Hand",
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
			"cash_bank_account": "Cash on Hand",
		},
		{
			"description":       "Weigh Bridge Fee",
			"currency":          "TZS", "fixed_value": 5000,
			"expense_account":   "Weigh Bridge Fees",
			"cash_bank_account": "Cash on Hand",
		},
		{
			"description":       "DSM Port Entry Fee",
			"currency":          "TZS", "fixed_value": 10000,
			"expense_account":   "Port Handling Charges",
			"cash_bank_account": "Cash on Hand",
		},
		{
			"description":       "Loading and Offloading Fee",
			"currency":          "TZS", "fixed_value": 20000,
			"expense_account":   "Loading and Offloading",
			"cash_bank_account": "Cash on Hand",
		},
		{
			"description":       "Namanga Border Fee",
			"currency":          "TZS", "fixed_value": 20000,
			"expense_account":   "Border Crossing Fees",
			"cash_bank_account": "Cash on Hand",
		},
		{
			"description":       "Tunduma Border Fee",
			"currency":          "TZS", "fixed_value": 30000,
			"expense_account":   "Border Crossing Fees",
			"cash_bank_account": "Cash on Hand",
		},
		{
			"description":       "Mutukula Border Fee",
			"currency":          "TZS", "fixed_value": 25000,
			"expense_account":   "Border Crossing Fees",
			"cash_bank_account": "Cash on Hand",
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
		{"location_type": "Destination Port", "arrival_date": 1,    "offloading_date": 1},
		{"location_type": "Weigh Bridge",     "arrival_date": 1,    "departure_date": 1},
		{"location_type": "Fuel Stop",        "arrival_date": 1,    "departure_date": 1},
	]
	for lt in location_types:
		_make("Trip Locations Type", lt, unique_field="location_type")
	frappe.db.commit()


# ── 5. Trip Locations ────────────────────────────────────────────────────────

def create_trip_locations():
	"""Create commonly used trip locations in East/Southern Africa with accurate
	coordinates and border flags used by logistics companies."""
	locations = [
		# ── Tanzania — Ports & Cities ─────────────────────────────────────────
		{"description": "Dar es Salaam Port",     "country": "Tanzania", "latitude": -6.824,  "longitude": 39.288,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Tanga Port",             "country": "Tanzania", "latitude": -5.068,  "longitude": 39.098,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Bagamoyo",               "country": "Tanzania", "latitude": -6.430,  "longitude": 38.900,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Chalinze",               "country": "Tanzania", "latitude": -6.541,  "longitude": 38.034,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Morogoro City",          "country": "Tanzania", "latitude": -6.821,  "longitude": 37.661,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Dodoma City",            "country": "Tanzania", "latitude": -6.173,  "longitude": 35.739,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Iringa Town",            "country": "Tanzania", "latitude": -7.770,  "longitude": 35.692,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Mbeya City",             "country": "Tanzania", "latitude": -8.900,  "longitude": 33.460,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Arusha City",            "country": "Tanzania", "latitude": -3.387,  "longitude": 36.682,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Moshi Town",             "country": "Tanzania", "latitude": -3.340,  "longitude": 37.340,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Mwanza City",            "country": "Tanzania", "latitude": -2.516,  "longitude": 32.900,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Shinyanga Town",         "country": "Tanzania", "latitude": -3.660,  "longitude": 33.420,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Tabora Town",            "country": "Tanzania", "latitude": -5.076,  "longitude": 32.800,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Singida Town",           "country": "Tanzania", "latitude": -4.817,  "longitude": 34.744,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Kigoma Town",            "country": "Tanzania", "latitude": -4.883,  "longitude": 29.626,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Songea Town",            "country": "Tanzania", "latitude": -10.683, "longitude": 35.650,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Lindi Town",             "country": "Tanzania", "latitude": -10.000, "longitude": 39.714,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Mtwara Town",            "country": "Tanzania", "latitude": -10.274, "longitude": 40.183,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Kahama Town",            "country": "Tanzania", "latitude": -3.840,  "longitude": 32.600,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Nzega Town",             "country": "Tanzania", "latitude": -4.210,  "longitude": 33.185,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Makambako Town",         "country": "Tanzania", "latitude": -8.850,  "longitude": 34.850,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Kibaha Town",            "country": "Tanzania", "latitude": -6.770,  "longitude": 38.930,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Korogwe Town",           "country": "Tanzania", "latitude": -5.154,  "longitude": 38.471,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Segera Junction",        "country": "Tanzania", "latitude": -5.375,  "longitude": 38.350,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Same Town",              "country": "Tanzania", "latitude": -4.076,  "longitude": 37.721,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Himo Town",              "country": "Tanzania", "latitude": -3.380,  "longitude": 37.530,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Isaka Dry Port",         "country": "Tanzania", "latitude": -3.600,  "longitude": 33.250,  "is_local_border": 0, "is_international_border": 0},

		# ── Tanzania — Border Posts (local side) ──────────────────────────────
		{"description": "Tunduma Border",         "country": "Tanzania", "latitude": -9.300,  "longitude": 32.770,  "is_local_border": 1, "is_international_border": 0},
		{"description": "Mutukula Border (TZ)",   "country": "Tanzania", "latitude": -1.000,  "longitude": 31.450,  "is_local_border": 1, "is_international_border": 0},
		{"description": "Namanga Border (TZ)",    "country": "Tanzania", "latitude": -2.540,  "longitude": 36.793,  "is_local_border": 1, "is_international_border": 0},
		{"description": "Holili Border (TZ)",     "country": "Tanzania", "latitude": -3.310,  "longitude": 37.660,  "is_local_border": 1, "is_international_border": 0},
		{"description": "Horohoro Border (TZ)",   "country": "Tanzania", "latitude": -4.604,  "longitude": 39.188,  "is_local_border": 1, "is_international_border": 0},
		{"description": "Sirari Border (TZ)",     "country": "Tanzania", "latitude": -1.249,  "longitude": 34.407,  "is_local_border": 1, "is_international_border": 0},
		{"description": "Kabanga Border (TZ)",    "country": "Tanzania", "latitude": -2.607,  "longitude": 30.467,  "is_local_border": 1, "is_international_border": 0},
		{"description": "Rusumo Border (TZ)",     "country": "Tanzania", "latitude": -2.382,  "longitude": 30.782,  "is_local_border": 1, "is_international_border": 0},
		{"description": "Kasumulu Border (TZ)",   "country": "Tanzania", "latitude": -9.508,  "longitude": 33.870,  "is_local_border": 1, "is_international_border": 0},

		# ── Kenya ─────────────────────────────────────────────────────────────
		{"description": "Mombasa Port",           "country": "Kenya",   "latitude": -4.052,  "longitude": 39.666,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Nairobi CBD",            "country": "Kenya",   "latitude": -1.286,  "longitude": 36.817,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Nairobi ICD (Embakasi)",  "country": "Kenya",   "latitude": -1.318,  "longitude": 36.900,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Nakuru Town",            "country": "Kenya",   "latitude": -0.303,  "longitude": 36.080,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Eldoret Town",           "country": "Kenya",   "latitude": 0.520,   "longitude": 35.270,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Kisumu City",            "country": "Kenya",   "latitude": -0.091,  "longitude": 34.768,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Voi Town",               "country": "Kenya",   "latitude": -3.396,  "longitude": 38.556,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Mtito Andei",            "country": "Kenya",   "latitude": -2.688,  "longitude": 38.174,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Mariakani",              "country": "Kenya",   "latitude": -3.859,  "longitude": 39.466,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Namanga Border (KE)",    "country": "Kenya",   "latitude": -2.540,  "longitude": 36.793,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Holili Border (KE)",     "country": "Kenya",   "latitude": -3.310,  "longitude": 37.660,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Lunga Lunga Border (KE)","country": "Kenya",   "latitude": -4.564,  "longitude": 39.128,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Isebania Border (KE)",   "country": "Kenya",   "latitude": -1.249,  "longitude": 34.407,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Malaba Border (KE)",     "country": "Kenya",   "latitude": 0.636,   "longitude": 34.284,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Busia Border (KE)",      "country": "Kenya",   "latitude": 0.460,   "longitude": 34.111,  "is_local_border": 0, "is_international_border": 1},

		# ── Uganda ────────────────────────────────────────────────────────────
		{"description": "Kampala City",           "country": "Uganda",  "latitude": 0.347,   "longitude": 32.582,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Jinja Town",             "country": "Uganda",  "latitude": 0.440,   "longitude": 33.204,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Tororo Town",            "country": "Uganda",  "latitude": 0.693,   "longitude": 34.180,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Mutukula Border (UG)",   "country": "Uganda",  "latitude": -1.000,  "longitude": 31.450,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Malaba Border (UG)",     "country": "Uganda",  "latitude": 0.636,   "longitude": 34.284,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Busia Border (UG)",      "country": "Uganda",  "latitude": 0.460,   "longitude": 34.090,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Elegu Border (UG)",      "country": "Uganda",  "latitude": 3.567,   "longitude": 31.833,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Katuna Border (UG)",     "country": "Uganda",  "latitude": -1.261,  "longitude": 29.688,  "is_local_border": 0, "is_international_border": 1},

		# ── Rwanda ────────────────────────────────────────────────────────────
		{"description": "Kigali City",            "country": "Rwanda",  "latitude": -1.940,  "longitude": 29.874,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Rusumo Border (RW)",     "country": "Rwanda",  "latitude": -2.382,  "longitude": 30.782,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Gatuna Border (RW)",     "country": "Rwanda",  "latitude": -1.261,  "longitude": 29.688,  "is_local_border": 0, "is_international_border": 1},

		# ── Burundi ───────────────────────────────────────────────────────────
		{"description": "Bujumbura City",         "country": "Burundi", "latitude": -3.361,  "longitude": 29.359,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Kobero Border (BI)",     "country": "Burundi", "latitude": -2.607,  "longitude": 30.467,  "is_local_border": 0, "is_international_border": 1},

		# ── Zambia ────────────────────────────────────────────────────────────
		{"description": "Lusaka City",            "country": "Zambia",  "latitude": -15.416, "longitude": 28.282,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Kapiri Mposhi",          "country": "Zambia",  "latitude": -14.971, "longitude": 28.682,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Mpika Town",             "country": "Zambia",  "latitude": -11.840, "longitude": 31.470,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Serenje Town",           "country": "Zambia",  "latitude": -13.230, "longitude": 30.228,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Nakonde Border (ZM)",    "country": "Zambia",  "latitude": -9.348,  "longitude": 32.767,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Kasumbalesa Border (ZM)","country": "Zambia",  "latitude": -12.600, "longitude": 28.529,  "is_local_border": 0, "is_international_border": 1},

		# ── DRC ───────────────────────────────────────────────────────────────
		{"description": "Lubumbashi City",        "country": "Congo, The Democratic Republic of the", "latitude": -11.667, "longitude": 27.467, "is_local_border": 0, "is_international_border": 0},
		{"description": "Kasumbalesa Border (CD)","country": "Congo, The Democratic Republic of the", "latitude": -12.600, "longitude": 28.529, "is_local_border": 0, "is_international_border": 1},

		# ── Malawi ────────────────────────────────────────────────────────────
		{"description": "Lilongwe City",          "country": "Malawi",  "latitude": -13.963, "longitude": 33.774,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Blantyre City",          "country": "Malawi",  "latitude": -15.786, "longitude": 35.005,  "is_local_border": 0, "is_international_border": 0},
		{"description": "Songwe Border (MW)",     "country": "Malawi",  "latitude": -9.508,  "longitude": 33.870,  "is_local_border": 0, "is_international_border": 1},
		{"description": "Mchinji Border (MW)",    "country": "Malawi",  "latitude": -13.797, "longitude": 32.897,  "is_local_border": 0, "is_international_border": 1},

		# ── Mozambique ────────────────────────────────────────────────────────
		{"description": "Maputo City",            "country": "Mozambique", "latitude": -25.966, "longitude": 32.573, "is_local_border": 0, "is_international_border": 0},
		{"description": "Beira Port",             "country": "Mozambique", "latitude": -19.843, "longitude": 34.871, "is_local_border": 0, "is_international_border": 0},
		{"description": "Nacala Port",            "country": "Mozambique", "latitude": -14.543, "longitude": 40.673, "is_local_border": 0, "is_international_border": 0},

		# ── South Sudan ───────────────────────────────────────────────────────
		{"description": "Juba City",              "country": "South Sudan", "latitude": 4.851, "longitude": 31.580, "is_local_border": 0, "is_international_border": 0},
		{"description": "Nimule Border (SS)",     "country": "South Sudan", "latitude": 3.593, "longitude": 31.799, "is_local_border": 0, "is_international_border": 1},
	]
	for loc in locations:
		if not frappe.db.exists("Trip Locations", loc["description"]):
			doc = frappe.get_doc({"doctype": "Trip Locations", **loc})
			doc.insert(ignore_permissions=True)
	frappe.db.commit()


# ── 5b. Transport Locations ─────────────────────────────────────────────────

def create_transport_locations():
	"""Create transport locations (city-level destinations for orders)."""
	transport_locs = [
		# Tanzania
		{"location": "Dar es Salaam",  "country": "Tanzania"},
		{"location": "Tanga",          "country": "Tanzania"},
		{"location": "Morogoro",       "country": "Tanzania"},
		{"location": "Dodoma",         "country": "Tanzania"},
		{"location": "Arusha",         "country": "Tanzania"},
		{"location": "Moshi",          "country": "Tanzania"},
		{"location": "Mwanza",         "country": "Tanzania"},
		{"location": "Mbeya",          "country": "Tanzania"},
		{"location": "Iringa",         "country": "Tanzania"},
		{"location": "Shinyanga",      "country": "Tanzania"},
		{"location": "Tabora",         "country": "Tanzania"},
		{"location": "Kigoma",         "country": "Tanzania"},
		{"location": "Songea",         "country": "Tanzania"},
		{"location": "Lindi",          "country": "Tanzania"},
		{"location": "Mtwara",         "country": "Tanzania"},
		{"location": "Singida",        "country": "Tanzania"},
		{"location": "Kahama",         "country": "Tanzania"},
		{"location": "Isaka",          "country": "Tanzania"},
		# Kenya
		{"location": "Mombasa",        "country": "Kenya"},
		{"location": "Nairobi",        "country": "Kenya"},
		{"location": "Nakuru",         "country": "Kenya"},
		{"location": "Eldoret",        "country": "Kenya"},
		{"location": "Kisumu",         "country": "Kenya"},
		# Uganda
		{"location": "Kampala",        "country": "Uganda"},
		{"location": "Jinja",          "country": "Uganda"},
		# Rwanda
		{"location": "Kigali",         "country": "Rwanda"},
		# Burundi
		{"location": "Bujumbura",      "country": "Burundi"},
		# Zambia
		{"location": "Lusaka",         "country": "Zambia"},
		{"location": "Kapiri Mposhi",  "country": "Zambia"},
		# DRC
		{"location": "Lubumbashi",     "country": "Congo, The Democratic Republic of the"},
		# Malawi
		{"location": "Lilongwe",       "country": "Malawi"},
		{"location": "Blantyre",       "country": "Malawi"},
		# Mozambique
		{"location": "Maputo",         "country": "Mozambique"},
		{"location": "Beira",          "country": "Mozambique"},
		{"location": "Nacala",         "country": "Mozambique"},
		# South Sudan
		{"location": "Juba",           "country": "South Sudan"},
	]
	for tl in transport_locs:
		_make("Transport Location", tl, unique_field="location")
	frappe.db.commit()


# ── 5c. Trip Routes ────────────────────────────────────────────────────────

def create_trip_routes():
	"""Create common logistics routes in East/Southern Africa with accurate
	distances, fuel estimates and fixed expenses per leg."""

	routes = [
		# ── 1. DSM → Mwanza (via Dodoma) ──────────────────────────────────
		{
			"route_name": "DAR-MWZ | Dar es Salaam → Mwanza",
			"starting_point": "Dar es Salaam",
			"ending_point": "Mwanza",
			"trip_steps": [
				{"location": "Dar es Salaam Port",  "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",            "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",       "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Dodoma City",         "distance": 263, "fuel_consumption_qty": 42,  "location_type": "Transit Stop"},
				{"location": "Nzega Town",          "distance": 265, "fuel_consumption_qty": 43,  "location_type": "Transit Stop"},
				{"location": "Mwanza City",         "distance": 170, "fuel_consumption_qty": 27,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
			],
		},
		# ── 2. DSM → Tunduma/Nakonde (Zambia border) ──────────────────────
		{
			"route_name": "DAR-TND | Dar es Salaam → Tunduma",
			"starting_point": "Dar es Salaam",
			"ending_point": "Tunduma",
			"trip_steps": [
				{"location": "Dar es Salaam Port",  "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",            "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",       "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Iringa Town",         "distance": 300, "fuel_consumption_qty": 48,  "location_type": "Transit Stop"},
				{"location": "Makambako Town",      "distance": 110, "fuel_consumption_qty": 18,  "location_type": "Transit Stop"},
				{"location": "Mbeya City",          "distance": 216, "fuel_consumption_qty": 35,  "location_type": "Transit Stop"},
				{"location": "Tunduma Border",      "distance": 110, "fuel_consumption_qty": 18,  "location_type": "Border Post"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Tunduma Border Fee",             "amount": 30000, "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
			],
		},
		# ── 3. DSM → Lusaka (via Tunduma/Nakonde) ─────────────────────────
		{
			"route_name": "DAR-LSK | Dar es Salaam → Lusaka",
			"starting_point": "Dar es Salaam",
			"ending_point": "Lusaka",
			"trip_steps": [
				{"location": "Dar es Salaam Port",   "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",             "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",        "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Iringa Town",          "distance": 300, "fuel_consumption_qty": 48,  "location_type": "Transit Stop"},
				{"location": "Mbeya City",           "distance": 326, "fuel_consumption_qty": 52,  "location_type": "Transit Stop"},
				{"location": "Tunduma Border",       "distance": 110, "fuel_consumption_qty": 18,  "location_type": "Border Post"},
				{"location": "Nakonde Border (ZM)",  "distance": 2,   "fuel_consumption_qty": 1,   "location_type": "Border Post"},
				{"location": "Mpika Town",           "distance": 410, "fuel_consumption_qty": 66,  "location_type": "Transit Stop"},
				{"location": "Serenje Town",         "distance": 172, "fuel_consumption_qty": 28,  "location_type": "Transit Stop"},
				{"location": "Kapiri Mposhi",        "distance": 225, "fuel_consumption_qty": 36,  "location_type": "Transit Stop"},
				{"location": "Lusaka City",          "distance": 195, "fuel_consumption_qty": 31,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Tunduma Border Fee",             "amount": 30000, "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
				{"expense": "Driver Subsistence (USD)",       "amount": 20,    "party_type": "Driver"},
			],
		},
		# ── 4. DSM → Nairobi (via Namanga) ────────────────────────────────
		{
			"route_name": "DAR-NBO | Dar es Salaam → Nairobi",
			"starting_point": "Dar es Salaam",
			"ending_point": "Nairobi",
			"trip_steps": [
				{"location": "Dar es Salaam Port",   "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",             "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Segera Junction",      "distance": 170, "fuel_consumption_qty": 27,  "location_type": "Transit Stop"},
				{"location": "Same Town",            "distance": 180, "fuel_consumption_qty": 29,  "location_type": "Transit Stop"},
				{"location": "Arusha City",          "distance": 175, "fuel_consumption_qty": 28,  "location_type": "Transit Stop"},
				{"location": "Namanga Border (TZ)",  "distance": 102, "fuel_consumption_qty": 16,  "location_type": "Border Post"},
				{"location": "Namanga Border (KE)",  "distance": 1,   "fuel_consumption_qty": 0,   "location_type": "Border Post"},
				{"location": "Nairobi CBD",          "distance": 165, "fuel_consumption_qty": 26,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Namanga Border Fee",             "amount": 20000, "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
			],
		},
		# ── 5. DSM → Kampala (via Mutukula) ───────────────────────────────
		{
			"route_name": "DAR-KLA | Dar es Salaam → Kampala",
			"starting_point": "Dar es Salaam",
			"ending_point": "Kampala",
			"trip_steps": [
				{"location": "Dar es Salaam Port",   "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",             "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",        "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Dodoma City",          "distance": 263, "fuel_consumption_qty": 42,  "location_type": "Transit Stop"},
				{"location": "Nzega Town",           "distance": 265, "fuel_consumption_qty": 43,  "location_type": "Transit Stop"},
				{"location": "Mwanza City",          "distance": 170, "fuel_consumption_qty": 27,  "location_type": "Transit Stop"},
				{"location": "Mutukula Border (TZ)", "distance": 250, "fuel_consumption_qty": 40,  "location_type": "Border Post"},
				{"location": "Mutukula Border (UG)", "distance": 1,   "fuel_consumption_qty": 0,   "location_type": "Border Post"},
				{"location": "Kampala City",         "distance": 220, "fuel_consumption_qty": 35,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Mutukula Border Fee",            "amount": 25000, "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
				{"expense": "Driver Subsistence (USD)",       "amount": 20,    "party_type": "Driver"},
			],
		},
		# ── 6. DSM → Lubumbashi (via Tunduma/Nakonde/Kasumbalesa) ─────────
		{
			"route_name": "DAR-LBH | Dar es Salaam → Lubumbashi",
			"starting_point": "Dar es Salaam",
			"ending_point": "Lubumbashi",
			"trip_steps": [
				{"location": "Dar es Salaam Port",      "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",                "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",           "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Iringa Town",             "distance": 300, "fuel_consumption_qty": 48,  "location_type": "Transit Stop"},
				{"location": "Mbeya City",              "distance": 326, "fuel_consumption_qty": 52,  "location_type": "Transit Stop"},
				{"location": "Tunduma Border",          "distance": 110, "fuel_consumption_qty": 18,  "location_type": "Border Post"},
				{"location": "Nakonde Border (ZM)",     "distance": 2,   "fuel_consumption_qty": 1,   "location_type": "Border Post"},
				{"location": "Mpika Town",              "distance": 410, "fuel_consumption_qty": 66,  "location_type": "Transit Stop"},
				{"location": "Kapiri Mposhi",           "distance": 397, "fuel_consumption_qty": 64,  "location_type": "Transit Stop"},
				{"location": "Kasumbalesa Border (ZM)", "distance": 350, "fuel_consumption_qty": 56,  "location_type": "Border Post"},
				{"location": "Kasumbalesa Border (CD)", "distance": 1,   "fuel_consumption_qty": 0,   "location_type": "Border Post"},
				{"location": "Lubumbashi City",         "distance": 90,  "fuel_consumption_qty": 14,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Tunduma Border Fee",             "amount": 30000, "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
				{"expense": "Driver Subsistence (USD)",       "amount": 20,    "party_type": "Driver"},
			],
		},
		# ── 7. DSM → Kigali (via Rusumo) ──────────────────────────────────
		{
			"route_name": "DAR-KGL | Dar es Salaam → Kigali",
			"starting_point": "Dar es Salaam",
			"ending_point": "Kigali",
			"trip_steps": [
				{"location": "Dar es Salaam Port",   "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",             "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",        "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Dodoma City",          "distance": 263, "fuel_consumption_qty": 42,  "location_type": "Transit Stop"},
				{"location": "Singida Town",         "distance": 133, "fuel_consumption_qty": 21,  "location_type": "Transit Stop"},
				{"location": "Kahama Town",          "distance": 255, "fuel_consumption_qty": 41,  "location_type": "Transit Stop"},
				{"location": "Rusumo Border (TZ)",   "distance": 350, "fuel_consumption_qty": 56,  "location_type": "Border Post"},
				{"location": "Rusumo Border (RW)",   "distance": 1,   "fuel_consumption_qty": 0,   "location_type": "Border Post"},
				{"location": "Kigali City",          "distance": 160, "fuel_consumption_qty": 26,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
				{"expense": "Driver Subsistence (USD)",       "amount": 20,    "party_type": "Driver"},
			],
		},
		# ── 8. DSM → Bujumbura (via Kabanga/Kobero) ───────────────────────
		{
			"route_name": "DAR-BJM | Dar es Salaam → Bujumbura",
			"starting_point": "Dar es Salaam",
			"ending_point": "Bujumbura",
			"trip_steps": [
				{"location": "Dar es Salaam Port",   "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",             "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",        "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Dodoma City",          "distance": 263, "fuel_consumption_qty": 42,  "location_type": "Transit Stop"},
				{"location": "Nzega Town",           "distance": 265, "fuel_consumption_qty": 43,  "location_type": "Transit Stop"},
				{"location": "Kahama Town",          "distance": 110, "fuel_consumption_qty": 18,  "location_type": "Transit Stop"},
				{"location": "Kabanga Border (TZ)",  "distance": 280, "fuel_consumption_qty": 45,  "location_type": "Border Post"},
				{"location": "Kobero Border (BI)",   "distance": 1,   "fuel_consumption_qty": 0,   "location_type": "Border Post"},
				{"location": "Bujumbura City",       "distance": 180, "fuel_consumption_qty": 29,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
				{"expense": "Driver Subsistence (USD)",       "amount": 20,    "party_type": "Driver"},
			],
		},
		# ── 9. DSM → Mombasa (via Horohoro/Lunga Lunga) ──────────────────
		{
			"route_name": "DAR-MSA | Dar es Salaam → Mombasa",
			"starting_point": "Dar es Salaam",
			"ending_point": "Mombasa",
			"trip_steps": [
				{"location": "Dar es Salaam Port",     "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Bagamoyo",               "distance": 65,  "fuel_consumption_qty": 10,  "location_type": "Transit Stop"},
				{"location": "Tanga Port",             "distance": 235, "fuel_consumption_qty": 38,  "location_type": "Transit Stop"},
				{"location": "Horohoro Border (TZ)",   "distance": 60,  "fuel_consumption_qty": 10,  "location_type": "Border Post"},
				{"location": "Lunga Lunga Border (KE)","distance": 1,   "fuel_consumption_qty": 0,   "location_type": "Border Post"},
				{"location": "Mombasa Port",           "distance": 120, "fuel_consumption_qty": 19,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
			],
		},
		# ── 10. DSM → Juba (via Mutukula/Elegu) ──────────────────────────
		{
			"route_name": "DAR-JUB | Dar es Salaam → Juba",
			"starting_point": "Dar es Salaam",
			"ending_point": "Juba",
			"trip_steps": [
				{"location": "Dar es Salaam Port",   "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",             "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",        "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Dodoma City",          "distance": 263, "fuel_consumption_qty": 42,  "location_type": "Transit Stop"},
				{"location": "Nzega Town",           "distance": 265, "fuel_consumption_qty": 43,  "location_type": "Transit Stop"},
				{"location": "Mwanza City",          "distance": 170, "fuel_consumption_qty": 27,  "location_type": "Transit Stop"},
				{"location": "Mutukula Border (TZ)", "distance": 250, "fuel_consumption_qty": 40,  "location_type": "Border Post"},
				{"location": "Mutukula Border (UG)", "distance": 1,   "fuel_consumption_qty": 0,   "location_type": "Border Post"},
				{"location": "Kampala City",         "distance": 220, "fuel_consumption_qty": 35,  "location_type": "Transit Stop"},
				{"location": "Elegu Border (UG)",    "distance": 475, "fuel_consumption_qty": 76,  "location_type": "Border Post"},
				{"location": "Nimule Border (SS)",   "distance": 2,   "fuel_consumption_qty": 0,   "location_type": "Border Post"},
				{"location": "Juba City",            "distance": 192, "fuel_consumption_qty": 31,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Mutukula Border Fee",            "amount": 25000, "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
				{"expense": "Driver Subsistence (USD)",       "amount": 20,    "party_type": "Driver"},
			],
		},
		# ── 11. Mombasa → Nairobi ─────────────────────────────────────────
		{
			"route_name": "MSA-NBO | Mombasa → Nairobi",
			"starting_point": "Mombasa",
			"ending_point": "Nairobi",
			"trip_steps": [
				{"location": "Mombasa Port",    "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Mariakani",       "distance": 30,  "fuel_consumption_qty": 5,   "location_type": "Transit Stop"},
				{"location": "Voi Town",        "distance": 119, "fuel_consumption_qty": 19,  "location_type": "Transit Stop"},
				{"location": "Mtito Andei",     "distance": 80,  "fuel_consumption_qty": 13,  "location_type": "Transit Stop"},
				{"location": "Nairobi ICD (Embakasi)", "distance": 262, "fuel_consumption_qty": 42, "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
			],
		},
		# ── 12. DSM → Isaka Dry Port ──────────────────────────────────────
		{
			"route_name": "DAR-ISK | Dar es Salaam → Isaka",
			"starting_point": "Dar es Salaam",
			"ending_point": "Isaka",
			"trip_steps": [
				{"location": "Dar es Salaam Port",  "distance": 0,   "fuel_consumption_qty": 0,   "location_type": "Loading Point"},
				{"location": "Chalinze",            "distance": 100, "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Morogoro City",       "distance": 96,  "fuel_consumption_qty": 16,  "location_type": "Transit Stop"},
				{"location": "Dodoma City",         "distance": 263, "fuel_consumption_qty": 42,  "location_type": "Transit Stop"},
				{"location": "Nzega Town",          "distance": 265, "fuel_consumption_qty": 43,  "location_type": "Transit Stop"},
				{"location": "Isaka Dry Port",      "distance": 60,  "fuel_consumption_qty": 10,  "location_type": "Offloading Point"},
			],
			"fixed_expenses": [
				{"expense": "Weigh Bridge Fee",               "amount": 5000,  "party_type": "Driver"},
				{"expense": "Road Toll (Local Highway)",      "amount": 3000,  "party_type": "Driver"},
				{"expense": "Driver Daily Allowance (TZS)",   "amount": 50000, "party_type": "Driver"},
			],
		},
	]

	for route in routes:
		if frappe.db.exists("Trip Routes", route["route_name"]):
			continue
		doc = frappe.get_doc({
			"doctype": "Trip Routes",
			"route_name": route["route_name"],
			"starting_point": route["starting_point"],
			"ending_point": route["ending_point"],
		})
		for step in route["trip_steps"]:
			doc.append("trip_steps", step)
		for exp in route.get("fixed_expenses", []):
			doc.append("fixed_expenses", exp)
		doc.insert(ignore_permissions=True)
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


# ── 8. Transport Settings ───────────────────────────────────────────────────

def set_transport_settings():
	"""Set default values on the Transport Settings singleton."""
	settings = frappe.get_single("Transport Settings")
	changed = False

	defaults = {
		"fuel_item": "Diesel",
		"fuel_expense_account": "Diesel Fuel",
		"fuel_cash_account": "Cash on Hand",
		"default_income_account": "Transport Revenue",
		"default_receivable_account": "Debtors",
		"default_payable_account": "Creditors",
	}
	for field, value in defaults.items():
		if not getattr(settings, field, None):
			setattr(settings, field, value)
			changed = True

	if changed:
		settings.save(ignore_permissions=True)
		frappe.db.commit()


# ── 9. Normalize account currencies ─────────────────────────────────────────

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
