# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

"""
Reusable CCTV camera library (backend half of the camera module).

Importable from any server code:

    from scrap_metal_suite.camera import service

Two transports feed the same storage path:

  * backend fetch - this module Digest-GETs the camera itself. Only works when
    the Frappe host is on the camera LAN (dev / on-prem).
  * agent upload  - the on-site agent Digest-fetches on the LAN and POSTs the
    JPEG to api/v1/camera.receive_weight_photo, which calls
    store_weight_photo_bytes() directly.

Storage is factored into store_weight_photo_bytes() so both paths produce
identical Weight Photo rows. It reuses dropoff.save_weight_photo(), so there
are no edits to dropoff.py or the Weight Photo doctype.
"""

import hashlib
import re

import frappe
import requests
from frappe import _
from frappe.utils import cint, now_datetime
from requests.auth import HTTPDigestAuth

from scrap_metal_suite.api.v1.dropoff import save_weight_photo

MAIN_CHANNEL = "101"
DEFAULT_SUB_CHANNEL = "102"

# Preview is polled ~1.25 fps, so it must fail fast; a saved capture may wait.
PREVIEW_TIMEOUT = 4
CAPTURE_TIMEOUT = 10

ALLOWED_PARENTS = ("Scrap Weight", "Truck Weight")


# =============================================================================
# CAMERA LOOKUP
# =============================================================================

def list_cameras(usage_type=None):
    """Active cameras, optionally filtered by usage_type.

    Args:
        usage_type: "Truck" / "Scrap" / "Production", or None for all

    Returns:
        list[dict]: camera_name, usage_type, location, channel, ip_address
    """
    filters = {"is_active": 1}
    if usage_type:
        filters["usage_type"] = usage_type

    return frappe.get_all(
        "Camera",
        filters=filters,
        fields=["name", "camera_name", "usage_type", "location", "channel", "ip_address"],
        order_by="camera_name asc",
    )


def get_camera(camera):
    """Resolve a camera name (or an already-loaded doc) to an active Camera doc.

    Raises if the camera is missing or inactive - callers treat that as a
    configuration error, not a transient failure.
    """
    if not camera:
        frappe.throw(_("Camera is required"))

    # Already a doc - trust it but still enforce the active check
    doc = camera if hasattr(camera, "doctype") else None

    if doc is None:
        if not frappe.db.exists("Camera", camera):
            frappe.throw(_("Camera '{0}' not found").format(camera))
        doc = frappe.get_doc("Camera", camera)

    if not doc.is_active:
        frappe.throw(_("Camera '{0}' is not active").format(doc.name))

    return doc


def _auth(doc):
    """Digest auth tuple for a camera, or None if no credentials are set."""
    username = doc.username
    password = doc.get_password("password", raise_exception=False) if doc.password else None

    if not username or not password:
        return None

    return HTTPDigestAuth(username, password)


# =============================================================================
# FETCHING
# =============================================================================

def fetch_snapshot(camera, channel=None, timeout=PREVIEW_TIMEOUT):
    """Fetch one JPEG from a camera. Throws on any failure.

    Used by preview and test_connection, where the caller wants the reason.
    """
    doc = get_camera(camera)
    url = doc.get_snapshot_url(channel)

    auth = _auth(doc)
    if auth is None:
        frappe.throw(
            _("Camera '{0}' has no username/password configured for backend fetch").format(doc.name)
        )

    try:
        response = requests.get(url, auth=auth, timeout=timeout)
    except requests.exceptions.RequestException as e:
        frappe.throw(_("Camera '{0}' unreachable: {1}").format(doc.name, str(e)))

    if response.status_code != 200:
        frappe.throw(
            _("Camera '{0}' returned HTTP {1} on channel {2}").format(
                doc.name, response.status_code, channel or doc.channel
            )
        )

    if not response.content:
        frappe.throw(_("Camera '{0}' returned an empty image").format(doc.name))

    return response.content


def try_fetch(camera, channel, timeout=CAPTURE_TIMEOUT):
    """Non-throwing fetch. Returns bytes, or None on any failure.

    Used by capture_bytes() to walk the channel fallback chain without
    aborting on the first non-200.
    """
    try:
        doc = get_camera(camera)
        url = doc.get_snapshot_url(channel)
        auth = _auth(doc)
        if auth is None:
            return None

        response = requests.get(url, auth=auth, timeout=timeout)
        if response.status_code == 200 and response.content:
            return response.content
    except Exception:
        # Deliberately swallowed - the caller falls back to the next channel and
        # throws its own error if every channel fails.
        pass

    return None


