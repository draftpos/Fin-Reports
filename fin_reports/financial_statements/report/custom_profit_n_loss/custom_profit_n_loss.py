# Copyright (c) 2026, Fin Reports
# License: MIT

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, getdate

from erpnext.accounts.report.financial_statements import get_columns, get_data, get_period_list


def execute(filters=None):
    filters = frappe._dict(filters or {})
    filters.company = filters.get("company")
    filters.filter_based_on = filters.get("filter_based_on") or "Fiscal Year"
    filters.periodicity = filters.get("periodicity") or "Yearly"
    filters.accumulated_values = cint(filters.get("accumulated_values", 0))
    filters.show_zero_values = cint(filters.get("show_zero_values", 0))
    filters.comparison_period = filters.get("comparison_period") or "None"

    validate_filters(filters)

    period_list = get_period_list(
        filters.from_fiscal_year,
        filters.to_fiscal_year,
        filters.period_start_date,
        filters.period_end_date,
        filters.filter_based_on,
        filters.periodicity,
        company=filters.company,
    )

    currency = filters.presentation_currency or frappe.get_cached_value("Company", filters.company, "default_currency")

    income = get_data(
        filters.company,
        "Income",
        "Credit",
        period_list,
        filters=filters,
        accumulated_values=filters.accumulated_values,
        ignore_closing_entries=True,
    )
    expense = get_data(
        filters.company,
        "Expense",
        "Debit",
        period_list,
        filters=filters,
        accumulated_values=filters.accumulated_values,
        ignore_closing_entries=True,
    )

    compare_label = None
    compare_map = None
    compare_section_totals = {}
    if filters.comparison_period and filters.comparison_period != "None":
        compare_label, compare_map, compare_section_totals = get_comparison_map(filters, period_list)

    data = build_statement_data(
        income or [],
        expense or [],
        period_list,
        currency,
        compare_map,
        compare_section_totals,
        show_zero_values=bool(filters.show_zero_values),
    )
    columns = build_columns(period_list, currency, filters, compare_label)
    report_summary = build_report_summary(data, currency, compare_label)

    return columns, data, None, None, report_summary, None


def validate_filters(filters):
    if not filters.company:
        frappe.throw(_("Company is mandatory"))

    if filters.filter_based_on == "Date Range":
        if not filters.period_start_date or not filters.period_end_date:
            frappe.throw(_("From Date and To Date are mandatory for Date Range"))
        if getdate(filters.period_end_date) < getdate(filters.period_start_date):
            frappe.throw(_("To Date cannot be earlier than From Date"))
    elif filters.filter_based_on == "Fiscal Year":
        if not filters.from_fiscal_year or not filters.to_fiscal_year:
            frappe.throw(_("Start Year and End Year are mandatory for Fiscal Year"))


def build_columns(period_list, currency, filters, compare_label=None):
    columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)

    if not any(col.get("fieldname") == "total" for col in columns):
        columns.append(
            {
                "fieldname": "total",
                "label": _("Total"),
                "fieldtype": "Currency",
                "width": 150,
                "options": "currency",
            }
        )

    if compare_label:
        columns.append(
            {
                "fieldname": "comparison_total",
                "label": _(compare_label),
                "fieldtype": "Currency",
                "width": 150,
                "options": "currency",
            }
        )

    return columns


