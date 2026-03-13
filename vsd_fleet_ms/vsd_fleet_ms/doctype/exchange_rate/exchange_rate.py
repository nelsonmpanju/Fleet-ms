import frappe
from frappe import _
from frappe.model.document import Document


class ExchangeRate(Document):
    def validate(self):
        self.validate_currencies()
        self.validate_rate()
        self.validate_duplicate()

    def validate_currencies(self):
        if self.from_currency == self.to_currency:
            frappe.throw(_("From Currency and To Currency cannot be the same"))

    def validate_rate(self):
        if self.exchange_rate <= 0:
            frappe.throw(_("Exchange Rate must be greater than 0"))

    def validate_duplicate(self):
        existing = frappe.db.exists(
            "Exchange Rate",
            {
                "from_currency": self.from_currency,
                "to_currency": self.to_currency,
                "date": self.date,
                "name": ("!=", self.name),
            },
        )
        if existing:
            frappe.throw(
                _("Exchange Rate already exists for {0} to {1} on {2}").format(
                    self.from_currency, self.to_currency, self.date
                )
            )
