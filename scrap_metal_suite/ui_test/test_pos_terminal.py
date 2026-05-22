# UI test: POS scrap terminal — Container weighing happy path.
#
# Drives the new inline Container weighing flow at /pos/terminal (the
# scrap-scale bench terminal where the Container UI now lives):
#   1. seed a Scheduled dropoff with 2 expected items + an open POS Session
#   2. login as Administrator
#   3. visit /pos/terminal, programmatically select the seeded dropoff
#      (skipping the queue UI for determinism)
#   4. set the Active Grade by clicking a left-panel item, fill the inline
#      weight + container type, and call Save & Print
#   5. assert: container row appears in the list with correct weight + grade,
#      print iframes were created with both thermal + sticker URLs
#
# The "+ Add Container" modal is gone — there is now a single inline weighing
# card on the right panel that the operator drives end-to-end. Hardware paths
# (WebSerial, QR scanner) are NOT exercised — this test takes the manual-entry
# path through the same input the inline card uses.

import json
import re

import pytest

from .conftest import KEEP_DATA


SEED_METHOD = "scrap_metal_suite.ui_test.fixtures.seed_pos_truck_scenario"


def _parse_seed(stdout):
    for line in stdout.splitlines():
        if line.startswith("SEED_RESULT:"):
            return json.loads(line[len("SEED_RESULT:"):])
    raise AssertionError(f"No SEED_RESULT in seed output:\n{stdout}")


@pytest.fixture
def seeded(seeder):
    """Seed the DB and yield the test context. Teardown cleans up unless
    SMT_UI_KEEP_DATA=1 is set (in which case the seeded data is left in the
    DB for manual inspection)."""
    payload = _parse_seed(seeder(SEED_METHOD))
    yield payload
    if not KEEP_DATA:
        seeder("scrap_metal_suite.ui_test.fixtures.cleanup_ui_test_data")


def test_add_container_happy_path(authed_page, seeded, base_url):
    page = authed_page
    ctx = seeded

    # Track print URLs hit by the auto-print iframes. Listen on `request`
    # rather than `frame` because hidden zero-size iframes don't always
    # fire framenavigated reliably.
    print_urls = []
    page.on(
        "request",
        lambda r: print_urls.append(r.url) if "printview" in (r.url or "") else None,
    )

    # Visit the scrap terminal. The route requires ?session=<name> — without
    # it, terminal.py redirects to /pos for session selection.
    page.goto(
        f"{base_url}/pos/terminal?session={ctx['session']}",
        wait_until="networkidle",
    )

    assert "/pos/terminal" in page.url, f"Expected /pos/terminal, got {page.url}"

    # Wait for the terminal scripts to finish initializing. The
    # CONTAINER_UI module is exposed on window once loaded.
    page.wait_for_function("typeof window.CONTAINER_UI !== 'undefined'",
                           timeout=15000)

    # Sanity: the inline weighing card must be present (i.e. the redesigned
    # use_container_model=true flow is live, not the legacy cart fallback).
    page.wait_for_selector("#containerWeighCard", state="attached", timeout=5000)

    # Programmatically select the seeded dropoff (skips the queue UI).
    page.evaluate(
        """({name, supplier}) => {
            window.selectDropoff(name, '', '_TEST_UI_UI-1234', supplier, 'Scheduled');
        }""",
        {"name": ctx["dropoff"], "supplier": ctx["supplier"]},
    )

    # The container panel should now be visible — and the inline card with it.
    page.wait_for_selector("#containerPanel", state="visible", timeout=5000)
    page.wait_for_selector("#containerWeighCard", state="visible", timeout=5000)

    # Wait for expected_items to populate (the deviation logic and Save button
    # both depend on it). The CONTAINER_UI fetches via get_dropoff_details.
    page.wait_for_function(
        """(itemCode) => {
            try {
                return !!(window.CONTAINER_UI
                    && document.getElementById('btnSaveActiveContainer'));
            } catch (e) { return false; }
        }""",
        arg=ctx["item_a"],
        timeout=10000,
    )

    # 1. Click a grade from the left panel — drives setActiveGrade.
    #    (Calling the method directly is equivalent to clicking the .item-btn,
    #    and avoids flakiness from category-tab visibility ordering.)
    page.evaluate(
        "([code, name]) => window.CONTAINER_UI.setActiveGrade(code, name)",
        [ctx["item_a"], ctx["item_a"]],
    )

    # The Active Grade pill should now be showing the selected grade.
    page.wait_for_selector("#activeGradePill", state="visible", timeout=3000)

    # 2. Fill the inline net-weight input (manual override path).
    page.fill("#containerNetWeight", "246.7")
    # Fire the oninput handler so the save button is enabled.
    page.evaluate("window.CONTAINER_UI.onWeightInput()")

    # 3. Pick container type (default Bag is fine, but exercise the dropdown).
    page.select_option("#containerType", value="Bag")

    # 4. Save & Print — the inline card submits + auto-prints both formats.
    page.evaluate("window.CONTAINER_UI.saveActiveContainer()")

    # The badge update is async after the API returns — give it headroom.
    page.wait_for_function(
        "document.getElementById('containerCountBadge').textContent === '1'",
        timeout=15000,
    )

    # After save the inline card resets — the active grade pill is hidden again.
    page.wait_for_selector("#activeGradeEmpty", state="visible", timeout=3000)

    # Assert the new container row shows the right item_name (canonical Thai)
    # and weight. The CONTAINER_UI renders rows into #containerList.
    list_text = page.locator("#containerList").inner_text()
    assert ctx["item_a"] in list_text, (
        f"Expected item_name {ctx['item_a']!r} in container list; got:\n{list_text}"
    )
    assert "246.7" in list_text, (
        f"Expected weight 246.7 in container list; got:\n{list_text}"
    )

    # Wave 9+: only the per-bag sticker prints on add_container. The
    # per-Dropoff thermal receipt (`ใบคิวสองภาษา`) is generated separately
    # when the operator hits Finish Container Weighing — not on every bag.
    page.wait_for_timeout(500)

    sticker = [u for u in print_urls if "Sticker" in u]
    assert sticker, f"No sticker print iframe detected. All print URLs:\n{print_urls}"

    # URL should reference the new container's name (CTN-...)
    assert re.search(r"CTN-\d{4}-\d+", sticker[0]), sticker[0]


