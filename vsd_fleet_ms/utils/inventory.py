from __future__ import annotations

import frappe
from frappe.utils import flt, get_datetime, nowdate, nowtime


def get_default_currency() -> str:
    from vsd_fleet_ms.utils.accounting import get_company_currency
    return get_company_currency()


def _posting_dt(posting_date: str, posting_time: str):
    return get_datetime(f"{posting_date} {posting_time}")


def get_stock_key(item_code: str, warehouse: str) -> str:
    return f"{item_code}::{warehouse}"


def get_or_create_stock_balance(item_code: str, warehouse: str):
    key = get_stock_key(item_code, warehouse)
    existing = frappe.db.get_value("Stock Balance", key)
    if existing:
        return frappe.get_doc("Stock Balance", existing)

    doc = frappe.new_doc("Stock Balance")
    doc.stock_key = key
    doc.item_code = item_code
    doc.warehouse = warehouse
    doc.currency = get_default_currency()
    doc.actual_qty = 0
    doc.valuation_rate = 0
    doc.stock_value = 0
    doc.last_posting_date = nowdate()
    doc.last_posting_time = nowtime()
    doc.insert(ignore_permissions=True)
    return doc


def get_latest_ledger_datetime(item_code: str, warehouse: str):
    row = frappe.db.sql(
        """
        select posting_date, posting_time
        from `tabStock Ledger Entry`
        where item_code = %s and warehouse = %s
        order by posting_date desc, posting_time desc, creation desc
        limit 1
        """,
        (item_code, warehouse),
        as_dict=True,
    )
    if not row:
        return None
    return _posting_dt(str(row[0].posting_date), str(row[0].posting_time))


def validate_non_backdated(item_code: str, warehouse: str, posting_date: str, posting_time: str):
    latest = get_latest_ledger_datetime(item_code, warehouse)
    if not latest:
        return

    current = _posting_dt(posting_date, posting_time)
    if current < latest:
        frappe.throw(
            f"Backdated stock posting not allowed for Item {item_code} in Warehouse {warehouse}. "
            "Please post on/after the latest stock transaction time."
        )


def validate_warehouse(warehouse: str):
    if not warehouse:
        frappe.throw("Warehouse is required for stock posting.")

    is_group = frappe.db.get_value("Warehouse", warehouse, "is_group")
    if is_group:
        frappe.throw(f"Warehouse {warehouse} is a group node. Select a leaf warehouse.")


def _resolve_incoming_rate(item_code: str, incoming_rate: float | None) -> float:
    if flt(incoming_rate):
        return flt(incoming_rate)
    return flt(frappe.db.get_value("Item", item_code, "standard_rate")) or 0


def get_current_valuation_rate(item_code: str, warehouse: str) -> float:
    bal = get_or_create_stock_balance(item_code, warehouse)
    return flt(bal.valuation_rate)


def post_stock_movement(
    *,
    posting_date: str,
    posting_time: str,
    item_code: str,
    warehouse: str,
    actual_qty: float,
    incoming_rate: float | None,
    transaction_type: str,
    voucher_type: str,
    voucher_no: str,
    voucher_detail_no: str | None = None,
    supplier: str | None = None,
    reference_trip: str | None = None,
    remarks: str | None = None,
    is_cancelled_entry: int = 0,
):
    validate_warehouse(warehouse)
    validate_non_backdated(item_code, warehouse, posting_date, posting_time)

    bal = get_or_create_stock_balance(item_code, warehouse)

    prev_qty = flt(bal.actual_qty)
    prev_rate = flt(bal.valuation_rate)
    prev_value = flt(bal.stock_value)
    qty_diff = flt(actual_qty)

    if qty_diff == 0:
        return

    if qty_diff > 0:
        in_rate = _resolve_incoming_rate(item_code, incoming_rate)
        value_diff = qty_diff * in_rate
        new_qty = prev_qty + qty_diff
        new_value = prev_value + value_diff
        valuation_rate = (new_value / new_qty) if new_qty else 0
    else:
        if (prev_qty + qty_diff) < -1e-9:
            frappe.throw(
                f"Insufficient stock for Item {item_code} in Warehouse {warehouse}. "
                f"Available {prev_qty}, requested {abs(qty_diff)}."
            )
        valuation_rate = prev_rate or _resolve_incoming_rate(item_code, incoming_rate)
        value_diff = qty_diff * valuation_rate
        new_qty = prev_qty + qty_diff
        new_value = prev_value + value_diff
        if new_qty <= 0:
            valuation_rate = 0

    sle = frappe.new_doc("Stock Ledger Entry")
    sle.posting_date = posting_date
    sle.posting_time = posting_time
    sle.item_code = item_code
    sle.warehouse = warehouse
    sle.transaction_type = transaction_type
    sle.voucher_type = voucher_type
    sle.voucher_no = voucher_no
    sle.voucher_detail_no = voucher_detail_no
    sle.actual_qty = qty_diff
    sle.qty_after_transaction = new_qty
    sle.incoming_rate = _resolve_incoming_rate(item_code, incoming_rate)
    sle.valuation_rate = valuation_rate
    sle.stock_value_difference = value_diff
    sle.stock_value = new_value
    sle.currency = get_default_currency()
    sle.supplier = supplier
    sle.reference_trip = reference_trip
    sle.remarks = remarks
    sle.is_cancelled_entry = cint(is_cancelled_entry)
    sle.insert(ignore_permissions=True)

    bal.actual_qty = new_qty
    bal.valuation_rate = valuation_rate
    bal.stock_value = new_value
    bal.currency = sle.currency
    bal.last_posting_date = posting_date
    bal.last_posting_time = posting_time
    bal.save(ignore_permissions=True)


