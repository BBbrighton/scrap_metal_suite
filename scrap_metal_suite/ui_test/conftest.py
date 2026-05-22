# UI test scaffolding for scrap_metal_suite.
#
# Tests run against a live bench dev server. Start it before invoking pytest:
#   bench start &
#
# Then, from frappe-bench root:
#   env/bin/pytest apps/scrap_metal_suite/scrap_metal_suite/ui_test/ -v
#
# Requirements: playwright + pytest-playwright + chromium browser.
#   pip install playwright pytest pytest-playwright
#   playwright install chromium

import os
import socket
import subprocess
from urllib.parse import urlparse

import pytest


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SITE = os.environ.get("SMT_UI_SITE", "metal")
BASE_URL = os.environ.get("SMT_UI_BASE_URL", "http://localhost:8000")
ADMIN_USER = os.environ.get("SMT_UI_ADMIN_USER", "Administrator")
ADMIN_PWD = os.environ.get("SMT_UI_ADMIN_PWD", "admin")
HEADLESS = os.environ.get("SMT_UI_HEADLESS", "0") != "0"
# Set SMT_UI_KEEP_DATA=1 to skip the teardown cleanup so seeded data
# (Dropoff, containers, session, supplier, scale, profile, PL, PO) is
# left in the DB after the test run for manual inspection.
KEEP_DATA = os.environ.get("SMT_UI_KEEP_DATA", "0") != "0"


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _bench_server_alive():
    """Fail fast if the bench server isn't reachable."""
    parsed = urlparse(BASE_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        try:
            sock.connect((host, port))
        except OSError as e:
            pytest.exit(
                f"Bench server not reachable at {BASE_URL} ({e}). "
                f"Run `bench start` from ~/frappe-bench in another terminal.",
                returncode=2,
            )


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def site():
    return SITE


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Inject Playwright context defaults — viewport, locale."""
    return {
        **browser_context_args,
        "viewport": {"width": 1400, "height": 900},
        "locale": "en-US",
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    args = {
        **browser_type_launch_args,
        "headless": HEADLESS,
    }
    # When running headed, slow each action by ~250ms so the human can
    # actually see what the test is doing. Override with SMT_UI_SLOW_MO=0.
    if not HEADLESS:
        args["slow_mo"] = int(os.environ.get("SMT_UI_SLOW_MO", "250"))
    return args


@pytest.fixture
def authed_page(page, base_url, request):
    """A Playwright Page logged in as Administrator with cookies set.

    Captures console + page errors to a list and dumps them on failure
    along with a screenshot. Helps debug headed-mode timeouts.
    """
    # Frappe's login endpoint accepts form-encoded {usr, pwd} and sets `sid`.
    response = page.context.request.post(
        f"{base_url}/api/method/login",
        form={"usr": ADMIN_USER, "pwd": ADMIN_PWD},
    )
    assert response.ok, (
        f"Login failed: {response.status} {response.status_text}. "
        f"Override admin password via SMT_UI_ADMIN_PWD env var if not 'admin'."
    )

    console_log = []
    page.on("console", lambda msg: console_log.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: console_log.append(f"[pageerror] {err}"))

    yield page

    # On failure, dump console + screenshot to /tmp.
    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        out_dir = "/tmp/smt-ui-test-failures"
        os.makedirs(out_dir, exist_ok=True)
        ts = request.node.name.replace("[", "_").replace("]", "")
        try:
            page.screenshot(path=f"{out_dir}/{ts}.png", full_page=True)
        except Exception:
            pass
        with open(f"{out_dir}/{ts}.console.log", "w") as f:
            f.write("\n".join(console_log))
        print(f"\n[SMT-UI] Failure artefacts: {out_dir}/{ts}.{{png,console.log}}")


# Capture pytest test outcome so authed_page teardown can detect failures.
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ---------------------------------------------------------------------------
# DB seed helpers — invoke Frappe via `bench execute` for transactional
# fixture setup. Faster than the REST API for multi-doc seeding.
# ---------------------------------------------------------------------------

def bench_execute(method_path, kwargs=None):
    """Run a server-side method via `bench --site <SITE> execute`.

    The method must be importable and accept keyword args. The return
    value is whatever the method prints / returns to stdout.
    """
    cmd = ["bench", "--site", SITE, "execute", method_path]
    if kwargs:
        import json
        cmd.extend(["--kwargs", json.dumps(kwargs)])

    result = subprocess.run(
        cmd,
        cwd=os.path.expanduser("~/frappe-bench"),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"bench execute failed:\n{result.stdout}\n---\n{result.stderr}"
        )
    return result.stdout


@pytest.fixture
def seeder():
    """Helper bound to `bench_execute` — pass through args."""
    return bench_execute
