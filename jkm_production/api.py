# Copyright (c) 2023, Finbyz Tech PVT LTD and contributors
# For license information, please see license.txt
import frappe
from frappe.utils import flt
from frappe.contacts.doctype.address.address import get_address_display, get_default_address
from frappe.contacts.doctype.address.address import get_address_display, get_default_address
from frappe.contacts.doctype.contact.contact import get_contact_details, get_default_contact
from frappe.desk.notifications import get_filters_for
from datetime import date
from jinja2 import TemplateSyntaxError
from frappe.model.mapper import get_mapped_doc
from erpnext.accounts.utils import get_fiscal_year, flt
from erpnext.stock.stock_ledger import update_entries_after

@frappe.whitelist()
def pe_on_submit(self, method):
	fwd_uti(self)

def fwd_uti(self):
	for row in self.get('forwards'):
		target_doc = frappe.get_doc("Forward Contract", row.forward_contract)
		if not frappe.db.get_value("Forward Contract Utilization", filters={"parent": row.forward_contract, "voucher_type": "Payment Entry", "voucher_no": self.name}):
			target_doc.append("payment_entries", {
				"date": self.posting_date,
				"party_type": self.party_type,
				"party": self.party,
				"paid_amount" : row.amount_utilized,
				"voucher_type": "Payment Entry",
				"voucher_no" : self.name,
			})
		target_doc.save()
@frappe.whitelist()
def pe_on_cancel(self, method):
	fwd_uti_cancel(self)
	remove_pe_from_brc(self,method)

def remove_pe_from_brc(self,method):
	if frappe.db.exists("DocType", 'BRC Management'):
		voucher_no = self.name
		data = frappe.db.sql(f"""SELECT brc.name as brc , brcp.name
								from `tabBRC Management` as brc
								left join `tabBRC Payment` as brcp on brcp.parent = brc.name     
								where brcp.voucher_type = "Payment Entry" and brcp.voucher_no = '{voucher_no}'
								""", as_dict=1)

		for row in data:
			frappe.db.delete("BRC Payment",row.name)

def fwd_uti_cancel(self):
	if self.name == "ACC-PAY-2022-00220":pass
	for row in self.get('forwards'):
		doc = frappe.get_doc("Forward Contract", row.forward_contract)
		to_remove = [row for row in doc.payment_entries if row.voucher_no == self.name and row.voucher_type == "Payment Entry"]
		[doc.remove(row) for row in to_remove]
		doc.save()


@frappe.whitelist()
def get_party_details(party=None, party_type="Customer", ignore_permissions=True):

	if not party:
		return {}

	if not frappe.db.exists(party_type, party):
		frappe.throw(_("{0}: {1} does not exists").format(party_type, party))

	return _get_party_details(party, party_type, ignore_permissions)

def _get_party_details(party=None, party_type="Customer", ignore_permissions=True):

	out = frappe._dict({
		party_type.lower(): party
	})

	party = out[party_type.lower()]

	if not ignore_permissions and not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted for {0}").format(party), frappe.PermissionError)

	party = frappe.get_doc(party_type, party)
	
	set_address_details(out, party, party_type)
	set_contact_details(out, party, party_type)
	set_other_values(out, party, party_type)
	set_organization_details(out, party, party_type)
	return out


def set_address_details(out, party, party_type):
	billing_address_field = "customer_address" if party_type == "Lead" \
		else party_type.lower() + "_address"
	out[billing_address_field] = get_default_address(party_type, party.name)
	
	# address display
	out.address_display = get_address_display(out[billing_address_field])


def set_contact_details(out, party, party_type):
	out.contact_person = get_default_contact(party_type, party.name)

	if not out.contact_person:
		out.update({
			"contact_person": None,
			"contact_display": None,
			"contact_email": None,
			"contact_mobile": None,
			"contact_phone": None,
			"contact_designation": None,
			"contact_department": None
		})
	else:
		out.update(get_contact_details(out.contact_person))

def set_other_values(out, party, party_type):
	# copy
	if party_type=="Customer":
		to_copy = ["customer_name", "customer_group", "territory", "language"]
	else:
		to_copy = ["supplier_name", "supplier_type", "language"]
	for f in to_copy:
		out[f] = party.get(f)
		
