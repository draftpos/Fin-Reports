// Copyright (c) 2026, Fin Reports
// License: MIT

frappe.query_reports["Custom Profit n Loss"] = $.extend({}, erpnext.financial_statements, {
	formatter: function (value, row, column, data, default_formatter, filter) {
		const isCurrencyField = column.fieldtype === "Currency";
		const isAmountColumn = column.fieldname !== "account" && isCurrencyField;

		if (isAmountColumn && typeof value === "number") {
			if (value < 0) {
				value = `(${Math.abs(value).toLocaleString(undefined, {maximumFractionDigits: 2, minimumFractionDigits: 2})})`;
			} else {
				value = value.toLocaleString(undefined, {maximumFractionDigits: 2, minimumFractionDigits: 2});
			}
		}

		if (data && column.fieldname == this.name_field) {
			value = data.section_name || data.account_name || value;

			if (!data.account && !data.accounts) {
				column.link_onclick = null;
			} else {
				column.link_onclick =
					"erpnext.financial_statements.open_general_ledger(" + JSON.stringify(data) + ")";
			}
			column.is_tree = true;
		}

		value = default_formatter(value, row, column, data);

		if (data && !data.parent_account) {
			value = $(`<span>${value}</span>`);
			value.css("font-weight", "bold");
			if (data.section_name) {
				value.css({"font-size": "1rem", color: "#2c3e50"});
			}
			if (data.warn_if_negative && data[column.fieldname] < 0) {
				value.addClass("text-danger");
			}
			value = value.wrap("<p></p>").parent().html();
		}

		if (isAmountColumn && data && data[column.fieldname] < 0) {
			value = $('<span>' + value + '</span>').addClass('text-danger').wrap('<p></p>').parent().html();
		}

		return value;
	},

	onload: function (report) {
		erpnext.financial_statements.onload(report);
	},
});

function get_filters() {
	let filters = [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{
			fieldname: "filter_based_on",
			label: __("Filter Based On"),
			fieldtype: "Select",
			options: ["Fiscal Year", "Date Range"],
			default: ["Fiscal Year"],
			reqd: 1,
			on_change: function () {
				let filter_based_on = frappe.query_report.get_filter_value("filter_based_on");
				frappe.query_report.toggle_filter_display("from_fiscal_year", filter_based_on === "Date Range");
				frappe.query_report.toggle_filter_display("to_fiscal_year", filter_based_on === "Date Range");
				frappe.query_report.toggle_filter_display("period_start_date", filter_based_on === "Fiscal Year");
				frappe.query_report.toggle_filter_display("period_end_date", filter_based_on === "Fiscal Year");
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "period_start_date",
			label: __("Start Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.filter_based_on == 'Date Range'",
			mandatory_depends_on: "eval:doc.filter_based_on == 'Date Range'",
		},
		{
			fieldname: "period_end_date",
			label: __("End Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.filter_based_on == 'Date Range'",
			mandatory_depends_on: "eval:doc.filter_based_on == 'Date Range'",
		},
		{
			fieldname: "from_fiscal_year",
			label: __("Start Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			reqd: 1,
			depends_on: "eval:doc.filter_based_on == 'Fiscal Year'",
		},
		{
			fieldname: "to_fiscal_year",
			label: __("End Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			reqd: 1,
			depends_on: "eval:doc.filter_based_on == 'Fiscal Year'",
		},
		{
			fieldname: "periodicity",
			label: __("Periodicity"),
			fieldtype: "Select",
			options: [
				{ value: "Monthly", label: __("Monthly") },
				{ value: "Quarterly", label: __("Quarterly") },
				{ value: "Yearly", label: __("Yearly") },
			],
			default: "Yearly",
			reqd: 1,
		},
		{
			fieldname: "comparison_period",
			label: __("Compare With"),
			fieldtype: "Select",
			options: ["None", "Previous Period", "Previous Year"],
			default: "None",
		},
		{
			fieldname: "presentation_currency",
			label: __("Currency"),
			fieldtype: "Select",
			options: erpnext.get_presentation_currency_list(),
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "MultiSelectList",
			options: "Cost Center",
			get_data: function (txt) {
				return frappe.db.get_link_options("Cost Center", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "MultiSelectList",
			options: "Project",
			get_data: function (txt) {
				return frappe.db.get_link_options("Project", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "accumulated_values",
			label: __("Accumulated Values"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_default_book_entries",
			label: __("Include Default FB Entries"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_zero_values",
			label: __("Show zero values"),
			fieldtype: "Check",
		},
	];

	let fiscal_year = erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), false, true);
	if (fiscal_year) {
		let fy = erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), false, false);
		filters.filter((x) => ["from_fiscal_year", "to_fiscal_year"].includes(x.fieldname)).forEach((x) => {
			x.default = fy;
		});
	}

	return filters;
}

frappe.query_reports["Custom Profit n Loss"].filters = get_filters();
erpnext.utils.add_dimensions("Custom Profit n Loss", 10);