def post_purchase_invoice_stock(doc, is_cancel=False):
    if is_cancel:
        posting_date = nowdate()
        posting_time = nowtime()
    else:
        posting_date = str(doc.posting_date or nowdate())
        posting_time = str(getattr(doc, "posting_time", None) or nowtime())
    multiplier = -1 if is_cancel else 1

    for row in doc.items:
        item_info = frappe.db.get_value(
            "Item", row.item_code, ["is_stock_item", "standard_rate"], as_dict=True
        )
        if not item_info or not cint(item_info.is_stock_item):
            continue

        warehouse = row.warehouse or getattr(doc, "set_warehouse", None)
        if not warehouse:
            frappe.throw(f"Warehouse is required for stock item {row.item_code} in Purchase Invoice.")

        post_stock_movement(
            posting_date=posting_date,
            posting_time=posting_time,
            item_code=row.item_code,
            warehouse=warehouse,
            actual_qty=flt(row.qty) * multiplier,
            incoming_rate=flt(row.rate) or flt(item_info.standard_rate),
            transaction_type="Purchase Receipt",
            voucher_type=doc.doctype,
            voucher_no=doc.name,
            voucher_detail_no=row.name,
            supplier=doc.supplier,
            reference_trip=doc.reference_trip,
            remarks=doc.remarks,
            is_cancelled_entry=1 if is_cancel else 0,
        )


def post_stock_entry(doc, is_cancel=False):
    if is_cancel:
        posting_date = nowdate()
        posting_time = nowtime()
    else:
        posting_date = str(doc.posting_date or nowdate())
        posting_time = str(doc.posting_time or nowtime())
    multiplier = -1 if is_cancel else 1
    movement_type = doc.stock_entry_type or doc.purpose or "Material Transfer"

    for row in doc.items:
        qty = flt(row.qty)
        if qty <= 0:
            continue

        row_rate = flt(getattr(row, "basic_rate", 0))
        source_wh = row.s_warehouse or doc.from_warehouse
        target_wh = row.t_warehouse or doc.to_warehouse

        if movement_type == "Material Issue":
            if not source_wh:
                frappe.throw(f"Source Warehouse is required for row {row.idx}.")
            issue_rate = get_current_valuation_rate(row.item_code, source_wh) or row_rate
            post_stock_movement(
                posting_date=posting_date,
                posting_time=posting_time,
                item_code=row.item_code,
                warehouse=source_wh,
                actual_qty=(-qty) * multiplier,
                incoming_rate=issue_rate,
                transaction_type="Material Issue",
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                voucher_detail_no=row.name,
                reference_trip=doc.reference_trip,
                remarks=doc.remarks,
                is_cancelled_entry=1 if is_cancel else 0,
            )

        elif movement_type == "Material Receipt":
            if not target_wh:
                frappe.throw(f"Target Warehouse is required for row {row.idx}.")
            post_stock_movement(
                posting_date=posting_date,
                posting_time=posting_time,
                item_code=row.item_code,
                warehouse=target_wh,
                actual_qty=qty * multiplier,
                incoming_rate=row_rate,
                transaction_type="Material Receipt",
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                voucher_detail_no=row.name,
                reference_trip=doc.reference_trip,
                remarks=doc.remarks,
                is_cancelled_entry=1 if is_cancel else 0,
            )

        else:
            if not source_wh or not target_wh:
                frappe.throw(f"Both Source and Target Warehouse are required for row {row.idx}.")
            if source_wh == target_wh:
                frappe.throw(f"Source and Target Warehouse cannot be same for row {row.idx}.")

            transfer_rate = get_current_valuation_rate(row.item_code, source_wh) or row_rate

            post_stock_movement(
                posting_date=posting_date,
                posting_time=posting_time,
                item_code=row.item_code,
                warehouse=source_wh,
                actual_qty=(-qty) * multiplier,
                incoming_rate=transfer_rate,
                transaction_type="Material Transfer (Out)",
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                voucher_detail_no=row.name,
                reference_trip=doc.reference_trip,
                remarks=doc.remarks,
                is_cancelled_entry=1 if is_cancel else 0,
            )
            post_stock_movement(
                posting_date=posting_date,
                posting_time=posting_time,
                item_code=row.item_code,
                warehouse=target_wh,
                actual_qty=qty * multiplier,
                incoming_rate=transfer_rate,
                transaction_type="Material Transfer (In)",
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                voucher_detail_no=row.name,
                reference_trip=doc.reference_trip,
                remarks=doc.remarks,
                is_cancelled_entry=1 if is_cancel else 0,
            )


def cint(value) -> int:
    return int(flt(value))
