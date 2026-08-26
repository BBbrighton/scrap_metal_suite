import frappe


def run():
    # Property setters that may override the doctype options.
    ps = frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": "Scrap Weight Container",
            "field_name": "naming_series",
        },
        fields=["name", "property", "value"],
    )
    print("Property Setters on naming_series:")
    for p in ps:
        print(f"  - {p}")

    # Custom Field on this doctype targeting naming_series? (rare)
    cf = frappe.get_all(
        "Custom Field",
        filters={"dt": "Scrap Weight Container", "fieldname": "naming_series"},
        fields=["name", "options"],
    )
    print(f"\nCustom Field overrides: {cf}")

    # Read the actual DocField row for naming_series.
    df_row = frappe.db.sql(
        """SELECT name, options, modified FROM `tabDocField`
           WHERE parent='Scrap Weight Container' AND fieldname='naming_series'""",
        as_dict=True,
    )
    print(f"\ntabDocField row: {df_row}")
