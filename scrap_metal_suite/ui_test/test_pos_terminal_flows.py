"""POS terminal flow tests — Pause/Resume and Reweigh cycles.

Companion to test_pos_terminal.py, which covers the add-container happy path
and the Wave 11 surface. These cover the two lifecycle flows that had no UI
coverage.

Assertions read the DOM and the public API rather than terminal internals:
`containerState` lives inside the CONTAINER_UI IIFE and is not reachable from
`page.evaluate` (same shape as the POS_SCANNER gotcha). Driving off the action
bar is also the better test — it checks what the operator actually sees.

Not covered here, deliberately: the legacy cart fallback. terminal.py reads
`getattr(profile, "use_container_model", True)` and POS Profile Scrap has no
such field, so the flag is always True and the legacy path is unreachable.
Testing it needs the real field first (Phase 11 follow-up in
DROPOFF_CONTAINER_REDESIGN.md §14 — "Real use_container_model field").

Run:
    cd ~/frappe-bench && SMT_UI_HEADLESS=1 SMT_UI_ADMIN_PWD='...' \
        env/bin/pytest apps/scrap_metal_suite/scrap_metal_suite/ui_test/ -v
"""

import json

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
    payload = _parse_seed(seeder(SEED_METHOD))
    yield payload
    if not KEEP_DATA:
        seeder("scrap_metal_suite.ui_test.fixtures.cleanup_ui_test_data")


def _open_terminal(page, ctx, base_url):
    """Load the terminal, select the seeded dropoff, wait until interactive."""
    page.goto(
        f"{base_url}/pos/terminal?session={ctx['session']}",
        wait_until="networkidle",
    )
    assert "/pos/terminal" in page.url, f"Expected /pos/terminal, got {page.url}"
    page.wait_for_function("typeof window.CONTAINER_UI !== 'undefined'", timeout=15000)
    page.wait_for_selector("#containerWeighCard", state="attached", timeout=5000)

    page.evaluate(
        """({name, supplier}) => {
            window.selectDropoff(name, '', '_TEST_UI_UI-1234', supplier, 'Scheduled');
        }""",
        {"name": ctx["dropoff"], "supplier": ctx["supplier"]},
    )
    page.wait_for_selector("#containerPanel", state="visible", timeout=5000)
    page.wait_for_selector("#containerWeighCard", state="visible", timeout=5000)


def _add_container(page, item_code, weight):
    """Drive the inline weighing card to save one bag; returns the new count."""
    before = page.evaluate(
        "() => document.getElementById('containerCountBadge').textContent || '0'"
    )
    page.evaluate(
        "([code, name]) => window.CONTAINER_UI.setActiveGrade(code, name)",
        [item_code, item_code],
    )
    page.wait_for_selector("#activeGradePill", state="visible", timeout=3000)
    page.fill("#containerNetWeight", str(weight))
    page.evaluate("window.CONTAINER_UI.onWeightInput()")
    page.evaluate("window.CONTAINER_UI.saveActiveContainer()")

    expected = str(int(before or 0) + 1)
    page.wait_for_function(
        "(want) => document.getElementById('containerCountBadge').textContent === want",
        arg=expected,
        timeout=15000,
    )
    return expected


def _action_bar(page):
    """Which lifecycle buttons the operator can see — our proxy for status."""
    return page.evaluate(
        """() => {
            const vis = (id) => {
                const el = document.getElementById(id);
                return !!el && el.offsetParent !== null;
            };
            return {
                pause: vis('btnPauseDropoff'),
                resume: vis('btnResumeDropoff'),
                complete: vis('btnCompleteContainerDropoff'),
                reopen: vis('btnReopenDropoff'),
            };
        }"""
    )


def _containers(page, dropoff, include_voided=False):
    """Server-side truth for this dropoff's bags."""
    return page.evaluate(
        """async ({d, v}) => {
            const r = await frappe.call({
                method: 'scrap_metal_suite.api.v1.dropoff.list_containers',
                args: { dropoff: d, include_voided: v ? 1 : 0 },
            });
            return (r && r.message) || [];
        }""",
        {"d": dropoff, "v": include_voided},
    )


def _field(page, doctype, name, fieldname):
    return page.evaluate(
        """async ({dt, n, f}) => {
            const r = await frappe.call({
                method: 'frappe.client.get_value',
                args: { doctype: dt, filters: { name: n }, fieldname: f },
            });
            return (r && r.message && r.message[f]) || null;
        }""",
        {"dt": doctype, "n": name, "f": fieldname},
    )


