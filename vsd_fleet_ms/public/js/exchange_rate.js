// Shared exchange rate utility for all VSD Fleet MS doctypes
if (!window.vsd_fleet_ms) {
    window.vsd_fleet_ms = {};
}

/**
 * Fetch exchange rate for the given form's currency and posting_date,
 * and set the conversion_rate field.
 *
 * @param {Object} frm - Frappe form object
 * @param {string} [currency_field="currency"] - Field name for currency
 * @param {string} [date_field="posting_date"] - Field name for date
 */
vsd_fleet_ms.fetch_exchange_rate = function (frm, currency_field, date_field) {
    currency_field = currency_field || "currency";
    date_field = date_field || "posting_date";

    const currency = frm.doc[currency_field];
    const posting_date = frm.doc[date_field];
    const company_currency = frappe.boot.vsd_company_currency || "TZS";

    if (!currency || !posting_date) return;

    // Same currency → rate is always 1
    if (currency === company_currency) {
        frm.set_value("conversion_rate", 1);
        return;
    }

    frappe.call({
        method: "vsd_fleet_ms.utils.accounting.get_exchange_rate_api",
        args: {
            from_currency: currency,
            to_currency: company_currency,
            date: posting_date,
        },
        callback: function (r) {
            if (r.message !== undefined && r.message !== null) {
                frm.set_value("conversion_rate", r.message);
            }
        },
    });
};
