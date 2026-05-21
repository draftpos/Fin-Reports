import frappe


def execute():
    create_module_def()
    create_report_doc()


def create_module_def():
    if not frappe.db.exists("Module Def", "Financial Statements"):
        frappe.get_doc(
            {
                "doctype": "Module Def",
                "module_name": "Financial Statements",
                "app_name": "fin_reports",
            }
        ).insert(ignore_permissions=True)


def create_report_doc():
    report_name = "Custom Profit n Loss"
    if frappe.db.exists("Report", report_name):
        return

    report = frappe.get_doc(
        {
            "doctype": "Report",
            "name": report_name,
            "report_name": report_name,
            "ref_doctype": "GL Entry",
            "report_type": "Script Report",
            "is_standard": "Yes",
            "module": "Financial Statements",
            "disabled": 0,
            "app_name": "fin_reports",
            "roles": [
                {"role": "Accounts User"},
                {"role": "Accounts Manager"},
                {"role": "System Manager"},
            ],
        }
    )
    report.insert(ignore_permissions=True)
