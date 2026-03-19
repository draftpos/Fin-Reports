import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item"},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data"},
		{"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse"},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float"},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data"},
		{"label": "Cost per Unit", "fieldname": "valuation_rate", "fieldtype": "Currency"},
		{"label": "Total Value", "fieldname": "total_value", "fieldtype": "Currency"},
	]


def get_data(filters):
	conditions = ""
	if filters.get("warehouse"):
		conditions += " AND b.warehouse = %(warehouse)s"

	data = frappe.db.sql(f"""
		SELECT
			b.item_code,
			i.item_name,
			b.warehouse,
			b.actual_qty as qty,
			i.stock_uom as uom,
			b.valuation_rate,
			b.stock_value as total_value
		FROM `tabBin` b
		JOIN `tabItem` i ON i.name = b.item_code
		WHERE i.disabled = 0
		{conditions}
	""", filters, as_dict=True)

	# Apply global UOM conversion if a filter is selected
	to_uom = filters.get("uom")
	if to_uom:
		for row in data:
			from_uom = row["uom"]
			if from_uom != to_uom:
				# get conversion factor from Stock UOM → filter UOM
				conv_factor = frappe.db.get_value(
					"UOM Conversion Detail",
					{"parent": row["item_code"], "uom": to_uom},
					"conversion_factor"
				)
				if conv_factor:
					# divide by factor, not multiply
					row["qty"] = row["qty"] / conv_factor
					row["valuation_rate"] = row["total_value"] / row["qty"]
					row["uom"] = to_uom
	return data