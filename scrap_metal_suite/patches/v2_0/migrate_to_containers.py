"""
Migrate legacy Scrap Weight + Scrap Weight Item data into the new
Scrap Weight Container model.

Background
----------
Before the container redesign, scrap weights for a Dropoff were stored as one
or more `Scrap Weight` documents, each carrying a child table of
`Scrap Weight Item` rows. A long-standing duplication bug (e.g. DO-260320-00002
which has 6 Scrap Weight records for the same physical scrap) meant that every
new Scrap Weight saved a *full* snapshot of the dropoff's items rather than
appending. As a result the **latest** Scrap Weight (by `creation desc`) is the
canonical truth; older ones are stale snapshots and must be ignored, not
summed.

Algorithm (per Dropoff)
-----------------------
1. Skip if the dropoff already has any Scrap Weight Container rows
   (idempotence — re-running `bench migrate` is safe).
2. Find the LATEST `Scrap Weight` for that dropoff, ordered by `creation desc`.
3. For each `Scrap Weight Item` in that latest SW (in `idx` order):
   - Insert one `Scrap Weight Container` with:
       * dropoff, session, scale stamped from the latest SW
       * operator = SW.owner
       * item_code, item_name copied verbatim (item_name is canonical Thai —
         never translated; see docs/BILINGUAL_GUIDE.md §2)
       * container_no = sequential within dropoff (1..N)
       * container_type = "Bag" (legacy data didn't track type — Bag is the
         documented default)
       * net_weight = flt(SWI.weight)
       * entry_method = "Manual Entry"
       * status = "Active"
       * legacy_scrap_weight = latest SW name (audit trail)
       * weight_history: one Container Weight History row, event="Initial"
4. Reload the Dropoff and call `save()` so its on-save hooks
   (`sync_actual_items`, `calculate_net_weight`) recompute aggregates from the
   newly-inserted Active containers.
5. Variance check: compare `total_actual_weight` against the truck `net_weight`.
   Threshold is read from `Dropoff Container Settings.weight_variance_threshold_pct`
   (default 0.1%). Variance above 1% is logged as a warning via
   `frappe.log_error` — the patch does NOT crash on variance.

Pre-flight report
-----------------
Before doing any inserts the patch logs (via frappe.log_error) a summary:
    - total dropoffs to consider
    - dropoffs with N>1 Scrap Weight rows (duplication candidates)
    - total Scrap Weight Item rows in latest-SW set
    - estimated containers to create

Idempotence & safety
--------------------
- Skips dropoffs that already have any Scrap Weight Container.
- Each dropoff is wrapped in try/except so a single bad record does not abort
  the whole migration; failures are logged and counted.
- `flags.ignore_permissions = True` is used on inserts/saves because this is a
  system-level migration, not a user action.
- A single `frappe.db.commit()` is issued at the end.
"""

import frappe
from frappe.utils import flt

# Variance above this percentage of the truck net weight is logged as a
# warning. We deliberately use a more permissive 1% here for migration
# warnings (the settings threshold is for live operational checks).
MIGRATION_WARN_PCT = 1.0


