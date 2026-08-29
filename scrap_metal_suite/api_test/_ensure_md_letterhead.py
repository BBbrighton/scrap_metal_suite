"""Create the MD Letter Head if missing, so Desk's print view offers it.

The truck terminal does NOT need this record — it sends `brand=MD` directly.
This exists purely so a Desk user can pick MD from the Letter Head dropdown.
Re-runnable; never edits an existing record.
"""

import frappe

NAME = "MD"
CONTENT = (
    '<div style="text-align: left;">'
    '<div style="font-size:13pt;font-weight:bold;">MD Recycle Group</div>'
    '<div style="font-size:11pt;font-weight:bold;">บริษัท เอ็มดี รีไซเคิล กรุ๊ป จำกัด</div>'
    "</div>"
)


def run():
    if frappe.db.exists("Letter Head", NAME):
        print(f"  = exists   Letter Head {NAME}")
        return {"created": False}

    doc = frappe.get_doc({
        "doctype": "Letter Head",
        "letter_head_name": NAME,
        "content": CONTENT,
        "source": "HTML",
        "is_default": 0,
        "disabled": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  + created  Letter Head {NAME}")
    return {"created": True}
