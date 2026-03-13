import frappe
from frappe.utils import flt, getdate, today


def get_company_currency():
    """Return the company (base) currency from Transport Settings."""
    currency = frappe.db.get_single_value("Transport Settings", "default_currency")
    if currency:
        return currency
    return "TZS"


def boot_session(bootinfo):
    """Inject company currency into frappe.boot so JS can access it."""
    bootinfo.vsd_company_currency = get_company_currency()


@frappe.whitelist()
def get_exchange_rate_api(from_currency, to_currency, date=None):
    """Whitelisted wrapper so JS forms can fetch exchange rates."""
    return get_exchange_rate(from_currency, to_currency, date)


def get_exchange_rate(from_currency, to_currency, date=None):
    """Get exchange rate between two currencies for a given date.

    Lookup order:
    1. Exact date match (direct, then reverse)
    2. Nearest earlier date (direct, then reverse)
    3. Returns 1 as fallback
    """
    if not from_currency or not to_currency or from_currency == to_currency:
        return 1

    if not date:
        date = today()

    date = getdate(date)

    # Try direct rate for exact date
    rate = _get_rate(from_currency, to_currency, date)
    if rate:
        return flt(rate)

    # Try reverse rate for exact date
    rate = _get_rate(to_currency, from_currency, date)
    if rate:
        return (1 / flt(rate)) if flt(rate) else 1

    # Try nearest earlier date - direct
    rate = _get_nearest_rate(from_currency, to_currency, date)
    if rate:
        return flt(rate)

    # Try nearest earlier date - reverse
    rate = _get_nearest_rate(to_currency, from_currency, date)
    if rate:
        return (1 / flt(rate)) if flt(rate) else 1

    return 1


def _get_rate(from_currency, to_currency, date):
    """Get exchange rate for exact date."""
    return frappe.db.get_value(
        "Exchange Rate",
        {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "date": date,
            "enabled": 1,
        },
        "exchange_rate",
    )


def _get_nearest_rate(from_currency, to_currency, date):
    """Get the most recent exchange rate on or before the given date."""
    return frappe.db.get_value(
        "Exchange Rate",
        {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "date": ("<=", date),
            "enabled": 1,
        },
        "exchange_rate",
        order_by="date desc",
    )
