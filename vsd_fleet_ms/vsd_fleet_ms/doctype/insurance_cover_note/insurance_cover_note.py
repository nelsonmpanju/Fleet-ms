# Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, today


class InsuranceCoverNote(Document):
	def before_save(self):
		if self.cover_note_end_date:
			self.days_to_expiry = date_diff(self.cover_note_end_date, today())
			if self.days_to_expiry < 0:
				self.status = "Expired"
			elif self.days_to_expiry <= 30:
				self.status = "Expiring Soon"
			else:
				self.status = "Active"
