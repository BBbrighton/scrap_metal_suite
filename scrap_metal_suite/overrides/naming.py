"""Shared naming helpers for supplier-coded autoname patterns.

All four target doctypes (SMT Price Lock, POS Order, SMT Purchase Order,
Dropoff) embed `Supplier.short_code` in their docnames so a paper-readable ID
identifies WHO and WHEN at a glance:

    PLO-{short}-YYMM-###    (SMT Price Lock)
    PDR-{short}-YYMM-###    (POS Order — mirrors PLO when sourced from one)
    SPO-{short}-YYMM-###    (SMT Purchase Order)
    DO-{short}-YYMMDD-#     (Dropoff)

Counters are scoped per-prefix via `frappe.model.naming.make_autoname`, so each
(supplier × period) combo has its own counter starting at 1. The `.#` notation
is a *minimum* zero-padding; counters grow gracefully past the pad if a
supplier exceeds the daily/monthly volume.

See docs/DROPOFF_CONTAINER_REDESIGN.md §14.16 for the design rationale.
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import getdate, now_datetime


def supplier_short(supplier: str | None) -> str:
    """Return `Supplier.short_code` or throw if missing.

    Every supplier-coded docname relies on the short_code being populated; the
    Custom Field is `reqd: 1` and the supplier `before_save` hook auto-defaults
    or blocks save if it can't. Throwing here is defensive — it means a caller
    constructed the doc with a supplier that has no short_code, which should
    never happen in practice.
    """
    if not supplier:
        frappe.throw(_("Supplier is required to generate a document ID."))
    short = frappe.db.get_value("Supplier", supplier, "short_code")
    if not short:
        frappe.throw(
            _(
                "Supplier {0} has no Short Code. Open the supplier and set one "
                "(2-8 ASCII chars) before creating documents that reference it."
            ).format(supplier),
            title=_("Supplier Short Code Missing"),
        )
    return short


def _yymm(date: datetime | None = None) -> str:
    return (date or now_datetime()).strftime("%y%m")


def _yymmdd(date: datetime | None = None) -> str:
    return (date or now_datetime()).strftime("%y%m%d")


def supplier_monthly_name(prefix: str, supplier: str, padding: int = 3) -> str:
    """Build a name like `PLO-ACME-2604-001` (3-digit counter by default)."""
    short = supplier_short(supplier)
    pad = "#" * padding
    return make_autoname(f"{prefix}-{short}-{_yymm()}-.{pad}")


def supplier_daily_name(
    prefix: str,
    supplier: str,
    on_date: datetime | None = None,
    padding: int = 1,
) -> str:
    """Build a name like `DO-ACME-260427-1` (1-digit counter by default).

    `on_date` is the business date to embed (e.g. `dropoff_scheduled_start`);
    falls back to current time if not provided.
    """
    short = supplier_short(supplier)
    pad = "#" * padding
    # `make_autoname` reads its prefix string verbatim, so `_yymmdd(on_date)`
    # must produce the exact date we want embedded.
    if on_date and not isinstance(on_date, datetime):
        on_date = datetime.combine(getdate(on_date), datetime.min.time())
    return make_autoname(f"{prefix}-{short}-{_yymmdd(on_date)}-.{pad}")


def derive_pdr_from_plo(plo_name: str) -> str:
    """Mirror a PLO name as PDR by swapping the 3-char prefix.

        PLO-ACME-2604-001  ->  PDR-ACME-2604-001

    Assumes 1:1 PLO→PDR (confirmed in the design discussion). If a PLO ever
    spawned multiple PDRs the second insert would collide on the unique name
    constraint, which is the right safety net.
    """
    if not plo_name or len(plo_name) < 4 or not plo_name.startswith("PLO-"):
        frappe.throw(
            _("Cannot derive POS Order name: source Price Lock {0!r} doesn't match the PLO-* pattern.").format(plo_name),
            title=_("Invalid Price Lock Name"),
        )
    return "PDR" + plo_name[3:]
