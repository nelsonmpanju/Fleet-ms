"""
Fleet MS — Test Data Seeder (Trip Routes only)
Run: bench --site fleet.local execute vsd_fleet_ms.vsd_fleet_ms.utils.seed.seed_all

NOTE: Accounts, fixed expenses, locations, cargo types and fuel items
are now created automatically during app install (see install.py).
This seeder only creates sample trip routes for testing.
"""
import frappe


def seed_all():
	"""Create sample trip routes that reference the install-time master data."""
	_seed_trip_routes()
	frappe.db.commit()
	print("\n  All seed data created successfully!")


def _seed_trip_routes():
	print("\n-- Trip Routes --")

	def make_route(route_name, starting_point, ending_point, steps, expense_keys):
		if frappe.db.exists("Trip Routes", {"route_name": route_name}):
			print(f"  - Exists   Trip Routes: {route_name}")
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
		print(f"  + Created Trip Routes: {route_name} ({len(steps)} stops, {len(expense_keys)} expenses)")

	# Route 1 — Dar → Nairobi
	make_route(
		route_name="DAR-NBI | Dar es Salaam → Nairobi",
		starting_point="Dar es Salaam Port",
		ending_point="Nairobi CBD",
		steps=[
			{"location": "Dar es Salaam Port",      "location_type": "Loading Point",    "distance": 0,   "fuel_consumption_qty": 0},
			{"location": "Korogwe, Tanga",           "location_type": "Transit Stop",     "distance": 308, "fuel_consumption_qty": 50},
			{"location": "Moshi Town, Kilimanjaro",  "location_type": "Transit Stop",     "distance": 110, "fuel_consumption_qty": 18},
			{"location": "Arusha City",              "location_type": "Transit Stop",     "distance": 82,  "fuel_consumption_qty": 13},
			{"location": "Namanga, Arusha",          "location_type": "Border Post",      "distance": 110, "fuel_consumption_qty": 18},
			{"location": "Nairobi CBD",              "location_type": "Offloading Point", "distance": 170, "fuel_consumption_qty": 27},
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
			{"location": "Dar es Salaam Port", "location_type": "Loading Point",    "distance": 0,   "fuel_consumption_qty": 0},
			{"location": "Dodoma City",         "location_type": "Transit Stop",     "distance": 453, "fuel_consumption_qty": 73},
			{"location": "Mwanza City",         "location_type": "Transit Stop",     "distance": 728, "fuel_consumption_qty": 117},
			{"location": "Mutukula Border",     "location_type": "Border Post",      "distance": 278, "fuel_consumption_qty": 45},
			{"location": "Kampala City",        "location_type": "Offloading Point", "distance": 162, "fuel_consumption_qty": 26},
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
			{"location": "Dar es Salaam Port", "location_type": "Loading Point",    "distance": 0,    "fuel_consumption_qty": 0},
			{"location": "Iringa Town",         "location_type": "Transit Stop",     "distance": 502,  "fuel_consumption_qty": 81},
			{"location": "Mbeya City",          "location_type": "Transit Stop",     "distance": 215,  "fuel_consumption_qty": 35},
			{"location": "Tunduma Border",      "location_type": "Border Post",      "distance": 105,  "fuel_consumption_qty": 17},
			{"location": "Nakonde Border",      "location_type": "Border Post",      "distance": 2,    "fuel_consumption_qty": 0},
			{"location": "Lusaka City",         "location_type": "Offloading Point", "distance": 1070, "fuel_consumption_qty": 172},
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
			{"location": "Dar es Salaam Port", "location_type": "Loading Point",    "distance": 0,   "fuel_consumption_qty": 0},
			{"location": "Dodoma City",         "location_type": "Transit Stop",     "distance": 453, "fuel_consumption_qty": 73},
			{"location": "Mwanza City",         "location_type": "Offloading Point", "distance": 728, "fuel_consumption_qty": 117},
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
