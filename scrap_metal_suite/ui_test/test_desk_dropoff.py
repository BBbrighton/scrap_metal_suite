# UI test: Frappe desk — Dropoff "Mark Verified (Override)" button.
#
# Drives the manual override flow on the Dropoff form:
#   1. seed a Dropoff with verification_status = "Needs Review"
#   2. login as Administrator
#   3. visit /app/dropoff/<name>
#   4. click the "Mark Verified (Override)" custom button
#   5. fill the prompt with an override reason, click Confirm
#   6. assert: verification_status flips to "Verified",
#      verification_overridden=1, override_reason recorded

import json

import pytest

from .conftest import KEEP_DATA


SEED_METHOD = "scrap_metal_suite.ui_test.fixtures.seed_desk_dropoff_needs_review"


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


def test_mark_verified_override(authed_page, seeded, base_url):
    page = authed_page
    name = seeded["dropoff"]

    page.goto(f"{base_url}/app/dropoff/{name}", wait_until="domcontentloaded")

    # Brief settle, then introspect what loaded — useful failure context.
    page.wait_for_timeout(3000)
    print(f"[desk-test] URL after goto: {page.url}")
    print(f"[desk-test] Title: {page.title()}")
    print(f"[desk-test] body class: {page.locator('body').get_attribute('class')}")

    # Wait for the form layout (status field is mandatory on Dropoff and
    # always rendered). Fallback to any form-layout class.
    try:
        page.wait_for_selector(
            ".frappe-control[data-fieldname='status'], .form-layout, .form-page",
            state="attached",
            timeout=20000,
        )
    except Exception:
        # Dump the visible top-level structure for debugging.
        snippet = page.evaluate(
            "() => document.body ? document.body.innerHTML.slice(0, 1500) : '(no body)'"
        )
        print(f"[desk-test] body[0:1500]:\n{snippet}")
        raise

    # Give refresh handlers time to register custom buttons.
    page.wait_for_timeout(3000)

    # The custom button "Mark Verified (Override)" sits at top-level (not in
    # a group).
    page.get_by_role("button", name="Mark Verified (Override)").click()

    # A Frappe `prompt` dialog opens. Locate the reason textarea by
    # data-fieldname (set from the prompt's fieldname kwarg) — this is
    # locale-independent. Then fill it.
    reason_box = page.locator(
        ".modal.show [data-fieldname='reason'] textarea, "
        ".modal-dialog [data-fieldname='reason'] textarea"
    ).first
    reason_box.wait_for(state="visible", timeout=8000)
    reason_box.fill("Manually verified after operator review — UI test")

    # Click "Confirm" — the primary action in the modal footer.
    page.locator(".modal.show .btn-primary, .modal-dialog .btn-primary").first.click()

    # Wait for the save round-trip and form reload.
    page.wait_for_timeout(2000)

    # Assert state via the frappe form API (most reliable).
    state = page.evaluate(
        """async (name) => {
            const r = await frappe.db.get_doc('Dropoff', name);
            return {
                verification_status: r.verification_status,
                verification_overridden: r.verification_overridden,
                verification_override_reason: r.verification_override_reason,
                verification_override_by: r.verification_override_by,
            };
        }""",
        name,
    )

    assert state["verification_status"] == "Verified", state
    assert state["verification_overridden"] == 1, state
    assert "UI test" in (state["verification_override_reason"] or ""), state
    assert state["verification_override_by"] == "Administrator", state
