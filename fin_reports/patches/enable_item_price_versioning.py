import frappe

def execute():
    if frappe.db.exists("DocType", "Item Price"):
        frappe.db.set_value("DocType", "Item Price", "track_changes", 1)
        frappe.db.commit()
