# Copyright (c) 2022, Finbyz Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class CourierManagement(Document):
	def before_save(self):
		if self.link_to == "Customer" and self.party:
			for row in self.sample_items:
				if row.item:
					ref_code = frappe.db.get_value("Item Customer Detail", {'parent': row.item, 'customer_name': self.party}, 'ref_code')
					row.product_name = ref_code