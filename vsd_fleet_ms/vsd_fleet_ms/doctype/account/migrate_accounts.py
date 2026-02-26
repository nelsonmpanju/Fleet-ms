# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt
"""
One-time migration: harmonise legacy hand-crafted accounts with the
numbered chart of accounts that was seeded on install.

Run with:
  bench --site fleet.local execute \
    vsd_fleet_ms.vsd_fleet_ms.doctype.account.migrate_accounts.run
"""

import frappe
from frappe import _


def run():
	"""
	1. Assign account_numbers to the two legacy root groups (Expenses, Income).
	2. Convert the legacy Petty Cash leaf into a proper group under Assets.
	3. Re-parent and number the legacy fleet expense/income leaf accounts.
	4. Re-parent Driver Cash Advance under Other Current Assets.
	5. Rebuild the nested-set tree so lft/rgt are consistent.
	"""
	frappe.set_user("Administrator")

	_assign_numbers_to_roots()
	_fix_petty_cash()
	_reparent_legacy_leaves()
	_rebuild()

	frappe.db.commit()
	print("Account migration complete.")


# ── helpers ────────────────────────────────────────────────────────────────────

def _set_number(name, number):
	"""Directly patch account_number without triggering full validation."""
	frappe.db.set_value("Account", name, "account_number", number, update_modified=False)


def _reparent(name, new_parent, number=None):
	"""Move a leaf account to a new parent and optionally set its account_number."""
	if not frappe.db.exists("Account", name):
		return
	parent_is_group = frappe.db.get_value("Account", new_parent, "is_group")
	if not parent_is_group:
		print(f"  SKIP reparent '{name}': target parent '{new_parent}' is not a group.")
		return
	frappe.db.set_value("Account", name, "parent_account", new_parent, update_modified=False)
	if number:
		_set_number(name, number)
	print(f"  Moved '{name}' → '{new_parent}'" + (f" [{number}]" if number else ""))


# ── steps ──────────────────────────────────────────────────────────────────────

def _assign_numbers_to_roots():
	"""Give the legacy root groups the account numbers they should have."""
	for name, number in [("Expenses", "5000"), ("Income", "4000")]:
		if frappe.db.exists("Account", name):
			existing = frappe.db.get_value("Account", name, "account_number")
			if not existing:
				_set_number(name, number)
				print(f"  Set account_number={number} on '{name}'")


def _fix_petty_cash():
	"""
	The legacy Petty Cash was a leaf (is_group=0) with no parent.
	Promote it to a group and nest it under Assets so that the
	'Cash on Hand' child can be created beneath it.
	"""
	if not frappe.db.exists("Account", "Petty Cash"):
		return

	acct = frappe.get_doc("Account", "Petty Cash")
	changed = False

	if not acct.is_group:
		# Can only promote if no GL entries reference it directly
		gl_count = frappe.db.count("GL Entry", {"account": "Petty Cash"})
		if gl_count:
			print(
				f"  SKIP: 'Petty Cash' has {gl_count} GL entries — cannot change is_group."
				" Rename or archive it manually."
			)
			return
		acct.is_group = 1
		changed = True
		print("  Promoted 'Petty Cash' to group account.")

	if not acct.parent_account:
		acct.parent_account = "Assets"
		changed = True
		print("  Set parent_account='Assets' on 'Petty Cash'.")

	if not acct.account_number:
		acct.account_number = "1200"
		changed = True

	if changed:
		acct.flags.ignore_validate = True
		acct.save(ignore_permissions=True)
		frappe.db.commit()

	# Now create the Cash on Hand leaf if it doesn't exist yet
	if not frappe.db.exists("Account", "Cash on Hand"):
		frappe.get_doc({
			"doctype": "Account",
			"account_name": "Cash on Hand",
			"account_number": "1210",
			"parent_account": "Petty Cash",
			"is_group": 0,
			"account_type": "Asset",
			"description": "Cash kept for day-to-day expenses",
		}).insert(ignore_permissions=True)
		frappe.db.commit()
		print("  Created 'Cash on Hand' under 'Petty Cash'.")


def _reparent_legacy_leaves():
	"""
	Move legacy fleet expense/income leaf accounts into the correct numbered
	sub-groups, and assign them account numbers.
	"""

	# (account_name, new_parent, account_number)
	expense_moves = [
		("Fuel",                    "Fuel Expenses",           "5111"),
		("Driver Daily Allowance",  "Driver Expenses",         "5211"),
		("Driver Subsistence USD",  "Driver Expenses",         "5212"),
		("Posho",                   "Driver Expenses",         "5213"),
		("Border Crossing Fees",    "Other Expenses",          "5511"),
		("Loading and Offloading",  "Other Expenses",          "5512"),
		("Port Handling Charges",   "Other Expenses",          "5513"),
		("Road Tolls and Levies",   "Administrative Expenses", "5431"),
		("Weigh Bridge Fees",       "Administrative Expenses", "5432"),
	]

	for name, parent, number in expense_moves:
		_reparent(name, parent, number)

	# Income leaf
	_reparent("Sales", "Freight Income", "4111")

	# Asset leaf
	_reparent("Driver Cash Advance", "Other Current Assets", "1410")


def _rebuild():
	"""Rebuild the nested-set lft/rgt indexes after structural changes."""
	from frappe.utils.nestedset import rebuild_tree
	rebuild_tree("Account")
	print("  Rebuilt Account nested-set tree.")