def test_wave11_surface(authed_page, seeded, base_url):
    """Wave 11 surface check — exercises the new features without doing a
    full save+print cycle:

      1. Unified scanner detector resolves URL + bare-ID inputs to the right
         doctype.
      2. Three-pane terminal renders all three panels.
      3. Both pane resizers exist + are interactive (LEFT/MIDDLE + MIDDLE/RIGHT).
      4. Inline weighing card has the Take Photo button (Wave 11 #3) and it
         enables only after a grade is picked.
    """
    page = authed_page
    ctx = seeded

    page.goto(
        f"{base_url}/pos/terminal?session={ctx['session']}",
        wait_until="networkidle",
    )
    page.wait_for_function("typeof window.CONTAINER_UI !== 'undefined'", timeout=15000)
    # POS_SCANNER is a top-level `const` (not assigned to window) — it's
    # accessible by bare name from `evaluate` callbacks but `window.POS_SCANNER`
    # is undefined. Wait by bare-name lookup via the script-scope binding.
    page.wait_for_function("typeof POS_SCANNER !== 'undefined'", timeout=5000)

    # 1. Unified scanner detector — verify each input shape lands the right route.
    cases = [
        ("https://demo.example.com/app/dropoff/DO-2026-001", "Dropoff", "DO-2026-001"),
        ("/app/scrap-weight-container/CTN-2026-00007", "Scrap Weight Container", "CTN-2026-00007"),
        ("DO-TEST-260501-42", "Dropoff", "DO-TEST-260501-42"),
        ("CTN-2026-00099", "Scrap Weight Container", "CTN-2026-00099"),
        ("DROP-12345", "Dropoff", "DROP-12345"),
        ("unknown-bare-id", None, "unknown-bare-id"),
    ]
    for raw, expected_dt, expected_name in cases:
        result = page.evaluate("(raw) => POS_SCANNER.detectDoctype(raw)", raw)
        assert result.get("doctype") == expected_dt, (
            f"detectDoctype({raw!r}) doctype={result.get('doctype')!r}, "
            f"expected {expected_dt!r}"
        )
        assert result.get("name") == expected_name, (
            f"detectDoctype({raw!r}) name={result.get('name')!r}, "
            f"expected {expected_name!r}"
        )

    # 2. Three panes render.
    page.wait_for_selector("#posTerminal .panel-items", state="visible", timeout=3000)
    page.wait_for_selector("#posTerminal .panel-transaction", state="visible", timeout=3000)
    page.wait_for_selector("#posTerminal .panel-journal", state="visible", timeout=3000)

    # 3. Both resizers are present and interactive.
    for handle_id in ("panelResizer", "panelResizerJournal"):
        cursor = page.eval_on_selector(
            f"#{handle_id}",
            "el => getComputedStyle(el).cursor",
        )
        assert cursor == "col-resize", f"#{handle_id} cursor={cursor!r}, expected col-resize"

    # 4. Take Photo button — disabled until a grade is picked, enabled after.
    page.evaluate(
        """({name, supplier}) => {
            window.selectDropoff(name, '', '_TEST_UI_UI-1234', supplier, 'Scheduled');
        }""",
        {"name": ctx["dropoff"], "supplier": ctx["supplier"]},
    )
    page.wait_for_selector("#containerWeighCard", state="visible", timeout=5000)

    photo_btn = page.locator("#btnContainerTakePhoto")
    assert photo_btn.count() == 1, "Take Photo button not in DOM"
    assert photo_btn.is_disabled(), "Take Photo button should be disabled before grade pick"

    page.evaluate(
        "([code, name]) => window.CONTAINER_UI.setActiveGrade(code, name)",
        [ctx["item_a"], ctx["item_a"]],
    )
    page.wait_for_function(
        "() => !document.getElementById('btnContainerTakePhoto').disabled",
        timeout=3000,
    )
    assert not photo_btn.is_disabled(), "Take Photo button should enable after grade pick"

    # Pill starts hidden (no buffered photos).
    pill = page.locator("#containerPhotoCountPill")
    assert pill.is_hidden(), "Photo count pill should be hidden when buffer is empty"
