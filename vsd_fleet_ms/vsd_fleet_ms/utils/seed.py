"""
Fleet MS — Test Data Seeder
Run: bench --site fleet.local execute vsd_fleet_ms.vsd_fleet_ms.utils.seed.seed_all
"""
import frappe


def _make(doctype, data, unique_field="name"):
	"""Insert if not already exists; return the doc."""
	key = data.get(unique_field) or data.get("name")
	if not frappe.db.exists(doctype, key):
		doc = frappe.get_doc({"doctype": doctype, **data})
		doc.insert(ignore_permissions=True)
		print(f"  ✓ Created {doctype}: {key}")
		return doc
	else:
		print(f"  – Exists   {doctype}: {key}")
		return frappe.get_doc(doctype, key)


def seed_all():
	# ───────────────────────────────────────────────────
	# 1. TRIP LOCATION TYPES
	# ───────────────────────────────────────────────────
	print("\n── Trip Location Types ──")
	location_types = [
		{"location_type": "Loading Point",    "loading_date": 1,    "arrival_date": 1},
		{"location_type": "Offloading Point", "offloading_date": 1, "arrival_date": 1},
		{"location_type": "Border Post",      "arrival_date": 1,    "departure_date": 1},
		{"location_type": "Transit Stop",     "arrival_date": 1,    "departure_date": 1},
		{"location_type": "Destination Port", "arrival_date": 1,    "offloading_date": 1},
	]
	for lt in location_types:
		_make("Trip Locations Type", lt, unique_field="location_type")

	# ───────────────────────────────────────────────────
	# 2. TRIP LOCATIONS
	# ───────────────────────────────────────────────────
	print("\n── Trip Locations ──")
	locations = [
		# Tanzania
		{"description": "Dar es Salaam Port",       "country": "Tanzania", "latitude": -6.824,  "longitude": 39.288},
		{"description": "Arusha City",              "country": "Tanzania", "latitude": -3.387,  "longitude": 36.682},
		{"description": "Dodoma City",              "country": "Tanzania", "latitude": -6.173,  "longitude": 35.739},
		{"description": "Mwanza City",              "country": "Tanzania", "latitude": -2.516,  "longitude": 32.900},
		{"description": "Iringa Town",              "country": "Tanzania", "latitude": -7.770,  "longitude": 35.692},
		{"description": "Mbeya City",               "country": "Tanzania", "latitude": -8.900,  "longitude": 33.460},
		{"description": "Tunduma Border",           "country": "Tanzania", "latitude": -9.300,  "longitude": 32.770},
		{"description": "Mutukula Border",          "country": "Tanzania", "latitude": -1.014,  "longitude": 31.372},
		# Kenya
		{"description": "Nairobi CBD",              "country": "Kenya",    "latitude": -1.286,  "longitude": 36.817},
		{"description": "Mombasa Port",             "country": "Kenya",    "latitude": -4.052,  "longitude": 39.666},
		# Uganda
		{"description": "Kampala City",             "country": "Uganda",   "latitude": 0.347,   "longitude": 32.582},
		{"description": "Busia Border",             "country": "Uganda",   "latitude": 0.460,   "longitude": 34.090},
		# Zambia
		{"description": "Lusaka City",              "country": "Zambia",   "latitude": -15.416, "longitude": 28.282},
		{"description": "Nakonde Border",           "country": "Zambia",   "latitude": -9.348,  "longitude": 32.767},
	]
	for loc in locations:
		_make("Trip Locations", loc, unique_field="description")

	# ───────────────────────────────────────────────────
	# 3. ACCOUNTS
	# ───────────────────────────────────────────────────
	print("\n── Accounts ──")
	accounts = [
		{"account_name": "Petty Cash",              "account_type": "Asset",   "account_currency": "TZS"},
		{"account_name": "Driver Cash Advance",     "account_type": "Asset",   "account_currency": "TZS"},
		{"account_name": "Driver Daily Allowance",  "account_type": "Expense", "account_currency": "TZS", "parent_account": "Expenses"},
		{"account_name": "Driver Subsistence USD",  "account_type": "Expense", "account_currency": "USD", "parent_account": "Expenses"},
		{"account_name": "Road Tolls and Levies",   "account_type": "Expense", "account_currency": "TZS", "parent_account": "Expenses"},
		{"account_name": "Border Crossing Fees",    "account_type": "Expense", "account_currency": "TZS", "parent_account": "Expenses"},
		{"account_name": "Port Handling Charges",   "account_type": "Expense", "account_currency": "TZS", "parent_account": "Expenses"},
		{"account_name": "Weigh Bridge Fees",       "account_type": "Expense", "account_currency": "TZS", "parent_account": "Expenses"},
		{"account_name": "Loading and Offloading",  "account_type": "Expense", "account_currency": "TZS", "parent_account": "Expenses"},
	]
	for acc in accounts:
		_make("Account", acc, unique_field="account_name")

	# ───────────────────────────────────────────────────
	# 4. CARGO TYPES
	# ───────────────────────────────────────────────────
	print("\n── Cargo Types ──")
	# permit_type valid options: Local Import, Transit Import, Local Export,
	#                            Transit Export, Border Exit, Border Entry
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
			print(f"  ✓ Created Cargo Types: {ct['cargo_name']}")
		else:
			print(f"  – Exists   Cargo Types: {ct['cargo_name']}")

	# ───────────────────────────────────────────────────
	# 5. FIXED EXPENSES
	# ───────────────────────────────────────────────────
	print("\n── Fixed Expenses ──")
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

	# ───────────────────────────────────────────────────
	# 6. TRIP ROUTES
	# ───────────────────────────────────────────────────
	print("\n── Trip Routes ──")

	def make_route(route_name, starting_point, ending_point, steps, expense_keys):
		if frappe.db.exists("Trip Routes", {"route_name": route_name}):
			print(f"  – Exists   Trip Routes: {route_name}")
			return
		doc = frappe.get_doc({
			"doctype":        "Trip Routes",
			"route_name":     route_name,
			"starting_point": starting_point,
			"ending_point":   ending_point,
		})
		for step in steps:
			doc.append("trip_steps", step)
		for ek in expense_keys:
			fe = frappe.get_doc("Fixed Expenses", ek["expense"])
			doc.append("fixed_expenses", {
				"expense":    ek["expense"],
				"currency":   fe.currency,
				"amount":     fe.fixed_value,
				"party_type": ek.get("party_type", "Driver"),
			})
		doc.insert(ignore_permissions=True)
		print(f"  ✓ Created Trip Routes: {route_name} ({len(steps)} stops, {len(expense_keys)} expenses)")

	# Route 1 — Dar → Nairobi
	make_route(
		route_name="DAR-NBI | Dar es Salaam → Nairobi",
		starting_point="Dar es Salaam Port",
		ending_point="Nairobi CBD",
		steps=[
			{"location": "Dar es Salaam Port",      "location_type": "Loading Point",   "distance": 0,   "fuel_consumption_qty": 0},
			{"location": "Korogwe, Tanga",           "location_type": "Transit Stop",    "distance": 308, "fuel_consumption_qty": 50},
			{"location": "Moshi Town, Kilimanjaro",  "location_type": "Transit Stop",    "distance": 110, "fuel_consumption_qty": 18},
			{"location": "Arusha City",              "location_type": "Transit Stop",    "distance": 82,  "fuel_consumption_qty": 13},
			{"location": "Namanga, Arusha",          "location_type": "Border Post",     "distance": 110, "fuel_consumption_qty": 18},
			{"location": "Nairobi CBD",              "location_type": "Offloading Point","distance": 170, "fuel_consumption_qty": 27},
		],
		expense_keys=[
			{"expense": "Driver Daily Allowance (TZS)", "party_type": "Driver"},
			{"expense": "Driver Subsistence (USD)",      "party_type": "Driver"},
			{"expense": "DSM Port Entry Fee",            "party_type": "Supplier"},
			{"expense": "Road Toll (Local Highway)",     "party_type": "Supplier"},
			{"expense": "Namanga Border Fee",            "party_type": "Supplier"},
			{"expense": "Weigh Bridge Fee",              "party_type": "Supplier"},
		],
	)

	# Route 2 — Dar → Kampala
	make_route(
		route_name="DAR-KMP | Dar es Salaam → Kampala",
		starting_point="Dar es Salaam Port",
		ending_point="Kampala City",
		steps=[
			{"location": "Dar es Salaam Port", "location_type": "Loading Point",   "distance": 0,   "fuel_consumption_qty": 0},
			{"location": "Dodoma City",         "location_type": "Transit Stop",    "distance": 453, "fuel_consumption_qty": 73},
			{"location": "Mwanza City",         "location_type": "Transit Stop",    "distance": 728, "fuel_consumption_qty": 117},
			{"location": "Mutukula Border",     "location_type": "Border Post",     "distance": 278, "fuel_consumption_qty": 45},
			{"location": "Kampala City",        "location_type": "Offloading Point","distance": 162, "fuel_consumption_qty": 26},
		],
		expense_keys=[
			{"expense": "Driver Daily Allowance (TZS)", "party_type": "Driver"},
			{"expense": "Driver Subsistence (USD)",      "party_type": "Driver"},
			{"expense": "DSM Port Entry Fee",            "party_type": "Supplier"},
			{"expense": "Road Toll (Local Highway)",     "party_type": "Supplier"},
			{"expense": "Mutukula Border Fee",           "party_type": "Supplier"},
			{"expense": "Weigh Bridge Fee",              "party_type": "Supplier"},
			{"expense": "Loading and Offloading Fee",    "party_type": "Supplier"},
		],
	)

	# Route 3 — Dar → Lusaka
	make_route(
		route_name="DAR-LUS | Dar es Salaam → Lusaka",
		starting_point="Dar es Salaam Port",
		ending_point="Lusaka City",
		steps=[
			{"location": "Dar es Salaam Port", "location_type": "Loading Point",   "distance": 0,    "fuel_consumption_qty": 0},
			{"location": "Iringa Town",         "location_type": "Transit Stop",    "distance": 502,  "fuel_consumption_qty": 81},
			{"location": "Mbeya City",          "location_type": "Transit Stop",    "distance": 215,  "fuel_consumption_qty": 35},
			{"location": "Tunduma Border",      "location_type": "Border Post",     "distance": 105,  "fuel_consumption_qty": 17},
			{"location": "Nakonde Border",      "location_type": "Border Post",     "distance": 2,    "fuel_consumption_qty": 0},
			{"location": "Lusaka City",         "location_type": "Offloading Point","distance": 1070, "fuel_consumption_qty": 172},
		],
		expense_keys=[
			{"expense": "Driver Daily Allowance (TZS)", "party_type": "Driver"},
			{"expense": "Driver Subsistence (USD)",      "party_type": "Driver"},
			{"expense": "DSM Port Entry Fee",            "party_type": "Supplier"},
			{"expense": "Road Toll (Local Highway)",     "party_type": "Supplier"},
			{"expense": "Tunduma Border Fee",            "party_type": "Supplier"},
			{"expense": "Weigh Bridge Fee",              "party_type": "Supplier"},
			{"expense": "Loading and Offloading Fee",    "party_type": "Supplier"},
		],
	)

	# Route 4 — Dar → Mwanza (local)
	make_route(
		route_name="DAR-MWZ | Dar es Salaam → Mwanza",
		starting_point="Dar es Salaam Port",
		ending_point="Mwanza City",
		steps=[
			{"location": "Dar es Salaam Port", "location_type": "Loading Point",   "distance": 0,   "fuel_consumption_qty": 0},
			{"location": "Dodoma City",         "location_type": "Transit Stop",    "distance": 453, "fuel_consumption_qty": 73},
			{"location": "Mwanza City",         "location_type": "Offloading Point","distance": 728, "fuel_consumption_qty": 117},
		],
		expense_keys=[
			{"expense": "Driver Daily Allowance (TZS)", "party_type": "Driver"},
			{"expense": "DSM Port Entry Fee",            "party_type": "Supplier"},
			{"expense": "Road Toll (Local Highway)",     "party_type": "Supplier"},
			{"expense": "Weigh Bridge Fee",              "party_type": "Supplier"},
		],
	)

	# Route 5 — Mombasa → Kampala
	make_route(
		route_name="MBA-KMP | Mombasa → Kampala",
		starting_point="Mombasa Port",
		ending_point="Kampala City",
		steps=[
			{"location": "Mombasa Port",  "location_type": "Destination Port", "distance": 0,   "fuel_consumption_qty": 0},
			{"location": "Nairobi CBD",   "location_type": "Transit Stop",     "distance": 488, "fuel_consumption_qty": 78},
			{"location": "Busia Border",  "location_type": "Border Post",      "distance": 350, "fuel_consumption_qty": 56},
			{"location": "Kampala City",  "location_type": "Offloading Point", "distance": 120, "fuel_consumption_qty": 19},
		],
		expense_keys=[
			{"expense": "Driver Subsistence (USD)",  "party_type": "Driver"},
			{"expense": "Road Toll (Local Highway)", "party_type": "Supplier"},
			{"expense": "Weigh Bridge Fee",          "party_type": "Supplier"},
		],
	)

	frappe.db.commit()
	print("\n✅ All test data created successfully!")