def execute():
    """Migrate Scrap Weight + Scrap Weight Item -> Scrap Weight Container."""

    # The new doctype must exist before we can migrate. If the migration
    # cycle hasn't deployed it yet, defer silently — the next `bench migrate`
    # run will pick it up.
    if not frappe.db.exists("DocType", "Scrap Weight Container"):
        return

    # ----- Pre-flight report ----------------------------------------------
    try:
        all_dropoffs = frappe.db.get_all(
            "Dropoff",
            fields=["name", "net_weight"],
        )
        total_dropoffs = len(all_dropoffs)

        # Dropoffs with N>1 Scrap Weight rows (duplication candidates)
        dup_candidates = 0
        total_latest_items = 0
        for d in all_dropoffs:
            sw_count = frappe.db.count("Scrap Weight", {"dropoff": d.name})
            if sw_count > 1:
                dup_candidates += 1
            if sw_count >= 1:
                latest = frappe.db.get_all(
                    "Scrap Weight",
                    filters={"dropoff": d.name},
                    fields=["name"],
                    order_by="creation desc",
                    limit=1,
                )
                if latest:
                    total_latest_items += frappe.db.count(
                        "Scrap Weight Item", {"parent": latest[0].name}
                    )

        frappe.log_error(
            (
                f"Container migration pre-flight: "
                f"dropoffs={total_dropoffs} "
                f"duplication_candidates(N>1 SW)={dup_candidates} "
                f"latest_sw_items_total={total_latest_items} "
                f"estimated_containers={total_latest_items}"
            ),
            "Container migration pre-flight",
        )
    except Exception as e:
        frappe.log_error(
            f"Pre-flight summary failed: {e}", "Container migration pre-flight"
        )

    # ----- Variance threshold (informational; we use MIGRATION_WARN_PCT) ---
    try:
        settings_pct = flt(
            frappe.db.get_single_value(
                "Dropoff Container Settings", "weight_variance_threshold_pct"
            )
        )
        if settings_pct <= 0:
            settings_pct = 0.1
    except Exception:
        settings_pct = 0.1
    # settings_pct is logged for context but the warn threshold for migration
    # remains MIGRATION_WARN_PCT (1.0%) per the migration plan.

    # ----- Migration loop -------------------------------------------------
    skipped = migrated = errored = warned = 0
    no_sw = no_items = 0

    for d in all_dropoffs:
        try:
            # Idempotence: skip if any container already exists for this dropoff
            if frappe.db.exists("Scrap Weight Container", {"dropoff": d.name}):
                skipped += 1
                continue

            sws = frappe.db.get_all(
                "Scrap Weight",
                filters={"dropoff": d.name},
                fields=["name", "session", "scale", "creation", "owner"],
                order_by="creation desc",
                limit=1,
            )
            if not sws:
                # No legacy weights for this dropoff — nothing to migrate.
                no_sw += 1
                continue

            latest = sws[0]
            items = frappe.db.get_all(
                "Scrap Weight Item",
                filters={"parent": latest.name},
                fields=["item_code", "item_name", "weight"],
                order_by="idx asc",
            )
            if not items:
                no_items += 1
                continue

            operator = latest.get("owner") or frappe.db.get_value(
                "Scrap Weight", latest.name, "owner"
            )

            for idx, item in enumerate(items, start=1):
                container = frappe.get_doc(
                    {
                        "doctype": "Scrap Weight Container",
                        "dropoff": d.name,
                        "session": latest.get("session"),
                        "scale": latest.get("scale"),
                        "operator": operator,
                        "item_code": item.get("item_code"),
                        # item_name is canonical Thai; never translated.
                        "item_name": item.get("item_name"),
                        "container_no": idx,
                        "container_type": "Bag",
                        "net_weight": flt(item.get("weight")),
                        "entry_method": "Manual Entry",
                        "status": "Active",
                        "legacy_scrap_weight": latest.name,
                        "weight_history": [
                            {
                                "doctype": "Container Weight History",
                                "weight": flt(item.get("weight")),
                                "recorded_at": latest.get("creation"),
                                "recorded_by": operator or "Administrator",
                                "event": "Initial",
                                "reason": "Migrated from legacy Scrap Weight",
                                "scale": latest.get("scale"),
                                "entry_method": "Manual Entry",
                            }
                        ],
                    }
                )
                container.flags.ignore_permissions = True
                container.insert()

            # Re-sync aggregates by saving the dropoff (triggers
            # sync_actual_items + calculate_net_weight).
            dropoff_doc = frappe.get_doc("Dropoff", d.name)
            dropoff_doc.flags.ignore_permissions = True
            dropoff_doc.save()

            # Variance verification
            truck_net = flt(dropoff_doc.get("net_weight"))
            actual = flt(dropoff_doc.get("total_actual_weight"))
            if truck_net > 0:
                pct = abs(actual - truck_net) / truck_net * 100.0
                if pct > MIGRATION_WARN_PCT:
                    warned += 1
                    frappe.log_error(
                        (
                            f"Dropoff {d.name}: post-migration variance "
                            f"{pct:.2f}% (truck_net={truck_net} kg, "
                            f"total_actual_weight={actual} kg)"
                        ),
                        "Container migration variance",
                    )

            migrated += 1
        except Exception as e:
            errored += 1
            frappe.log_error(
                f"Failed migrating {d.name}: {e}",
                "Container migration failure",
            )

    # ----- Final summary --------------------------------------------------
    frappe.log_error(
        (
            f"Container migration summary: "
            f"migrated={migrated} skipped={skipped} "
            f"no_scrap_weight={no_sw} no_items={no_items} "
            f"warned={warned} errored={errored} "
            f"settings_variance_pct={settings_pct} "
            f"warn_pct={MIGRATION_WARN_PCT}"
        ),
        "Container migration summary",
    )
    frappe.db.commit()
