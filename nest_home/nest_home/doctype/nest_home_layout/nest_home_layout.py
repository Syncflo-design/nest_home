"""Nest Home Layout — one record per Role or Role Profile.

Owns which attention lists and which quick-launch buttons a matching user sees.
Resolution (role profile first, then role, highest priority wins) lives in
nest_home.api so both the page and the landing redirect share one source.
"""

import frappe
from frappe.model.document import Document


class NestHomeLayout(Document):
    def validate(self):
        # Keep the unused link side clean so resolution filters stay simple.
        if self.applies_to == "Role":
            self.role_profile = None
        elif self.applies_to == "Role Profile":
            self.role = None