def test_pause_resume_cycle(authed_page, seeded, base_url):
    """Pause parks a dropoff so another operator can take the scale; Resume
    re-binds it to the current session. Regression guard for the Wave 11
    session-lock bug, where pause left `weighing_session` pointing at the old
    session and resume then failed with "locked to session X"."""
    page = authed_page
    ctx = seeded

    _open_terminal(page, ctx, base_url)

    # A bag must exist first — Pause only appears once weighing has started.
    _add_container(page, ctx["item_a"], 120.5)
    bar = _action_bar(page)
    assert bar["pause"] and not bar["resume"], f"Expected Pause offered, got {bar}"

    # --- Pause ---
    page.evaluate("window.CONTAINER_UI.openPause()")
    page.wait_for_selector("#pauseDropoffModal", state="visible", timeout=3000)
    page.fill("#pauseReason", "_TEST_UI_ pause - operator break")
    page.evaluate("window.CONTAINER_UI.confirmPause()")

    page.wait_for_selector("#pauseDropoffModal", state="hidden", timeout=10000)
    page.wait_for_function(
        """() => {
            const r = document.getElementById('btnResumeDropoff');
            return !!r && r.offsetParent !== null;
        }""",
        timeout=10000,
    )
    bar = _action_bar(page)
    assert bar["resume"] and not bar["pause"], f"Expected Resume offered, got {bar}"

    status = _field(page, "Dropoff", ctx["dropoff"], "status")
    assert status == "Paused", f"Dropoff status={status!r}, expected Paused"

    # --- Resume ---
    page.evaluate("window.CONTAINER_UI.resumeDropoff()")
    page.wait_for_function(
        """() => {
            const p = document.getElementById('btnPauseDropoff');
            return !!p && p.offsetParent !== null;
        }""",
        timeout=10000,
    )
    status = _field(page, "Dropoff", ctx["dropoff"], "status")
    assert status == "In Progress", f"Dropoff status={status!r}, expected In Progress"

    # The bag weighed before the pause survives — resume calls loadContainers(),
    # so this also proves the reload path.
    page.wait_for_function(
        "() => document.getElementById('containerCountBadge').textContent === '1'",
        timeout=10000,
    )
    assert "120.5" in page.locator("#containerList").inner_text()

    # Weighing is usable again afterwards.
    _add_container(page, ctx["item_a"], 80.25)
    assert "80.25" in page.locator("#containerList").inner_text()


def test_reweigh_flow(authed_page, seeded, base_url):
    """Reweighing supersedes a bag rather than editing it.

    Containers are immutable (Wave 10), so `reweigh_container` is structurally
    void-of-old + insert-of-new: the original is **Voided** — not marked
    `Reweighed`, despite that status existing on the doctype — and the
    replacement back-links via `reweighed_from`. Voided rows are hidden from
    `list_containers` unless `include_voided` is set, which is why the journal
    still shows exactly one bag afterwards.
    """
    page = authed_page
    ctx = seeded

    _open_terminal(page, ctx, base_url)
    _add_container(page, ctx["item_a"], 100.0)

    rows = _containers(page, ctx["dropoff"])
    assert len(rows) == 1, rows
    original = rows[0]["name"]

    # --- Reweigh ---
    page.evaluate("(n) => window.CONTAINER_UI.openReweigh(n)", original)
    page.wait_for_selector("#reweighContainerModal", state="visible", timeout=3000)

    assert original in page.locator("#reweighContainerLabel").inner_text()
    assert "100.00" in page.locator("#reweighCurrentWeight").inner_text()

    page.fill("#reweighNewWeight", "155.75")
    page.fill("#reweighReason", "_TEST_UI_ scale drift recheck")
    page.evaluate("window.CONTAINER_UI.confirmReweigh()")
    page.wait_for_selector("#reweighContainerModal", state="hidden", timeout=10000)

    page.wait_for_function(
        "() => (document.getElementById('containerList').innerText || '').includes('155.75')",
        timeout=10000,
    )

    # Default listing hides voided rows, so the journal shows only the new bag.
    visible = _containers(page, ctx["dropoff"])
    assert len(visible) == 1, f"Journal should show one live bag, got {visible}"
    active = visible[0]
    assert active["status"] == "Active", active
    assert float(active["net_weight"]) == pytest.approx(155.75), active
    assert active["name"] != original, (
        "Active bag should be a NEW container, not the original edited in place"
    )

    # With voided included, the original is there and retired.
    all_rows = _containers(page, ctx["dropoff"], include_voided=True)
    retired = next((r for r in all_rows if r["name"] == original), None)
    assert retired is not None, f"Original {original} missing from full list: {all_rows}"
    assert retired["status"] == "Voided", retired
    assert float(retired["net_weight"]) == pytest.approx(100.0), retired

    # Audit chain: the replacement points back at what it replaced.
    linked = _field(page, "Scrap Weight Container", active["name"], "reweighed_from")
    assert linked == original, f"reweighed_from={linked!r}, expected {original!r}"

    # Exactly one live bag in the journal.
    assert page.evaluate(
        "() => document.getElementById('containerCountBadge').textContent"
    ) == "1", "Reweigh should supersede the bag, not create a second active one"


