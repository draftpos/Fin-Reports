import frappe
import json
import re
from frappe import _
from frappe.utils import flt


def parse_price(value):
    """Strip currency symbols/formatting and return float."""
    if value is None:
        return 0.0
    cleaned = re.sub(r'[^\d.-]', '', str(value))
    return flt(cleaned) if cleaned else 0.0


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Date & Time"), "fieldname": "changed_on", "fieldtype": "Datetime", "width": 160},
        {"label": _("Price List"), "fieldname": "price_list", "fieldtype": "Link", "options": "Price List", "width": 150},
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
        {"label": _("Previous Price"), "fieldname": "previous_price", "fieldtype": "Float", "width": 130},
        {"label": _("Current Price"), "fieldname": "current_price", "fieldtype": "Float", "width": 130},
        {"label": _("Changed By"), "fieldname": "changed_by", "fieldtype": "Link", "options": "User", "width": 200}
    ]


def get_data(filters):
    conditions = "v.ref_doctype = 'Item Price'"
    if filters.get("from_date"):
        conditions += " AND DATE(v.creation) >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND DATE(v.creation) <= %(to_date)s"
    if filters.get("changed_by"):
        conditions += " AND v.owner = %(changed_by)s"

    versions = frappe.db.sql("""
        SELECT v.name, v.docname, v.owner, v.creation, v.data
        FROM `tabVersion` v
        WHERE {conditions}
        ORDER BY v.creation DESC
    """.format(conditions=conditions), filters, as_dict=True)

    rows = []
    for version in versions:
        try:
            data = json.loads(version.data) if isinstance(version.data, str) else version.data
        except Exception:
            continue

        price_change = next((c for c in data.get("changed", []) if c[0] == "price_list_rate"), None)
        if not price_change:
            continue

        item_price = frappe.db.get_value("Item Price", version.docname,
            ["item_code", "item_name", "price_list", "currency"], as_dict=True)
        if not item_price:
            continue

        if filters.get("item_code") and item_price.item_code != filters["item_code"]:
            continue
        if filters.get("price_list") and item_price.price_list != filters["price_list"]:
            continue

        previous_price = parse_price(price_change[1])
        current_price = parse_price(price_change[2])

        rows.append({
            "changed_on": version.creation,
            "price_list": item_price.price_list,
            "item_code": item_price.item_code,
            "item_name": item_price.item_name,
            "currency": item_price.currency,
            "previous_price": previous_price,
            "current_price": current_price,
            "changed_by": version.owner
        })
    return rows