def build_statement_data(income_rows, expense_rows, period_list, currency, compare_map, compare_section_totals, show_zero_values=False):
    sections = []

    def _clean_source_rows(rows):
        cleaned = []
        for r in rows or []:
            if not r or not r.get("account_name"):
                continue
            # Keep the summary rows as they appear in the user's example
            cleaned.append(r)
        return cleaned

    def identify_section(rows, types, name_subset=None):
        out = []
        for r in rows:
            acc_type = (r.get("account_type") or "").lower().strip()
            acc_name = (r.get("account_name") or "").lower().strip()
            if acc_type in types:
                out.append(r)
            elif name_subset and any(x in acc_name for x in name_subset):
                out.append(r)
        return out

    # 1. Sales Revenue (Direct Income)
    sales_rows = identify_section(income_rows, ["direct income", "direct incomes", "income account"], ["sales", "revenue"])
    sales_totals = sum_section_values(sales_rows, period_list)

    # 2. Cost of Sales
    cos_rows = identify_section(expense_rows, ["cost of goods sold", "direct expense", "direct expenses"], ["cost of sales", "cost of goods sold"])
    cos_totals = sum_section_values(cos_rows, period_list)

    # 3. Operating Expenses (All expenses except COS, Interest, Tax)
    # We'll filter them by exclusion or explicit type
    interest_tax_types = ["interest expense", "tax"]
    interest_tax_names = ["interest", "tax", "income tax"]
    op_ex_rows = [r for r in expense_rows if (r.get("account_type") or "").lower().strip() not in (interest_tax_types + ["cost of goods sold", "direct expense", "direct expenses"])
                  and not any(x in (r.get("account_name") or "").lower() for x in interest_tax_names)
                  and r not in cos_rows]
    op_ex_totals = sum_section_values(op_ex_rows, period_list)

    # 4. Other Income
    other_income_rows = identify_section(income_rows, ["indirect income", "indirect incomes"], ["other income"])
    other_income_totals = sum_section_values(other_income_rows, period_list)

    # 5. Interest & Tax
    interest_rows = identify_section(expense_rows, ["interest expense"], ["interest"])
    tax_rows = identify_section(expense_rows, ["tax"], ["tax", "income tax"])
    interest_totals = sum_section_values(interest_rows, period_list)
    tax_totals = sum_section_values(tax_rows, period_list)

    # Calculations
    gross_profit_totals = subtract_section_values(sales_totals, cos_totals, period_list)
    op_profit_totals = subtract_section_values(gross_profit_totals, op_ex_totals, period_list)
    ebt_totals = add_section_values(op_profit_totals, other_income_totals, period_list)
    ebt_totals = subtract_section_values(ebt_totals, interest_totals, period_list)
    net_profit_totals = subtract_section_values(ebt_totals, tax_totals, period_list)

    # Building Data Rows for Print Format
    # Headers
    sections.append(make_subtotal_row(_("Sales Revenue"), sales_totals, currency, period_list))
    sections.extend(copy_rows(cos_rows, compare_map))
    sections.append(make_subtotal_row(_("Less: Cost of Sales"), cos_totals, currency, period_list))
    sections.append(make_subtotal_row(_("Gross Profit"), gross_profit_totals, currency, period_list))
    sections.append({})

    sections.append(make_section_header(_("Operating Expenses"), currency, period_list))
    sections.extend(copy_rows(op_ex_rows, compare_map))
    sections.append(make_subtotal_row(_("Total Operating Expenses"), op_ex_totals, currency, period_list))
    sections.append({})

    sections.append(make_subtotal_row(_("Operating Profit"), op_profit_totals, currency, period_list))
    sections.append({})

    if other_income_rows:
        sections.extend(copy_rows(other_income_rows, compare_map))
    if interest_rows:
        sections.extend(copy_rows(interest_rows, compare_map))

    sections.append({})
    sections.append(make_subtotal_row(_("Net Profit Before Tax"), ebt_totals, currency, period_list))
    
    if tax_rows:
        sections.extend(copy_rows(tax_rows, compare_map))
    
    sections.append({})
    sections.append(make_subtotal_row(_("Net Profit After Tax"), net_profit_totals, currency, period_list))

    return sections


def sum_section_values(rows, period_list):
    totals = {str(period.key): 0.0 for period in period_list}
    totals["total"] = 0.0
    if not rows:
        return totals

    # Avoid double counting by only summing leaf nodes relative to this list
    parents_in_list = set(r.get("account") for r in rows if r.get("is_group") or r.get("account") in set(x.get("parent_account") for x in rows if x.get("parent_account")))
    
    for row in rows:
        # Skip system-generated summary rows (Total XXX) to avoid contamination
        if str(row.get("account_name")).startswith("'"):
            continue
            
        # If this row is a parent, skip it to avoid double counting its children
        if row.get("account") in parents_in_list:
            continue

        for period in period_list:
            key = period.key
            # Try both the original key and string version (e.g. 2026 vs "2026")
            val = flt(row.get(key, row.get(str(key), 0.0)))
            totals[str(key)] += val
        totals["total"] += flt(row.get("total", 0.0))
    return totals


def add_section_values(first, second, period_list):
    totals = {}
    for period in period_list:
        key = str(period.key)
        totals[key] = flt(first.get(key, 0.0)) + flt(second.get(key, 0.0))
    totals["total"] = flt(first.get("total", 0.0)) + flt(second.get("total", 0.0))
    return totals


def subtract_section_values(first, second, period_list):
    totals = {}
    for period in period_list:
        key = str(period.key)
        totals[key] = flt(first.get(key, 0.0)) - flt(second.get(key, 0.0))
    totals["total"] = flt(first.get("total", 0.0)) - flt(second.get("total", 0.0))
    return totals


def make_total_row(label, period_values, currency, period_list, compare_amount=0.0):
    row = make_section_header(label, currency, period_list)
    row.warn_if_negative = True
    for period in period_list:
        key = str(period.key)
        row[key] = flt(period_values.get(key, 0.0), 3)
    row.total = get_total_from_period_values(period_values, period_list)
    row.comparison_total = flt(compare_amount, 3)
    return row


def get_total_from_period_values(period_values, period_list):
    if not period_list:
        return flt(period_values.get("total", 0.0), 3)

    period_total = sum(flt(period_values.get(str(period.key), 0.0)) for period in period_list)
    source_total = flt(period_values.get("total", 0.0))
    if source_total == 0 and period_total != 0:
        return flt(period_total, 3)

    return flt(source_total, 3)


