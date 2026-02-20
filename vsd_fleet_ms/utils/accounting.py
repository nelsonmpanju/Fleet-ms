import frappe
from frappe.utils import flt


def get_exchange_rate(from_currency, to_currency):
    if not from_currency or not to_currency or from_currency == to_currency:
        return 1

    direct = frappe.db.get_value(
        "Exchange Rate",
        {"from_currency": from_currency, "to_currency": to_currency, "enabled": 1},
        "exchange_rate",
        order_by="modified desc",
    )
    if direct:
        return flt(direct)

    reverse = frappe.db.get_value(
        "Exchange Rate",
        {"from_currency": to_currency, "to_currency": from_currency, "enabled": 1},
        "exchange_rate",
        order_by="modified desc",
    )
    if reverse:
        rate = flt(reverse)
        return (1 / rate) if rate else 1

    return 1