def set_organization_details(out, party, party_type):

	organization = None

	if party_type == 'Lead':
		organization = frappe.db.get_value("Lead", {"name": party.name}, "company_name")
	elif party_type == 'Customer':
		organization = frappe.db.get_value("Customer", {"name": party.name}, "customer_name")
	elif party_type == 'Supplier':
		organization = frappe.db.get_value("Supplier", {"name": party.name}, "supplier_name")

	out.update({'party_name': organization})

@frappe.whitelist()
def get_customer_ref_code(item_code, customer):
	ref_code = frappe.db.get_value("Item Customer Detail", {'parent': item_code, 'customer_name': customer}, 'ref_code')
	return ref_code if ref_code else ''

@frappe.whitelist()
@frappe.whitelist()
def make_courier_management(source_name, target_doc=None):
	doclist = get_mapped_doc(
		"Quotation",
		source_name,
		{
			"Quotation": {
				"doctype": "Inward Sample",
				"validation": {"docstatus": ["=", 1]},
				"field_no_map": ["address_display", "contact_person", "contact_display", "contact_mobile", "contact_email"],
				"field_map":{
					"name" : "party",
					"doctype" : "party_type"
				}
			},
			"Quotation Item": {
				"doctype": "Inward Sample Details",
				"field_map": {
					
				},	
			}
		},
		target_doc,
	)
	
	return doclist

#Roadtepclaimmanagement
import frappe
from frappe import _
@frappe.whitelist()
def si_on_submit(self, method):
	export_lic(self)
	create_jv(self)
	create_brc(self)

@frappe.whitelist()
def si_on_cancel(self, method):
	export_lic_cancel(self)
	cancel_jv(self, method)
	
@frappe.whitelist()
def si_before_save(self,method):
	duty_calculation(self)
	meis_calculation(self)
	cal_total_fob_value(self)
	
@frappe.whitelist()
def pi_on_submit(self, method):
	import_lic(self)
	
@frappe.whitelist()
def pi_on_cancel(self, method):
	import_lic_cancel(self)

def create_jv(self):
	if self.total_duty_drawback:
		drawback_receivable_account = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_receivable_account")
		drawback_income_account = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_income_account")
		drawback_cost_center = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_cost_center")
		if not drawback_receivable_account:
			frappe.throw(_("Set Duty Drawback Receivable Account in Company"))
		elif not drawback_income_account:
			frappe.throw(_("Set Duty Drawback Income Account in Company"))
		elif not drawback_cost_center:
			frappe.throw(_("Set Duty Drawback Cost Center in Company"))
		else:
			jv = frappe.new_doc("Journal Entry")
			jv.voucher_type = "Duty Drawback Entry"
			jv.posting_date = self.posting_date
			jv.company = self.company
			jv.cheque_no = self.name
			jv.cheque_date = self.posting_date
			jv.user_remark = "Duty draw back against " + self.name + " for " + self.customer
			jv.append("accounts", {
				"account": drawback_receivable_account,
				"cost_center": drawback_cost_center,
				"debit_in_account_currency": self.total_duty_drawback
			})
			jv.append("accounts", {
				"account": drawback_income_account,
				"cost_center": drawback_cost_center,
				"credit_in_account_currency": self.total_duty_drawback
			})
			try:
				jv.save(ignore_permissions=True)
				jv.submit()
			except Exception as e:
				frappe.throw(str(e))
			else:
				self.db_set('duty_drawback_',jv.name)

	if self.get('total_meis'):
		meis_receivable_account = frappe.db.get_value("Company", { "company_name": self.company}, "meis_receivable_account")
		meis_income_account = frappe.db.get_value("Company", { "company_name": self.company}, "meis_income_account")
		meis_cost_center = frappe.db.get_value("Company", { "company_name": self.company}, "meis_cost_center")
		if not meis_receivable_account:
			frappe.throw(_("Set RODTEP Receivable Account in Company"))
		elif not meis_income_account:
			frappe.throw(_("Set RODTEP Income Account in Company"))
		elif not meis_cost_center:
			frappe.throw(_("Set RODTEP Cost Center in Company"))
		else:
			meis_jv = frappe.new_doc("Journal Entry")
			meis_jv.voucher_type = "RODTEP Entry"
			meis_jv.posting_date = self.posting_date
			meis_jv.company = self.company
			meis_jv.cheque_no = self.name
			meis_jv.cheque_date = self.posting_date
			meis_jv.user_remark = "RODTEP against " + self.name + " for " + self.customer
			meis_jv.append("accounts", {
				"account": meis_receivable_account,
				"cost_center": meis_cost_center,
				"debit_in_account_currency": self.total_meis
			})
			meis_jv.append("accounts", {
				"account": meis_income_account,
				"cost_center": meis_cost_center,
				"credit_in_account_currency": self.total_meis
			})
			
			try:
				meis_jv.save(ignore_permissions=True)
				meis_jv.submit()
				
			except Exception as e:
				frappe.throw(str(e))
			else:
				self.db_set('rodtep_jv',meis_jv.name)
