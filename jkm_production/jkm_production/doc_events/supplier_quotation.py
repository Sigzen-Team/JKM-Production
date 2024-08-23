import frappe
from frappe.model.mapper import get_mapped_doc

from erpnext.buying.doctype.supplier_quotation.supplier_quotation import SupplierQuotation
from erpnext.buying.utils import validate_for_items
from frappe.utils import flt


class jkmsupplierquotation(SupplierQuotation):
    def validate(self):
        self.buying_price_list = ''
        self.ignore_pricing_rule = 1
        for row in self.items:
            if row.custom_rate_currency:
                row.rate = row.custom_rate_currency * row.custom_exchange_rate
            if row.custom_packing_size:
                row.custom_total_packages = row.qty / row.custom_packing_size
                
        super().validate()

        if not self.status:
            self.status = "Draft"

        from erpnext.controllers.status_updater import validate_status

        validate_status(self.status, ["Draft", "Submitted", "Stopped", "Cancelled"])

        validate_for_items(self)
        self.validate_with_previous_doc()
        self.validate_uom_is_integer("uom", "qty")
        self.validate_valid_till()

        
        for row in self.items:
            if self.custom_total_transportation_expenses:
                row.custom_local_transport_charges = flt(self.custom_total_transportation_expenses)/self.total_qty
            if self.custom_total_packing_charges:
                row.custom_other_charges = flt(self.custom_total_packing_charges)/self.total_qty
            if self.custom_total_fob_value:
                row.custom_shipping_fob = flt(self.custom_total_fob_value)/self.total_qty
            if self.custom_total_cif_value:
                row.custom_cif_charges = flt(self.custom_total_cif_value)/self.total_qty
            row.custom_total_fob = flt(row.rate) + flt(row.custom_local_transport_charges)  + flt(row.custom_other_charges) + flt(row.custom_shipping_fob)
            row.custom_total_fob_value = flt(row.rate) + flt(row.custom_local_transport_charges) + flt(row.custom_interest_) + flt(row.custom_other_charges) + flt(row.custom_shipping_fob)
            row.custom_total_cif_value  = flt(row.custom_total_fob_value) + flt(row.custom_cif_charges)
            row.custom_final_rate = flt(row.custom_margin) + flt(row.custom_total_cif_value)

        

def on_submit(self, method):
    pass

def validate(self,method):
    update_workflow(self)

    if self.custom_self_pickup:
        if not (self.custom_total_transportation_expenses > 0):
            frappe.throw("Transporter details and charges not updated")

    if self.custom_is_export_inquire_:
        if not (self.custom_total_cif_value > 0 or self.custom_total_fob_value):
            frappe.throw("Export charges is missing, please update Export charges")

def update_workflow(self):
    if self.workflow_state == "Approved":
        for row in self.items: 
            if row.request_for_quotation_item:
                frappe.db.set_value("Request for Quotation Item", row.request_for_quotation_item, "custom_approved_price", row.custom_final_rate)
        
        if self.items[0].get('request_for_quotation'):
            doc = frappe.get_doc("Request for Quotation")
            doc.workflow_state = "Rate Received"
            doc.save()    

    #     rfq = self.items[0].get("request_for_quotation")
    #     if rfq:
    #         data = frappe.db.sql(f"""
    #                     Select rfq.name, sqi.parent
    #                     From `tabRequest for Quotation` as rfq
    #                     left Join `tabSupplier Quotation Item` as sqi On sqi.request_for_quotation = rfq.name
    #                     Where rfq.name = '{rfq}' and sqi.docstatus != 2
    #         """,as_dict=1)
    #         sq = []
    #         reject = []
    #         for row in data:
    #             if row.parent and row.parent not in sq:
    #                 sq.append(row.parent)
    #                 if row.parent != self.name:
    #                     reject.append(row.parent)

    #         for row in reject:
    #             frappe.db.set_value("Supplier Quotation", row, "workflow_state", "Rejected")
    # for row in self.items:
    #     if not row.custom_margin:
    #         frappe.throw(f"Row #{row.idx} : Margin amount is missing")
    #     


def update_rfq_status(self):
    pass
    # rfq = self.items[0].get("request_for_quotation")
    # if rfq:
    #     data = frappe.db.sql(f"""
    #                 select parent
    #                 From `tabSupplier Quotation Item`
    #                 Where docstatus = 1 and request_for_quotation = '{rfq}'
    #     """,as_dict=1)
    #     sq = []
    #     if data:
    #         for row in data:
    #             sq.append(row.parent)
    #     sq = list(set(sq))
    #     doc = frappe.get_doc("Request for Quotation", rfq)
    #     frappe.db.set_value("Request for Quotation", doc.name, "workflow_state", "Completed")

@frappe.whitelist()
def get_contact_detail(contact):
    doc = frappe.get_doc("Contact", contact)
    first_name = doc.first_name if doc.first_name else ''
    last_name = doc.last_name if doc.last_name else ''

    return {
        "custom_email_id" : doc.email_id,
        "custom_mobile_no":doc.phone or doc.mobile_no,
        "custom_contact_person_name": first_name + " " + last_name 
    }

@frappe.whitelist()
def get_transporter_contact_detail(transporter):
    if name := frappe.db.exists("Dynamic Link", {"parenttype": "Contact", "link_name":transporter, "link_doctype" : "Supplier"}):
        contact = frappe.db.get_value("Dynamic Link", name, 'parent')
        return {
            "custom_contact" : contact
        }
    return {
        "custom_contact" : '',
        "custom_email_id" : '',
        "custom_mobile_no":'',
        "custom_contact_person_name": ''
    }