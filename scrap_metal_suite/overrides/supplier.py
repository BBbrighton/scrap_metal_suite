"""Supplier DocType overrides and hooks"""

import re

import frappe
from frappe import _


SHORT_CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,8}$")
ASCII_PREFIX_LEN = 4
MAX_COLLISION_TRIES = 99


def set_source_on_manual_create(doc, method=None):
    """Set source field when supplier is created manually."""
    if not doc.get("custom_source"):
        doc.custom_source = "Manual"


def populate_short_code(doc, method=None):
    """Auto-default + validate `Supplier.short_code`.

    Used in document IDs as `PLO-{short_code}-YYMM-###`. ASCII-only so docnames
    stay clean for URLs, CLI, copy-paste, and accounting paper. Field is
    `unique` and `reqd: 1` on the Custom Field; this hook fills it in when the
    operator hasn't typed one and the supplier_name has at least 2 ASCII
    alphanumerics to seed from.

    Behaviour:
        - If `short_code` is already set: validate format only.
        - Else if supplier_name has >= 2 ASCII alphanumerics: derive from first
          `ASCII_PREFIX_LEN` chars uppercased; append numeric suffix on
          collision (`ACME`, `ACME2`, `ACME3`, ...).
        - Else (Thai-only / no usable ASCII chars): leave blank — the Custom
          Field's `reqd: 1` will block save until the operator types one. We
          surface a clearer message with frappe.throw() before the framework's
          generic missing-field error.
    """
    if doc.short_code:
        _validate_short_code_format(doc.short_code)
        return

    candidate = _derive_default(doc.supplier_name or "")
    if not candidate:
        frappe.throw(
            _(
                "Short Code is required. Auto-default could not derive an ASCII "
                "abbreviation from the supplier name — please type a 2-8 character "
                "code (A-Z, 0-9) the office uses for this supplier (e.g. TRP, ACME01)."
            ),
            title=_("Short Code Required"),
        )

    doc.short_code = _free_short_code(candidate, exclude_supplier=doc.name)


def _validate_short_code_format(value: str) -> None:
    if not SHORT_CODE_PATTERN.match(value or ""):
        frappe.throw(
            _("Short Code must be 2-8 ASCII characters (A-Z, 0-9 only). Got: {0}").format(value),
            title=_("Invalid Short Code"),
        )


def _derive_default(supplier_name: str) -> str:
    """Return first ASCII_PREFIX_LEN ASCII alphanumeric chars, uppercased.
    Empty string if fewer than 2 such chars exist (e.g. Thai-only name)."""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", supplier_name)
    cleaned = cleaned.upper()[:ASCII_PREFIX_LEN]
    return cleaned if len(cleaned) >= 2 else ""


def _free_short_code(base: str, exclude_supplier: str | None) -> str:
    """Return `base` if no other Supplier holds it; else `base{n}` with n=2..."""
    if not _is_taken(base, exclude_supplier):
        return base
    for n in range(2, MAX_COLLISION_TRIES + 1):
        candidate = f"{base}{n}"
        # Cap at 8 chars — the Custom Field's max length.
        if len(candidate) > 8:
            break
        if not _is_taken(candidate, exclude_supplier):
            return candidate
    frappe.throw(
        _("Could not auto-generate a unique Short Code from {0}; please type one manually.").format(base),
        title=_("Short Code Collision"),
    )


def _is_taken(code: str, exclude_supplier: str | None) -> bool:
    filters = {"short_code": code}
    if exclude_supplier:
        filters["name"] = ["!=", exclude_supplier]
    return bool(frappe.db.exists("Supplier", filters))
