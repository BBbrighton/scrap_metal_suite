import frappe


def run():
    pf = frappe.get_doc("Print Format", "ใบคิวสองภาษา")
    print(f"name={pf.name}")
    print(f"doc_type={pf.doc_type}")
    print(f"standard={pf.standard}")
    print(f"print_format_type={pf.print_format_type}")
    html = pf.html or ""
    print(f"html length: {len(html)}")
    if html:
        # Show line 478 ± a few.
        lines = html.split("\n")
        print(f"  total lines: {len(lines)}")
        start = max(0, 478 - 30)
        end = min(len(lines), 478 + 5)
        print(f"\n--- lines {start+1}..{end} ---")
        for i in range(start, end):
            marker = ">>> " if (i + 1) == 478 else "    "
            print(f"{marker}{i+1:4d}  {lines[i]}")