def capture_bytes(camera, high_res=1):
    """Fetch a JPEG for saving, preferring the main stream.

    Some units answer HTTP 503 on channel 101 by firmware and only ever serve
    the sub-stream. Falling back means a reachable camera never reports a false
    "offline".

    Returns:
        tuple[bytes, str]: (jpeg content, channel actually used)
    """
    doc = get_camera(camera)
    sub = str(doc.channel or DEFAULT_SUB_CHANNEL).strip()

    order = [MAIN_CHANNEL, sub] if cint(high_res) else [sub, MAIN_CHANNEL]

    tried = []
    for channel in order:
        if channel in tried:
            continue
        tried.append(channel)

        content = try_fetch(doc, channel, CAPTURE_TIMEOUT)
        if content:
            return content, channel

    frappe.throw(
        _("Camera '{0}' returned no image on channel(s) {1}").format(doc.name, ", ".join(tried))
    )


# =============================================================================
# STORAGE (shared by the backend-fetch path and the agent-upload path)
# =============================================================================

def _slug(value):
    """Filesystem-safe fragment for the stored file name."""
    return re.sub(r"[^A-Za-z0-9]+", "-", str(value or "")).strip("-").lower() or "cctv"


def store_weight_photo_bytes(content, parent_doctype, parent_doc, weight_type=None,
                             dropoff=None, session=None, camera=None):
    """Save JPEG bytes as a File and append a Weight Photo row.

    The single storage path for both transports. Reuses
    dropoff.save_weight_photo() so CCTV photos are indistinguishable from
    manually captured ones.

    Args:
        content: raw JPEG bytes
        parent_doctype: "Truck Weight" or "Scrap Weight"
        parent_doc: parent document name
        weight_type: "Truck Gross" / "Truck Tare" / "Scrap"
        dropoff: optional Dropoff name (defaults to the parent's)
        session: optional POS Session name
        camera: camera name, used for the file name and the return payload

    Returns:
        dict: save_weight_photo() result plus camera / file_url / source
    """
    if not content:
        frappe.throw(_("No image content to store"))

    if parent_doctype not in ALLOWED_PARENTS:
        frappe.throw(_("parent_doctype must be 'Scrap Weight' or 'Truck Weight'"))

    if not frappe.db.exists(parent_doctype, parent_doc):
        frappe.throw(_("{0} '{1}' not found").format(parent_doctype, parent_doc))

    # Name pattern: cctv_<YYYYMMDD>_<HHMMSS>_<camera>_<weighttype>_<hash>.jpg
    #
    # The leading timestamp is deliberate: it makes a plain directory listing
    # sort chronologically, so backups and retention cleanups can be scoped by
    # date without consulting the database. The trailing short content hash keeps
    # names unique and lets identical frames be spotted.
    #
    # Camera and weight-type slugs contain no underscores (see _slug), so the
    # fields stay unambiguously splittable on "_".
    stamp = now_datetime().strftime("%Y%m%d_%H%M%S")
    digest = hashlib.sha1(content).hexdigest()[:8]
    file_name = "cctv_{stamp}_{cam}_{wt}_{digest}.jpg".format(
        stamp=stamp, cam=_slug(camera), wt=_slug(weight_type), digest=digest
    )

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "is_private": 0,
        "content": content,
        "attached_to_doctype": parent_doctype,
        "attached_to_name": parent_doc,
    })
    file_doc.save(ignore_permissions=True)

    # Reuse the existing storage path so CCTV photos are indistinguishable from
    # manually captured ones, and dropoff.py stays untouched.
    #
    # NB: this needs write permission on the parent (and, via Truck Weight's
    # on_update hook, on Dropoff). POS Operator holds both. If a capture ever
    # starts failing with PermissionError, check that Custom DocPerm rows for
    # Truck Weight / Dropoff still include POS Operator - editing permissions in
    # the Role Permission Manager replaces the standard rows wholesale and has
    # silently dropped that role before.
    result = save_weight_photo(
        parent_doctype=parent_doctype,
        parent_doc=parent_doc,
        photo_url=file_doc.file_url,
        weight_type=weight_type,
        dropoff=dropoff,
        session=session,
    )

    result["camera"] = camera
    result["file_url"] = file_doc.file_url
    result["source"] = "cctv"

    return result


# =============================================================================
# BACKEND-FETCH CAPTURE (dev / on-prem only)
# =============================================================================

def capture_to_weight_photo(camera, parent_doctype, parent_doc, weight_type=None,
                            dropoff=None, session=None, high_res=1):
    """Fetch from the camera (from this host) and store the result.

    Only usable where the Frappe backend is on the camera LAN. In cloud
    production the agent path is used instead - see
    api/v1/camera.receive_weight_photo().
    """
    doc = get_camera(camera)
    content, channel = capture_bytes(doc, high_res=high_res)

    result = store_weight_photo_bytes(
        content,
        parent_doctype=parent_doctype,
        parent_doc=parent_doc,
        weight_type=weight_type,
        dropoff=dropoff,
        session=session,
        camera=doc.name,
    )

    result["channel"] = channel
    return result
