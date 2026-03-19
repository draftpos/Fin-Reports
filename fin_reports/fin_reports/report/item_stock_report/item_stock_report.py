import frappe

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = []

    # Only filter by warehouse at DB level
    db_filters = {}
    if filters.get("warehouse"):
        db_filters["warehouse"] = filters["warehouse"]

    bins = frappe.db.get_all(
        "Bin",
        filters=db_filters,
        fields=["item_code", "warehouse", "actual_qty", "valuation_rate", "stock_value"]
    )

    for b in bins:
        item = frappe.get_doc("Item", b.item_code)
        main_uom = None
        second_uom = None
        second_qty = 0
        units = b.actual_qty or 0
        cost_main = b.valuation_rate or 0
        cost_second = 0

        # Check child UOMs
        for u in item.uoms:
            if u.get("custom_main"):
                main_uom = u.uom
            if u.get("custom_second_uom"):
                second_uom = u.uom
                # Only calculate second UOM if filter matches
                if filters.get("uom") and filters["uom"] != second_uom:
                    continue
                if u.conversion_factor:
                    second_qty = units // u.conversion_factor
                    units = units % u.conversion_factor
                    cost_second = cost_main * u.conversion_factor

        # Skip this row if UOM filter is set and neither main nor second matches
        if filters.get("uom") and filters["uom"] not in (main_uom, second_uom):
            continue

        data.append({
            "item_code": b.item_code,
            "item_name": item.item_name,
            "warehouse": b.warehouse,
            "main_uom": main_uom or "",
            "main_qty": b.actual_qty,
            "valuation_rate_main": cost_main,
            "second_uom": second_uom or "",
            "second_qty": second_qty,
            "valuation_rate_second": cost_second,
            "units": units,
            "total_value": b.stock_value,
        })

    return columns, data


def get_columns():
    return [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item"},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data"},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse"},
        {"label": "Main UOM", "fieldname": "main_uom", "fieldtype": "Data"},
        {"label": "Qty (Main UOM)", "fieldname": "main_qty", "fieldtype": "Float"},
        {"label": "Cost per Unit (Main UOM)", "fieldname": "valuation_rate_main", "fieldtype": "Currency"},
        {"label": "Second UOM", "fieldname": "second_uom", "fieldtype": "Data"},
        {"label": "Qty (Second UOM)", "fieldname": "second_qty", "fieldtype": "Int"},
        {"label": "Cost per Unit (Second UOM)", "fieldname": "valuation_rate_second", "fieldtype": "Currency"},
        {"label": "Units (Remaining)", "fieldname": "units", "fieldtype": "Float"},
        {"label": "Total Value", "fieldname": "total_value", "fieldtype": "Currency"},
    ]