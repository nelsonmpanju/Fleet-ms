# Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TransportSettings(Document):
	def validate(self):
		if self.traccar_enabled:
			if not self.traccar_server_url:
				frappe.throw(_("Traccar Server URL is required when Traccar GPS is enabled."))
			if self.traccar_auth_method == "Token" and not self.traccar_api_token:
				frappe.throw(_("Traccar API Token is required for Token authentication."))
			if self.traccar_auth_method == "Email & Password":
				if not self.traccar_email or not self.traccar_password:
					frappe.throw(_("Traccar Email and Password are required."))
			# Normalize URL: strip trailing slash
			self.traccar_server_url = self.traccar_server_url.rstrip("/")