def cancel_jv(self, method):
	if self.duty_drawback_:
		jv = frappe.get_doc("Journal Entry", self.duty_drawback_)
		jv.cancel()
		self.duty_drawback_ = ''
	if self.get('rodtep_jv'):
		jv = frappe.get_doc("Journal Entry", self.rodtep_jv)
		jv.cancel()
		self.meis_jv = ''
	

def duty_calculation(self):
	total_duty_drawback = 0.0
	if frappe.db.get_value('Address', self.customer_address, 'country') != "India":
		for row in self.items:
			if row.duty_drawback_rate and row.fob_value:
				duty_drawback_amount = flt(row.fob_value * row.duty_drawback_rate / 100.0)
				if row.maximum_cap == 1:
					if row.capped_amount < duty_drawback_amount:
						row.duty_drawback_amount = row.capped_amount
						row.effective_rate = flt(row.capped_amount / row.fob_value * 100.0)
					else:
						row.duty_drawback_amount = duty_drawback_amount
						row.effective_rate = row.duty_drawback_rate
				else:
					row.duty_drawback_amount = duty_drawback_amount
					
			#row.fob_value = flt(row.base_amount)
			row.igst_taxable_value = flt(row.amount)
			total_duty_drawback += flt(row.duty_drawback_amount) or 0.0
			
			
		self.total_duty_drawback = total_duty_drawback

def cal_total_fob_value(self):
	total_fob = 0.0
	for row in self.items:
		row.fob_value = flt(row.base_amount - row.freight - row.insurance)
		if row.fob_value:
			total_fob += flt(row.fob_value)
	self.total_fob_value = flt(flt(total_fob) - (flt(self.freight) * flt(self.conversion_rate)) -(flt(self.insurance) * flt(self.conversion_rate)))
	
	
def meis_calculation(self):
	total_meis = 0.0
	if frappe.db.get_value('Address', self.customer_address, 'country') != "India":
		for row in self.items:
			if row.fob_value and row.meis_rate:
				meis_value = flt(row.fob_value * row.meis_rate / 100.0)
				row.meis_value = meis_value

				total_meis += flt(row.meis_value)
		self.total_meis = total_meis
	
def export_lic(self):
	for row in self.items:
		if row.get('custom_advance_authorisation_license'):
			aal = frappe.get_doc("Advance Authorisation License", row.custom_advance_authorisation_license)
			aal.append("exports", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"quantity": row.qty,
				"uom": row.uom,
				"cif_value" : flt(row.net_amount),
				"fob_value" : flt(row.fob_value),
				"currency" : self.currency,
				"shipping_bill_no": self.shipping_bill_number,
				"shipping_bill_date": self.shipping_bill_date,
				"port_of_loading" : self.custom_port_of_loading,
				"port_of_discharge" : self.custom_port_of_discharge,
				"sales_invoice" : self.name,
			})

			aal.total_export_qty = sum([flt(d.quantity) for d in aal.exports])
			aal.total_export_amount = sum([flt(d.fob_value) for d in aal.exports])
			aal.save()
	# else:
	# 	frappe.db.commit()

