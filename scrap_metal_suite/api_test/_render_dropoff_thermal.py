"""Render the bilingual queue print format for DO-TEST3-260501-1 to surface
the print error the user reported."""

import frappe
import traceback
from frappe.www.printview import get_html_and_style


def run(name="DO-TEST3-260501-1"):
    print(f"Rendering print format ใบคิวสองภาษา for {name} …\n")
    try:
        out = get_html_and_style(
            doc="Dropoff",
            name=name,
            print_format="ใบคิวสองภาษา",
        )
        html = out.get("html", "") if isinstance(out, dict) else str(out)
        print(f"OK — HTML length {len(html)}")
        # Surface first 500 chars for sanity.
        print("\n--- preview ---")
        print(html[:600])
    except Exception:
        print("RENDER FAILED:")
        print(traceback.format_exc())
