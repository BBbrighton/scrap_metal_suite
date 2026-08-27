"""Post-deploy readiness check: what the code cannot bring with it.

A deploy carries Python, doctypes, print formats and the patches. It does not
carry the records and site settings a working yard needs — those live in the
database, per site, and every one of them fails *quietly* when absent: an empty
scale picker, a sticker that never prints, a camera badge that does not appear.

Run this straight after `bench migrate` and fix whatever it reports.

    bench --site <site> execute scrap_metal_suite.deploy.readiness.check
"""

import frappe
from frappe.utils import flt

PATCHES = [
    "migrate_to_containers", "backfill_container_snapshot_fields",
    "fix_variance_threshold_defaults", "backfill_settled_value",
    "backfill_pos_order_status", "backfill_supplier_short_codes",
    "seed_variance_settings", "link_variance_settings_workspace",
    "baseline_permissions",
]

# The permissions a workflow cannot run without. Each was missing at some point
# and each broke an entire job silently — see patches/v2_0/baseline_permissions.
CRITICAL_PERMS = [
    ("Truck Weight", "POS Operator", "write", "operators cannot reweigh a truck or attach a photo"),
    ("Scrap Weight", "POS Operator", "submit", "operators cannot issue a weight receipt"),
    ("Scrap Weight", "POS Operator", "cancel", "operators cannot reweigh a bag"),
    ("Production Session", "Production Worker", "create", "sorters cannot start a sorting session"),
    ("Production Sorting", "Production Manager", "cancel", "nobody can reopen a submitted sorting"),
    ("Dropoff Final", "SMT Accountant", "read", "accountants cannot see what they are settling"),
]


def _row(status, what, detail, fix=""):
    return {"status": status, "what": what, "detail": detail, "fix": fix}


def check():
    frappe.set_user("Administrator")
    out = []

    # 1 — patches
    applied = {p.patch.rsplit(".", 1)[-1]
               for p in frappe.get_all("Patch Log", fields=["patch"])
               if "scrap_metal_suite" in p.patch}
    missing = [p for p in PATCHES if p not in applied]
    out.append(_row("FAIL" if missing else "OK", "Migration patches",
                    f"{len(PATCHES) - len(missing)}/{len(PATCHES)} applied"
                    + (f" — missing {missing}" if missing else ""),
                    "bench migrate" if missing else ""))

    # 2 — permissions that gate whole workflows
    bad = []
    for dt, role, perm, why in CRITICAL_PERMS:
        if not frappe.db.exists("DocType", dt):
            continue
        name = frappe.db.get_value("Custom DocPerm", {"parent": dt, "role": role, "permlevel": 0})
        has = frappe.db.get_value("Custom DocPerm", name, perm) if name else None
        if not has:
            bad.append(f"{role} cannot {perm} {dt} → {why}")
    out.append(_row("FAIL" if bad else "OK", "Critical permissions",
                    f"{len(CRITICAL_PERMS) - len(bad)}/{len(CRITICAL_PERMS)} in place",
                    "; ".join(bad) if bad else ""))

    # 3 — a Production scale, or sorting cannot start at all
    n = frappe.db.count("Scale", {"usage_type": "Production", "is_active": 1})
    out.append(_row("OK" if n else "FAIL", "Production scale",
                    f"{n} active",
                    "" if n else "Desk → Scale → New, usage_type=Production, is_active ✓ "
                                 "— without one the sorting picker is empty"))

    # 4 — scrap and truck scales
    for kind in ("Scrap", "Truck"):
        n = frappe.db.count("Scale", {"usage_type": kind, "is_active": 1})
        out.append(_row("OK" if n else "FAIL", f"{kind} scale", f"{n} active",
                        "" if n else f"no {kind} scale — that terminal cannot open a session"))

    # 5 — sticker printing, per profile
    off = [p.name for p in frappe.get_all("POS Profile Scrap", fields=["name"])
           if not frappe.db.get_value("POS Profile Scrap", p.name, "enable_sticker_print")]
    out.append(_row("WARN" if off else "OK", "Sticker printing",
                    f"{len(off)} profile(s) with printing off" if off else "on for every profile",
                    f"tick Enable Sticker Print on {off} — saving works, the sticker "
                    f"silently never prints" if off else ""))

    # 6 — supplier short codes (block document naming)
    if frappe.db.has_column("Supplier", "short_code"):
        blank = [s.name for s in frappe.get_all(
            "Supplier", filters={"short_code": ["in", ["", None]]}, fields=["name"], limit=200)]
        out.append(_row("WARN" if blank else "OK", "Supplier short codes",
                        f"{len(blank)} supplier(s) without one",
                        f"first Price Lock for these fails until set: {blank[:8]}" if blank else ""))
    else:
        out.append(_row("FAIL", "Supplier short codes", "column missing",
                        "backfill_supplier_short_codes did not run"))

    # 7 — variance thresholds
    from scrap_metal_suite.utils.variance import get_all_thresholds, FALLBACKS
    th = get_all_thresholds()
    odd = {k: v for k, v in th.items()
           if k.endswith("_percent") and not k.startswith("fulfillment") and flt(v) > 1.0}
    out.append(_row("WARN" if odd else "OK", "Variance thresholds",
                    ", ".join(f"{k.split('_')[0]}={v}" for k, v in th.items()),
                    f"unusually loose, check these are deliberate: {odd}" if odd else ""))

    # 8 — cameras (optional, but silent when absent)
    n = frappe.db.count("Camera") if frappe.db.exists("DocType", "Camera") else 0
    agent = frappe.conf.get("camera_agent_url")
    out.append(_row("INFO", "CCTV cameras",
                    f"{n} camera(s), agent_url={'set' if agent else 'not set'}",
                    "" if n else "no Camera records — the truck terminal shows an "
                                 "unconfigured badge. Set up per docs/CAMERA_INTEGRATION_HANDOFF.md §3"))

    # 9 — dormant privileged accounts
    risky = []
    for u in frappe.get_all("User", filters={"enabled": 1}, fields=["name", "last_active"]):
        if u.name in ("Guest",):
            continue
        roles = {h.role for h in frappe.get_all("Has Role", filters={"parent": u.name}, fields=["role"])}
        if "System Manager" in roles and not u.last_active:
            risky.append(u.name)
    out.append(_row("WARN" if risky else "OK", "Dormant admin accounts",
                    f"{len(risky)} System Manager account(s) that have never logged in",
                    f"disable: {risky}" if risky else ""))

    # 10 — anything left mid-flight
    open_pos = frappe.db.count("POS Session", {"status": "Open"})
    out.append(_row("INFO", "Open sessions", f"{open_pos} POS session(s) open",
                    "close these before migrating" if open_pos else ""))

    width = max(len(r["what"]) for r in out)
    fails = sum(1 for r in out if r["status"] == "FAIL")
    warns = sum(1 for r in out if r["status"] == "WARN")
    print("=" * 78)
    print("POST-DEPLOY READINESS")
    print("=" * 78)
    for r in out:
        mark = {"OK": " ok ", "WARN": "warn", "FAIL": "FAIL", "INFO": "info"}[r["status"]]
        print(f"  [{mark}] {r['what']:<{width}}  {r['detail']}")
        if r["fix"]:
            print(f"          {'':<{width}}  → {r['fix']}")
    print("-" * 78)
    print(f"  {fails} blocking, {warns} to check")
    print("=" * 78)
    return {"fail": fails, "warn": warns}
