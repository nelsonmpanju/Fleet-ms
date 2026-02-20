from __future__ import unicode_literals
import frappe
from frappe import _


def set_dimension(src_doc, tr_doc, src_child=None, tr_child=None):
    settings = frappe.get_cached_doc("Transport Settings", "Transport Settings")
    dimensions = settings.get("accounting_dimension") or []
    if not dimensions:
        return
    for dim in dimensions:
        if (
            dim.source_doctype == src_doc.doctype
            and dim.target_doctype == tr_doc.doctype
        ):
            value = None

            if dim.source_type == "Field":
                value = src_doc.get(dim.source_field_name)
            elif dim.source_type == "Value":
                value = dim.value
            elif dim.source_type == "Child" and src_child:
                value = src_child.get(dim.child_field_name)

            if dim.target_type == "Main":
                setattr(tr_doc, dim.target_field_name, value)
            elif dim.target_type == "Child" and tr_child:
                setattr(tr_child, dim.target_child_field_name, value)