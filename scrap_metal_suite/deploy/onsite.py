"""On-site check for camera and printer installation.

Run this on the server while standing at the yard. It covers everything that
can be checked from the cloud side; the two things it cannot see are called out
explicitly at the end, because the agent and the printer live on the
weighbridge PC and only the browser can reach them.

    bench --site smt.x-desk.tech execute scrap_metal_suite.deploy.onsite.check

Numbered findings map to docs/CAMERA_INTEGRATION_HANDOFF.md §5.
"""

import frappe
from frappe.utils import flt


def _p(status, what, detail, fix=""):
    mark = {"OK": " ok ", "WARN": "warn", "FAIL": "FAIL", "INFO": "info"}[status]
    print(f"  [{mark}] {what:<34} {detail}")
    if fix:
        print(f"          {'':<34} → {fix}")
    return status


def check():
    frappe.set_user("Administrator")
    fails = warns = 0
    print("=" * 78)
    print("ON-SITE READINESS — cameras and printing")
    print("=" * 78)

    # ---------- cameras ----------
    print("  CAMERAS")
    agent = frappe.conf.get("camera_agent_url")
    if not agent:
        fails += 1
        _p("FAIL", "camera_agent_url", "not set",
           "bench --site <site> set-config camera_agent_url \"http://127.0.0.1:8787\" "
           "— §5.1#1, the highest-value line in the deployment. Without it every "
           "weigh hangs ~10s then photos fail, because the cloud tries to reach "
           "192.168.1.x itself.")
    else:
        _p("OK", "camera_agent_url", agent)

    cams = frappe.get_all("Camera", fields=["name", "camera_name", "usage_type",
                                            "is_active", "ip_address", "channel"]) \
        if frappe.db.exists("DocType", "Camera") else []
    if not cams:
        fails += 1
        _p("FAIL", "Camera records", "none",
           "Desk → Camera → New, one per camera. camera_name must match the "
           "agent's config.json name EXACTLY — §5.1#2")
    else:
        _p("OK", "Camera records", f"{len(cams)} defined")
        for c in cams:
            issues = []
            if not c.is_active:
                issues.append("not active")
            if c.usage_type != "Truck":
                issues.append(f"usage_type={c.usage_type!r}, expected 'Truck'")
            if c.name != c.camera_name:
                issues.append(f"name {c.name!r} != camera_name {c.camera_name!r}")
            pw = frappe.db.get_value("Camera", c.name, "password")
            if pw:
                issues.append("password set — leave blank in agent mode (§5.1#5)")
            state = "WARN" if issues else "OK"
            if issues:
                warns += 1
            _p(state, f"  {c.camera_name}",
               f"ip={c.ip_address} ch={c.channel}",
               "; ".join(issues))

    # ---------- the agent's cloud identity ----------
    print("  AGENT ACCOUNT")
    agents = []
    for u in frappe.get_all("User", filters={"enabled": 1}, fields=["name"]):
        roles = {h.role for h in frappe.get_all("Has Role", filters={"parent": u.name},
                                                fields=["role"])}
        if "POS Operator" in roles and ("agent" in u.name.lower() or "camera" in u.name.lower()):
            agents.append((u.name, sorted(roles)))
    if not agents:
        warns += 1
        _p("WARN", "camera-agent user", "none found",
           "create a user with EXACTLY the POS Operator role and an API key/secret "
           "(User → Settings → API Access). Without it the agent logs "
           "'cloud HTTP 403' and photos vanish silently — §5.1#3")
    for name, roles in agents:
        extra = [r for r in roles if r not in ("POS Operator", "All", "Guest")]
        _p("WARN" if extra else "OK", f"  {name}", f"roles={roles}",
           f"holds more than POS Operator: {extra} — grant exactly POS Operator" if extra else "")
        if extra:
            warns += 1

    # ---------- the permission that 403s everything ----------
    print("  PERMISSIONS (§3.1 — everything 403s without these)")
    for dt in ("Truck Weight", "Dropoff"):
        n = frappe.db.get_value("Custom DocPerm", {"parent": dt, "role": "POS Operator",
                                                   "permlevel": 0})
        ok = frappe.db.get_value("Custom DocPerm", n, "write") if n else 0
        if not ok:
            fails += 1
        _p("OK" if ok else "FAIL", f"  POS Operator can write {dt}", "yes" if ok else "NO",
           "" if ok else "run baseline_permissions — the agent log will say "
                         "'PermissionError: No permission for " + dt + "'")

    # ---------- printing ----------
    print("  PRINTING")
    for pf, paper in (("Scrap Weight Container Sticker", "50x80mm label"),
                      ("Scrap Weight Thermal", "80mm receipt"),
                      ("Truck Weight Thermal", "80mm receipt"),
                      ("Production Sorting Thermal", "80mm receipt")):
        exists = frappe.db.exists("Print Format", pf)
        disabled = frappe.db.get_value("Print Format", pf, "disabled") if exists else None
        state = "OK" if exists and not disabled else "FAIL"
        if state == "FAIL":
            fails += 1
        _p(state, f"  {pf}", paper if exists else "MISSING",
           "" if exists and not disabled else "print format missing or disabled")

    profiles = frappe.get_all("POS Profile Scrap", fields=["name"])
    for p in profiles:
        on = frappe.db.get_value("POS Profile Scrap", p.name, "enable_sticker_print")
        if not on:
            warns += 1
        _p("OK" if on else "WARN", f"  sticker printing: {p.name}",
           "enabled" if on else "DISABLED",
           "" if on else "saving works and the sticker silently never prints — "
                         "tick Enable Sticker Print on the profile")

    print("-" * 78)
    print(f"  {fails} blocking, {warns} to check")
    print()
    print("  CANNOT BE CHECKED FROM HERE — do these in the browser at the weighbridge:")
    print("    1. Open /camera-test on the weighbridge PC. It probes the agent and each")
    print("       camera and reports resolution per channel. The cloud cannot reach")
    print("       192.168.1.x, so this is the only place reachability is provable.")
    print("    2. curl --digest a snapshot URL before trusting SADP — SADP discovers by")
    print("       broadcast and lists cameras that are not actually routable (§5.2#7).")
    print("    3. Print one sticker on real label stock and one 80mm receipt. Confirm the")
    print("       Thai renders and is not faint.")
    print("    4. Reboot the weighbridge PC and confirm the agent restarts by itself")
    print("       BEFORE leaving site.")
    print("=" * 78)
    return {"fail": fails, "warn": warns}
