"""Prove the container migration did not move any weight.

Run this on a scratch site restored from a PRODUCTION backup, once before
`bench migrate` and once after, then compare. The migration's whole risk sits
in one assumption:

    the LATEST Scrap Weight per Dropoff is canonical; older ones are stale
    snapshots and must be ignored, not summed

If that is wrong for even one dropoff, its weight changes silently. Nothing
else in the patch set can lose data — all eight are additive — so this is the
check that matters.

    bench --site <scratch> execute scrap_metal_suite.deploy.reconcile_migration.before
    bench --site <scratch> migrate
    bench --site <scratch> execute scrap_metal_suite.deploy.reconcile_migration.after
"""

import json
import os

import frappe
from frappe.utils import flt

SNAPSHOT = "/tmp/smt_migration_before.json"


def _legacy_weight_per_dropoff():
    """Weight per dropoff as the OLD model saw it: latest Scrap Weight only."""
    out = {}
    rows = frappe.db.sql(
        """
        SELECT sw.name, sw.dropoff, sw.creation
        FROM `tabScrap Weight` sw
        WHERE sw.dropoff IS NOT NULL AND sw.dropoff != ''
        ORDER BY sw.dropoff, sw.creation
        """,
        as_dict=True,
    )
    latest = {}
    counts = {}
    for r in rows:
        counts[r.dropoff] = counts.get(r.dropoff, 0) + 1
        latest[r.dropoff] = r.name          # ordered by creation, so last wins

    for dropoff, sw_name in latest.items():
        items = frappe.db.sql(
            """SELECT item_code, weight FROM `tabScrap Weight Item` WHERE parent=%s""",
            sw_name, as_dict=True,
        )
        out[dropoff] = {
            "latest_sw": sw_name,
            "sw_count": counts[dropoff],
            "items": len(items),
            "weight": round(sum(flt(i.weight) for i in items), 3),
        }
    return out


def _count_containers():
    """Container count, tolerating the table not existing yet.

    `before()` runs against the OLD schema, where `Scrap Weight Container` has
    never been created — counting it there raises rather than returning 0.
    """
    try:
        return frappe.db.count("Scrap Weight Container")
    except Exception:
        return 0


def before():
    frappe.set_user("Administrator")
    snap = {
        "legacy": _legacy_weight_per_dropoff(),
        "orphan_sw": frappe.db.sql(
            """SELECT count(*) FROM `tabScrap Weight`
               WHERE dropoff IS NULL OR dropoff=''"""
        )[0][0],
        "containers": _count_containers(),
        "dropoffs": frappe.db.count("Dropoff"),
    }
    json.dump(snap, open(SNAPSHOT, "w"), ensure_ascii=False, indent=1)

    multi = {d: v for d, v in snap["legacy"].items() if v["sw_count"] > 1}
    print("=" * 72)
    print("BEFORE MIGRATION")
    print("=" * 72)
    print(f"  dropoffs                       {snap['dropoffs']}")
    print(f"  dropoffs with scrap weight     {len(snap['legacy'])}")
    print(f"  containers (expect 0)          {snap['containers']}")
    print(f"  orphaned Scrap Weight          {snap['orphan_sw']}  (no dropoff — will be SKIPPED)")
    print(f"  expected containers to create  {sum(v['items'] for v in snap['legacy'].values())}")
    print()
    print(f"  ** dropoffs with MORE THAN ONE Scrap Weight: {len(multi)} **")
    print("     these are the ones the migration has to judge; everything else is trivial")
    for d, v in sorted(multi.items()):
        print(f"       {d:26} {v['sw_count']} SWs -> keeping {v['latest_sw']} "
              f"({v['items']} items, {v['weight']} kg)")
    if not multi:
        print("       none — the risky branch will not execute on this data")
    print(f"\n  snapshot written to {SNAPSHOT}")


def after():
    frappe.set_user("Administrator")
    if not os.path.exists(SNAPSHOT):
        frappe.throw(f"{SNAPSHOT} missing — run before() first")
    snap = json.load(open(SNAPSHOT))
    legacy = snap["legacy"]

    print("=" * 72)
    print("AFTER MIGRATION")
    print("=" * 72)

    mismatches, missing = [], []
    for dropoff, old in sorted(legacy.items()):
        rows = frappe.db.sql(
            """SELECT item_code, net_weight FROM `tabScrap Weight Container`
               WHERE dropoff=%s AND status='Active'""",
            dropoff, as_dict=True,
        )
        if not rows:
            missing.append(dropoff)
            continue
        new_w = round(sum(flt(r.net_weight) for r in rows), 3)
        if abs(new_w - old["weight"]) > 0.001 or len(rows) != old["items"]:
            mismatches.append((dropoff, old["weight"], new_w, old["items"], len(rows)))

    total = frappe.db.count("Scrap Weight Container")
    print(f"  containers created             {total}")
    print(f"  dropoffs reconciled            {len(legacy) - len(mismatches) - len(missing)}/{len(legacy)}")
    print(f"  dropoffs with NO containers    {len(missing)}")
    print(f"  WEIGHT MISMATCHES              {len(mismatches)}")
    print()

    if missing:
        print("  !! these dropoffs produced no containers:")
        for d in missing[:20]:
            print(f"       {d}  (legacy {legacy[d]['weight']} kg over {legacy[d]['items']} items)")
    if mismatches:
        print("  !! WEIGHT CHANGED — DO NOT DEPLOY:")
        for d, ow, nw, oi, ni in mismatches[:20]:
            print(f"       {d:26} {ow} kg / {oi} items  ->  {nw} kg / {ni} items")

    ok = not mismatches and not missing
    print()
    print("  VERDICT:", "PASS — no weight moved, safe to deploy"
          if ok else "FAIL — investigate before deploying")
    print("=" * 72)
    return {"pass": ok, "mismatches": len(mismatches), "missing": len(missing),
            "containers": total}
