import frappe


def _migrate_child_table(doctype: str):
    table_name = f"tab{doctype}"
    if not frappe.db.table_exists(table_name):
        return

    if not (frappe.db.has_column(doctype, "purchase_order") and frappe.db.has_column(doctype, "purchase_invoice")):
        return

    frappe.db.sql(
        f"""
        update `{table_name}`
        set purchase_invoice = purchase_order
        where ifnull(purchase_invoice, '') = ''
          and ifnull(purchase_order, '') != ''
        """
    )


def execute():
    _migrate_child_table("Fuel Requests Table")
    _migrate_child_table("Fuel Request History")