def export_lic_cancel(self):
	doc_list = list(set([row.custom_advance_authorisation_license for row in self.items if row.custom_advance_authorisation_license]))

	for doc_name in doc_list:
		doc = frappe.get_doc("Advance Authorisation License", doc_name)
		to_remove = []

		for row in doc.exports:
			if row.parent == doc_name and row.sales_invoice == self.name:
				to_remove.append(row)

		[doc.remove(row) for row in to_remove]
		doc.total_export_qty = sum([flt(d.quantity) for d in doc.exports])
		doc.total_export_amount = sum([flt(d.fob_value) for d in doc.exports])
		doc.save()
	# else:
	# 	frappe.db.commit()

def import_lic(self):
	for row in self.items:
		if row.custom_advance_authorisation_license:
			aal = frappe.get_doc("Advance Authorisation License", row.custom_advance_authorisation_license)
			aal.append("imports", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"quantity": row.qty,
				"uom": row.uom,
				"cif_value" : flt(row.net_amount),
				"currency" : self.currency,
				"port_of_loading" : self.custom_port_of_loading,
				"port_of_discharge" : self.custom_port_of_discharge,
				"purchase_invoice" : self.name,
			})

			aal.total_import_qty = sum([flt(d.quantity) for d in aal.imports])
			aal.total_import_amount = sum([flt(d.cif_value) for d in aal.imports])
			aal.save()
	# else:
	# 	frappe.db.commit()

def import_lic_cancel(self):
	doc_list = list(set([row.custom_advance_authorisation_license for row in self.items if row.custom_advance_authorisation_license]))

	for doc_name in doc_list:
		doc = frappe.get_doc("Advance Authorisation License", doc_name)
		to_remove = []

		for row in doc.imports:
			if row.parent == doc_name and row.purchase_invoice == self.name:
				to_remove.append(row)

		[doc.remove(row) for row in to_remove]
		doc.total_import_qty = sum([flt(d.quantity) for d in doc.imports])
		doc.total_import_amount = sum([flt(d.cif_value) for d in doc.imports])
		doc.save()
	# else:
	# 	frappe.db.commit()		
	
@frappe.whitelist()
def get_custom_address(party=None, party_type="Customer", ignore_permissions=False):

	if not party:
		return {}

	if not frappe.db.exists(party_type, party):
		frappe.throw(_("{0}: {1} does not exists").format(party_type, party))

	return _get_custom_address(party, party_type, ignore_permissions)

def _get_custom_address(party=None, party_type="Customer", ignore_permissions=False):

	out = frappe._dict({
		party_type.lower(): party
	})

	party = out[party_type.lower()]

	if not ignore_permissions and not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted for {0}").format(party), frappe.PermissionError)

	party = frappe.get_doc(party_type, party)
	
	set_custom_address_details(out, party, party_type)
	return out

def set_custom_address_details(out, party, party_type):
	billing_address_field = "customer_address" if party_type == "Lead" \
		else party_type.lower() + "_address"
	out[billing_address_field] = get_custom_default_address(party_type, party.name)
	
	# address display
	out.address_display = get_custom_address_display(out[billing_address_field])

def get_custom_address_display(address_dict):
	if not address_dict:
		return

	if not isinstance(address_dict, dict):
		address_dict = frappe.db.get_value("Address", address_dict, "*", as_dict=True, cache=True) or {}

	name, template = get_custom_address_templates(address_dict)

	try:
		return frappe.render_template(template, address_dict)
	except TemplateSyntaxError:
		frappe.throw(_("There is an error in your Address Template {0}").format(name))

def get_custom_address_templates(address):
	result = frappe.db.get_value("Address Template", \
		{"country": address.get("country")}, ["name", "template"])

	if not result:
		result = frappe.db.get_value("Address Template", \
			{"is_default": 1}, ["name", "template"])

	if not result:
		frappe.throw(_("No default Address Template found. Please create a new one from Setup > Printing and Branding > Address Template."))
	else:
		return result