def make_subtotal_row(label, period_values, currency, period_list, compare_amount=0.0):
    row = make_total_row(label, period_values, currency, period_list, compare_amount)
    row.account_name = label
    row.section_name = label
    return row


def copy_rows(rows, compare_map, skip_root=False):
    copied = []
    for row in rows:
        if skip_root and cint(row.get("indent")) == 0 and cint(row.get("is_group")):
            continue

        copied_row = frappe._dict(row)
        copied_row.account = row.get("account")
        copied_row.parent_account = row.get("parent_account")
        copied_row.indent = row.get("indent", 0)
        copied_row.currency = row.get("currency")
        if compare_map is not None:
            copied_row.comparison_total = compare_map.get(row.get("account"), 0.0)
        copied.append(copied_row)
    return copied


def make_section_header(label, currency, period_list):
    return frappe._dict(
        {
            "account": "",
            "parent_account": "",
            "account_name": label,
            "section_name": label,
            "indent": 0,
            "is_group": 1,
            "currency": currency,
            "year_start_date": period_list[0]["year_start_date"].strftime("%Y-%m-%d"),
            "year_end_date": period_list[-1]["year_end_date"].strftime("%Y-%m-%d"),
            "total": 0.0,
            "comparison_total": 0.0,
        }
    )


def get_comparison_map(filters, period_list):
    if filters.comparison_period == "Previous Year":
        months = 12
    else:
        months = (getdate(period_list[-1].to_date).year - getdate(period_list[0].from_date).year) * 12 + (
            getdate(period_list[-1].to_date).month - getdate(period_list[0].from_date).month
        ) + 1

    compare_start_date = add_months(getdate(period_list[0].from_date), -months)
    compare_end_date = add_days(add_months(compare_start_date, months), -1)

    compare_filters = frappe._dict(filters)
    compare_filters.filter_based_on = "Date Range"
    compare_filters.period_start_date = compare_start_date
    compare_filters.period_end_date = compare_end_date
    compare_filters.from_fiscal_year = None
    compare_filters.to_fiscal_year = None

    compare_period_list = get_period_list(
        None,
        None,
        compare_start_date,
        compare_end_date,
        "Date Range",
        filters.periodicity,
        company=filters.company,
        ignore_fiscal_year=True,
    )

    compare_income = get_data(
        filters.company,
        "Income",
        "Credit",
        compare_period_list,
        filters=compare_filters,
        accumulated_values=filters.accumulated_values,
        ignore_closing_entries=True,
    ) or []
    compare_expense = get_data(
        filters.company,
        "Expense",
        "Debit",
        compare_period_list,
        filters=compare_filters,
        accumulated_values=filters.accumulated_values,
        ignore_closing_entries=True,
    ) or []

    compare_map = {r.get("account"): flt(r.get("total", 0.0), 3) for r in compare_income + compare_expense if r.get("account")}

    income_total = sum(
        r.get("total", 0.0)
        for r in compare_income
        if r.get("account_type") in ("Income Account", "Direct Income", "")
    )
    other_income_total = sum(r.get("total", 0.0) for r in compare_income if r.get("account_type") == "Indirect Income")
    cost_of_sales_total = sum(r.get("total", 0.0) for r in compare_expense if r.get("account_type") in ("Cost of Goods Sold", "Direct Expense"))
    expense_total = sum(
        r.get("total", 0.0)
        for r in compare_expense
        if r.get("account_type") not in ("Cost of Goods Sold", "Direct Expense", "Tax")
    )
    tax_total = sum(r.get("total", 0.0) for r in compare_expense if r.get("account_type") == "Tax")
    gross_profit = income_total - cost_of_sales_total
    operating_profit = gross_profit - expense_total
    net_before_tax = operating_profit + other_income_total
    net_after_tax = net_before_tax - tax_total

    return (
        "Previous Period" if filters.comparison_period == "Previous Period" else "Previous Year",
        compare_map,
        {
            "income": income_total,
            "other_income": other_income_total,
            "cost_of_sales": cost_of_sales_total,
            "expenses": expense_total,
            "tax": tax_total,
            "gross_profit": gross_profit,
            "operating_profit": operating_profit,
            "net_before_tax": net_before_tax,
            "net_after_tax": net_after_tax,
        },
    )


def build_report_summary(data, currency, compare_label=None):
    if not data:
        return []

    last_row = data[-1]
    net_after_tax = last_row.get("total", 0.0)
    summary = [
        {"label": _("Net Profit After Tax"), "value": net_after_tax, "datatype": "Currency", "currency": currency},
    ]
    if compare_label:
        summary.append(
            {"label": _(compare_label), "value": last_row.get("comparison_total", 0.0), "datatype": "Currency", "currency": currency}
        )
    return summary