def test_ctn_scan_loads_parent_dropoff(authed_page, seeded, base_url):
    """Scanning a container QR pulls up its parent Dropoff and flashes the row.

    Wave 11 routed CTN scans through `unifiedScanHandler`, which resolves the
    container's parent via `get_container`, loads that Dropoff for full
    context, then highlights the matching journal row. The concern noted in
    §14.22 was that a CTN belonging to a Dropoff other than the one on screen
    might silently bail; this drives the same code path from a cleared context,
    which is what the operator hits when scanning a bag out of the blue.

    Note: the seeder creates a single Dropoff, so this exercises
    no-context -> correct-Dropoff rather than dropoff-A -> dropoff-B. Both go
    through the identical `searchAndSelectDropoff(c.dropoff)` call, but the
    two-Dropoff switch is still worth eyeballing in the hardware walkthrough.
    """
    page = authed_page
    ctx = seeded

    _open_terminal(page, ctx, base_url)
    _add_container(page, ctx["item_a"], 63.5)

    rows = _containers(page, ctx["dropoff"])
    assert rows
    ctn = rows[0]["name"]

    # Clear the terminal so the scan has to resolve context from scratch.
    page.evaluate("() => window.clearDropoff()")
    page.wait_for_selector("#containerPanel", state="hidden", timeout=5000)

    # Scan the bag.
    page.evaluate("(raw) => window.unifiedScanHandler(raw)", ctn)

    # The parent Dropoff loads...
    page.wait_for_selector("#containerPanel", state="visible", timeout=10000)
    page.wait_for_function(
        "(want) => (document.getElementById('containerList').innerText || '').includes(want)",
        arg=ctn,
        timeout=10000,
    )

    # ...and the scanned row flashes. The class is removed after 2.4s, so poll
    # for its arrival rather than asserting once.
    page.wait_for_function(
        """(name) => {
            const row = document.querySelector('.container-row[data-name="' + CSS.escape(name) + '"]');
            return !!row && row.classList.contains('container-row-highlight');
        }""",
        arg=ctn,
        timeout=8000,
    )

    assert "63.5" in page.locator("#containerList").inner_text()


def test_container_photo_viewer_surface(authed_page, seeded, base_url):
    """The journal's photo count is a button that opens the bag's saved photos.

    Before this, updatePhotoThumbnails() could render an "existing photos"
    section but nothing populated it for containers — the count was inert. A
    freshly weighed bag has no photos, so the viewer should say so rather than
    opening an empty modal, and must not leave capture mode broken.
    """
    page = authed_page
    ctx = seeded

    _open_terminal(page, ctx, base_url)
    _add_container(page, ctx["item_a"], 42.0)

    rows = _containers(page, ctx["dropoff"])
    assert rows
    name = rows[0]["name"]
    assert int(rows[0].get("photo_count") or 0) == 0

    assert page.evaluate(
        "() => typeof window.CONTAINER_UI.viewPhotos === 'function'"
    ), "CONTAINER_UI.viewPhotos not exposed"

    # No photos on a fresh bag -> the count button is not rendered at all.
    assert page.locator("#containerList .container-row-photo").count() == 0

    # Calling the viewer must not throw or open an empty modal.
    page.evaluate("(n) => window.CONTAINER_UI.viewPhotos(n)", name)
    page.wait_for_timeout(1500)
    assert page.evaluate(
        "() => document.getElementById('photoModal').style.display !== 'flex'"
    ), "Photo viewer should stay closed when the bag has no photos"

    # View-only teardown must not have clobbered capture mode.
    restored = page.evaluate(
        """() => {
            const m = document.getElementById('photoModal');
            return {
                viewOnly: m.dataset.viewOnly || null,
                saveBtn: document.getElementById('savePhotoBtn').style.display,
            };
        }"""
    )
    assert restored["viewOnly"] is None, restored
    assert restored["saveBtn"] != "none", restored
