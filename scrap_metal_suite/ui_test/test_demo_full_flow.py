"""HEADED end-to-end DEMO — human-watchable full receiving flow.

Walks the whole chain in a visible browser, slowly, with an on-screen
narration banner at each step:

    Price Lock (desk, live)  ->  auto POS Order (shown)
      ->  Dropoff (desk, live)  ->  weigh containers (terminal, live)
      ->  finish + complete  ->  verify override
      ->  Production Sorting (desk, live)  ->  Dropoff Final (shown)

This is a DEMO, not an assertion test. It is skipped in normal runs and only
executes when SMT_DEMO=1 is set. Run it headed + slow so a human can follow:

    cd ~/frappe-bench
    SMT_DEMO=1 SMT_UI_HEADLESS=0 SMT_UI_SLOW_MO=900 SMT_UI_ADMIN_PWD="$SMT_UI_ADMIN_PWD" \
      env/bin/pytest apps/scrap_metal_suite/scrap_metal_suite/ui_test/test_demo_full_flow.py -v -s

Leaves data in the DB (no teardown) so you can inspect afterwards.
"""

import json
import os
import re

import pytest

SEED_METHOD = "scrap_metal_suite.ui_test.fixtures.seed_demo_masters"

pytestmark = pytest.mark.skipif(
    os.environ.get("SMT_DEMO", "0") != "1",
    reason="headed demo — set SMT_DEMO=1 to run",
)

# Pause lengths (ms) so a human can read the banner / see the result.
BEAT = int(os.environ.get("SMT_DEMO_BEAT", "1600"))
LONG = BEAT * 2


def _parse_seed(stdout):
    for line in stdout.splitlines():
        if line.startswith("SEED_RESULT:"):
            return json.loads(line[len("SEED_RESULT:"):])
    raise AssertionError(f"No SEED_RESULT in:\n{stdout}")


def narrate(page, step, title, detail=""):
    """Inject / update a fixed banner at the top of whatever page is loaded."""
    page.evaluate(
        """([step, title, detail]) => {
            let b = document.getElementById('smt-demo-banner');
            if (!b) {
                b = document.createElement('div');
                b.id = 'smt-demo-banner';
                b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;'
                    + 'background:linear-gradient(90deg,#0d47a1,#1976d2);color:#fff;'
                    + 'padding:12px 20px;font:600 17px/1.35 system-ui,Segoe UI,sans-serif;'
                    + 'box-shadow:0 2px 10px rgba(0,0,0,.35);letter-spacing:.2px';
                document.body.appendChild(b);
            }
            b.innerHTML =
                '<span style="opacity:.65">SMT E2E DEMO · </span>'
                + '<span style="opacity:.85">Step ' + step + '</span> &nbsp;'
                + title
                + (detail ? ' <span style="font-weight:400;opacity:.9">— ' + detail + '</span>' : '');
        }""",
        [step, title, detail],
    )


def _wait_frm(page, doctype, timeout=20000):
    page.wait_for_function(
        "(dt) => window.cur_frm && cur_frm.doc && cur_frm.doctype === dt && !cur_frm.is_dirty_loading",
        arg=doctype,
        timeout=timeout,
    )


def _click_confirm_yes(page):
    """Click the primary button of a Frappe confirm/submit dialog, if present."""
    try:
        page.locator(".modal.show .btn-primary, .modal.in .btn-primary").last.click(timeout=6000)
    except Exception:
        pass