def get_custom_default_address(doctype, name, sort_key='is_primary_address'):
	'''Returns default Address name for the given doctype, name'''
	out = frappe.db.sql('''select
			parent, (select name from tabAddress a where a.name=dl.parent) as name,
			(select address_type from tabAddress a where a.name=dl.parent and a.address_type="Consignee-Custom") as address_type
			from
			`tabDynamic Link` dl
			where
			link_doctype=%s and
			link_name=%s and
			parenttype = "Address" and
			(select address_type from tabAddress a where a.name=dl.parent)="Consignee-Custom"
		'''.format(sort_key),(doctype, name))

	if out:
		return sorted(out, key = functools.cmp_to_key(lambda x,y: cmp(y[1], x[1])))[0][0]
	else:
		return None

@frappe.whitelist()
def company_address(company):
	return get_company_address(company)

@frappe.whitelist()
def make_lc(source_name, target_doc=None):
	def postprocess(source, target):
		target.append('contract_term_order', {
				'sales_order': source.name,
				'grand_total': source.grand_total,
				'net_total': source.net_total,
			})

	doclist = get_mapped_doc("Sales Order", source_name, {
			"Sales Order": {
				"doctype": "Contract Term",
				"field_map": {
					"name": "sales_order",
					"transaction_date":"contract_date",
					"grand_total": "contract_amount",
				},	
			},		
		}, target_doc, postprocess)

	return doclist
	
@frappe.whitelist()
def contract_and_lc_filter(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	so_list = filters.get("sales_order_item")

	return frappe.db.sql("""
		SELECT DISTINCT ct.name
		FROM `tabContract Term` AS ct JOIN `tabContract Term Order` as cto ON (cto.parent = ct.name) 
		WHERE cto.sales_order in (%s) """% ', '.join(['%s']*len(so_list)), tuple(so_list))

		
def validate_document_checks(self):
	if self.get('sales_invoice_export_document_item') and not all([row.checked for row in self.get('sales_invoice_export_document_item')]):
		frappe.throw(_("Not all documents are checked for Export Documents"))

	elif self.get('sales_invoice_contract_term_check') and not all([row.checked for row in self.get('sales_invoice_contract_term_check')]):
		frappe.throw(_("Not all documents are checked for Document Checks"))
		
@frappe.whitelist()
def docs_before_naming(self, method):
	from erpnext.accounts.utils import get_fiscal_year

	date = self.get("transaction_date") or self.get("posting_date") or getdate()

	fy = get_fiscal_year(date)[0]
	fiscal = frappe.db.get_value("Fiscal Year", fy, 'fiscal')

	if fiscal:
		self.fiscal = fiscal
	else:
		fy_years = fy.split("-")
		fiscal = fy_years[0][2:] + fy_years[1][2:]
		self.fiscal = fiscal

@frappe.whitelist()
def send_lead_mail(recipients, person, email_template, doc_name):

	doc = frappe.get_doc('Email Template',email_template)
	context = {"person": person}
	message = frappe.render_template(doc.response, context)
	subject = doc.subject
	# email_account = get_outgoing_email_account(True, append_to = "Lead")
	email_account = EmailAccount.find_outgoing(match_by_doctype="Lead", match_by_email=None, _raise_error=True)
	sender = email_account.default_sender

	make(
		recipients = recipients,
		subject = subject,
		content = message,
		sender = sender,
		doctype = "Lead",
		name = doc_name,
		send_email = True
	)

	return "Mail send successfully!"

def create_brc(self):
	if frappe.db.get_value('Address', self.customer_address, 'country') != "India":
		if frappe.db.exists("DocType", "BRC Management"):
			brc = frappe.new_doc("BRC Management")
			brc.invoice_no = self.name
			if not self.is_return:
				if self.shipping_bill_number and self.shipping_bill_date and self.rounded_total:
					brc.append("shipping_bill_details", {
							"shipping_bill": self.shipping_bill_number,
							"shipping_date": self.shipping_bill_date,
							"shipping_bill_amount": self.rounded_total
						})
				try:
					brc.save(ignore_permissions=True)
				except Exception as e:
					frappe.throw(str(e))

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sales_order(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql(""" 
					  Select name 
					  From `tabSales Order` 
					  where docstatus = 1 and name like %(txt)s 
					  """,
					  {"txt": "%%%s%%" % txt},
					  )


@frappe.whitelist()
def get_supplier_quotation_rate(ref):
	rate = frappe.db.get_value("Supplier Quotation Item", ref, "rate")
	return rate