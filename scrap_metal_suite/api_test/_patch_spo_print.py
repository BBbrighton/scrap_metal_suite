"""Patch ใบสั่งซื้อ so the Dropoff Finals table prints what THIS document
settles, not the delivery's entire good weight.

Under partial settlement `total_weight` (fetched from Dropoff Final) is no
longer what the supplier is being paid for — a 300 kg payment against a 1000 kg
delivery printed "1000 kg". Adds a "Settled Here" column driven by the new
computed `drawn_weight`, and relabels the old column as the delivery total.
"""

import json

PATH = "scrap_metal_suite/fixtures/print_format.json"

OLD_HEAD = """                    <th style="width:5%">#</th>
                    <th style="width:40%">เลขที่ / Dropoff Final</th>
                    <th style="width:25%">วันที่ / Date</th>
                    <th style="width:30%" class="text-right">น้ำหนัก / Weight (kg)</th>"""

NEW_HEAD = """                    <th style="width:5%">#</th>
                    <th style="width:33%">เลขที่ / Dropoff Final</th>
                    <th style="width:20%">วันที่ / Date</th>
                    <th style="width:21%" class="text-right">น้ำหนักรวม / Total (kg)</th>
                    <th style="width:21%" class="text-right">ชำระในใบนี้ / Settled Here (kg)</th>"""

OLD_CELL = """                    <td class="text-right">{{ "{:,.3f}".format(dof.total_weight or 0) }}</td>"""

NEW_CELL = """                    <td class="text-right">{{ "{:,.3f}".format(dof.total_weight or 0) }}</td>
                    <td class="text-right"><strong>{{ "{:,.3f}".format(dof.drawn_weight or 0) }}</strong></td>"""

data = json.load(open(PATH, encoding="utf-8"))

patched = False
for pf in data:
    if pf.get("doc_type") != "SMT Purchase Order":
        continue
    html = pf["html"]
    if NEW_CELL in html:
        print("already patched:", pf["name"])
        break
    assert OLD_HEAD in html, "header row not found - print format changed?"
    assert OLD_CELL in html, "weight cell not found - print format changed?"
    html = html.replace(OLD_HEAD, NEW_HEAD).replace(OLD_CELL, NEW_CELL)
    pf["html"] = html
    patched = True
    print("patched:", pf["name"])

if patched:
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, indent=1, ensure_ascii=False)
        f.write("\n")
    print("fixture written")