def test_full_receiving_demo(authed_page, seeder, base_url):
    page = authed_page
    ctx = _parse_seed(seeder(SEED_METHOD))
    supplier, item_a, item_b = ctx["supplier"], ctx["item_a"], ctx["item_b"]
    session = ctx["session"]
    plate = "_TEST_UI_DEMO-99"

    # ================================================================
    # STEP 1 — Price Lock (create live in the desk form)
    # ================================================================
    page.goto(f"{base_url}/app/smt-price-lock/new", wait_until="networkidle")
    _wait_frm(page, "SMT Price Lock")
    narrate(page, 1, "Booking the price", "creating an SMT Price Lock")
    page.wait_for_timeout(BEAT)

    page.evaluate(
        """async ({supplier, items}) => {
            await cur_frm.set_value('supplier', supplier);
            cur_frm.clear_table('items');   // drop the auto-created blank row
            for (const it of items) {
                const row = cur_frm.add_child('items');
                row.item_code = it.code; row.po_qty = it.qty; row.po_rate = it.rate;
            }
            cur_frm.refresh_field('items');
        }""",
        {"supplier": supplier, "items": [
            {"code": item_a, "qty": 500, "rate": 250},
            {"code": item_b, "qty": 300, "rate": 180},
        ]},
    )
    narrate(page, 1, "Booking the price", "2 grades, qty + rate filled — saving")
    page.wait_for_timeout(LONG)

    # Fire-and-forget: saving a NEW doc navigates the URL (→ saved doc), which
    # destroys the evaluate context. Don't await the promise; poll for the result.
    page.evaluate("() => { cur_frm.save(); }")
    page.wait_for_function(
        "() => window.cur_frm && cur_frm.doc && cur_frm.doc.name && !cur_frm.doc.__islocal",
        timeout=20000)
    pl_name = page.evaluate("() => cur_frm.doc.name")

    narrate(page, 1, "Submitting Price Lock", "this auto-creates the POS Order")
    page.wait_for_timeout(BEAT)
    page.evaluate("() => { cur_frm.savesubmit(); }")
    _click_confirm_yes(page)
    page.wait_for_function(
        "() => window.cur_frm && cur_frm.doc && cur_frm.doc.docstatus === 1", timeout=20000)
    page.wait_for_timeout(BEAT)

    po_name = page.evaluate(
        """async (pl) => {
            const r = await frappe.db.get_list('POS Order',
                {filters: {smt_price_lock: pl}, fields: ['name'], limit: 1});
            return r && r[0] && r[0].name;
        }""",
        pl_name,
    )
    print(f"[demo] Price Lock {pl_name} -> POS Order {po_name}")

    # ================================================================
    # STEP 2 — show the auto-created POS Order
    # ================================================================
    page.goto(f"{base_url}/app/pos-order/{po_name}", wait_until="networkidle")
    _wait_frm(page, "POS Order")
    narrate(page, 2, "POS Order auto-created", f"{po_name} — linked back to the Price Lock")
    page.wait_for_timeout(LONG)

    # ================================================================
    # STEP 3 — Dropoff (create live, link the POS Order)
    # ================================================================
    page.goto(f"{base_url}/app/dropoff/new", wait_until="networkidle")
    _wait_frm(page, "Dropoff")
    narrate(page, 3, "Scheduling the Drop-off", "truck arrives — linking the POS Order")
    page.wait_for_timeout(BEAT)

    page.evaluate(
        """async ({supplier, plate, po, items}) => {
            await cur_frm.set_value('supplier', supplier);      // read-only; set programmatically
            await cur_frm.set_value('license_plate', plate);
            cur_frm.clear_table('orders');
            const o = cur_frm.add_child('orders'); o.pos_order = po;
            cur_frm.refresh_field('orders');
            cur_frm.clear_table('expected_items');
            for (const it of items) {
                const r = cur_frm.add_child('expected_items');
                r.item = it.code; r.indicated_weight = it.kg;
            }
            cur_frm.refresh_field('expected_items');
        }""",
        {"supplier": supplier, "plate": plate, "po": po_name,
         "items": [{"code": item_a, "kg": 500}, {"code": item_b, "kg": 300}]},
    )
    narrate(page, 3, "Drop-off details", "license plate + expected items — saving")
    page.wait_for_timeout(LONG)

    page.evaluate("() => { cur_frm.save(); }")
    page.wait_for_function(
        "() => window.cur_frm && cur_frm.doc && cur_frm.doc.name && !cur_frm.doc.__islocal",
        timeout=20000)
    do_name = page.evaluate("() => cur_frm.doc.name")
    do_status = page.evaluate("() => cur_frm.doc.status")
    narrate(page, 3, "Drop-off scheduled", f"{do_name} — status {do_status}")
    print(f"[demo] Dropoff {do_name} ({do_status})")
    page.wait_for_timeout(LONG)

    # ================================================================
    # STEP 4 — weigh containers on the three-pane terminal (LIVE)
    # ================================================================
    page.goto(f"{base_url}/pos/terminal?session={session}", wait_until="networkidle")
    page.wait_for_function("typeof window.CONTAINER_UI !== 'undefined'", timeout=15000)
    page.wait_for_selector("#containerWeighCard", state="attached", timeout=5000)
    narrate(page, 4, "At the scrap scale", "operator opens the Drop-off on the terminal")
    page.wait_for_timeout(BEAT)

    page.evaluate(
        """({name, plate, supplier}) => window.selectDropoff(name, '', plate, supplier, 'Scheduled')""",
        {"name": do_name, "plate": plate, "supplier": supplier},
    )
    page.wait_for_selector("#containerPanel", state="visible", timeout=5000)
    page.wait_for_selector("#containerWeighCard", state="visible", timeout=5000)
    page.wait_for_timeout(BEAT)

    # Weigh three bags across the two grades — watch rows appear in the journal.
    bags = [(item_a, "250.0"), (item_a, "230.5"), (item_b, "180.0")]
    for idx, (code, wt) in enumerate(bags, start=1):
        narrate(page, 4, f"Weighing bag {idx}/{len(bags)}", f"{code} — {wt} kg")
        page.evaluate("([c, n]) => window.CONTAINER_UI.setActiveGrade(c, n)", [code, code])
        page.wait_for_selector("#activeGradePill", state="visible", timeout=3000)
        page.fill("#containerNetWeight", wt)
        page.evaluate("() => window.CONTAINER_UI.onWeightInput()")
        page.wait_for_timeout(BEAT)
        page.evaluate("() => window.CONTAINER_UI.saveActiveContainer()")
        page.wait_for_function(
            "(n) => document.getElementById('containerCountBadge').textContent === String(n)",
            arg=idx, timeout=15000,
        )
        page.wait_for_timeout(BEAT)

    narrate(page, 4, "Three bags weighed", "journal shows each container + running total")
    page.wait_for_timeout(LONG)

    # Finish + complete + verify run SERVER-SIDE: the custom terminal page has
    # no desk frappe.db/frappe.call client API. The human already watched the
    # bags being weighed; we now settle the paperwork via bench.
    narrate(page, 4, "Finishing session", "issuing receipt · completing · verifying")
    page.wait_for_timeout(LONG)
    seeder("scrap_metal_suite.ui_test.fixtures.demo_finish_and_complete", {"dropoff": do_name})

    # ================================================================
    # STEP 5 — show the completed + verified Drop-off
    # ================================================================
    page.goto(f"{base_url}/app/dropoff/{do_name}", wait_until="networkidle")
    _wait_frm(page, "Dropoff")
    status = page.evaluate("() => cur_frm.doc.status")
    vstatus = page.evaluate("() => cur_frm.doc.verification_status")
    narrate(page, 5, "Drop-off completed",
            f"status {status} · verification {vstatus} — ready to be graded")
    page.wait_for_timeout(LONG)

    # ================================================================
    # STEP 6 — Production Sorting (grade) live, then Dropoff Final
    # ================================================================
    page.goto(f"{base_url}/app/production-sorting/new", wait_until="networkidle")
    _wait_frm(page, "Production Sorting")
    narrate(page, 6, "Grading the material", "selecting the completed Drop-off")
    page.wait_for_timeout(BEAT)

    page.evaluate("async (d) => cur_frm.set_value('dropoff', d)", do_name)
    # source_items populate from the dropoff's item_summary via the form script.
    page.wait_for_function(
        "() => cur_frm && cur_frm.doc && (cur_frm.doc.source_items || []).length > 0",
        timeout=10000,
    )
    narrate(page, 6, "Source items loaded", "splitting into Keep & Return")
    page.wait_for_timeout(LONG)

    page.evaluate(
        """async ({item_a, item_b}) => {
            // Assign posting date/time directly (avoids set_value promise quirks).
            if (!cur_frm.doc.posting_date)
                cur_frm.doc.posting_date = frappe.datetime.get_today();
            if (!cur_frm.doc.posting_time)
                cur_frm.doc.posting_time = new Date().toTimeString().slice(0, 8);
            cur_frm.clear_table('good_items');
            const g = cur_frm.add_child('good_items');
            g.item_code = item_a; g.weight = 400;
            cur_frm.clear_table('unwanted_items');
            const u = cur_frm.add_child('unwanted_items');
            u.item_code = item_b; u.weight = 60; u.return_reason = 'Contamination';
            cur_frm.refresh_field('good_items');
            cur_frm.refresh_field('unwanted_items');
        }""",
        {"item_a": item_a, "item_b": item_b},
    )
    narrate(page, 6, "Sorted", "Keep 400 kg · Return 60 kg — submitting")
    page.wait_for_timeout(LONG)

    page.evaluate("() => { cur_frm.save(); }")
    page.wait_for_function(
        "() => window.cur_frm && cur_frm.doc && cur_frm.doc.name && !cur_frm.doc.__islocal",
        timeout=20000)
    page.evaluate("() => { cur_frm.savesubmit(); }")
    _click_confirm_yes(page)
    page.wait_for_function(
        "() => window.cur_frm && cur_frm.doc && cur_frm.doc.docstatus === 1", timeout=20000)
    sort_name = page.evaluate("() => cur_frm.doc.name")
    print(f"[demo] Production Sorting {sort_name} submitted")
    page.wait_for_timeout(BEAT)

    final = page.evaluate(
        """async (d) => {
            const r = await frappe.db.get_list('Dropoff Final',
                {filters: {dropoff: d}, fields: ['name'], limit: 1});
            return r && r[0] && r[0].name;
        }""",
        do_name,
    )
    if final:
        page.goto(f"{base_url}/app/dropoff-final/{final}", wait_until="networkidle")
        _wait_frm(page, "Dropoff Final")
        narrate(page, 6, "Dropoff Final created", f"{final} — end to end complete ✔")
        print(f"[demo] Dropoff Final {final}")
    else:
        narrate(page, 6, "Graded", "Production Sorting submitted ✔")
    page.wait_for_timeout(LONG * 2)
