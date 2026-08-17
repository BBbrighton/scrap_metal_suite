# Camera API Endpoints
# CCTV capture for the POS weighing terminals.
#
# Thin @frappe.whitelist() wrappers over scrap_metal_suite.camera.service.
# Every endpoint runs check_pos_operator() first - including receive_weight_photo(),
# which is what the on-site capture agent calls. That means the agent's cloud user
# needs the POS Operator role (not System Manager).

import base64

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from scrap_metal_suite.api.v1.auth import check_pos_operator
from scrap_metal_suite.camera import service


@frappe.whitelist()
def get_cameras(usage_type=None):
    """List active cameras, optionally filtered by usage_type."""
    check_pos_operator()

    cameras = service.list_cameras(usage_type)

    return {
        "success": True,
        "usage_type": usage_type,
        "count": len(cameras),
        "cameras": cameras,
    }


@frappe.whitelist()
def live_frame(camera):
    """One preview frame as a data URI. Polled by CameraClient.startPreview()."""
    check_pos_operator()

    doc = service.get_camera(camera)
    content = service.fetch_snapshot(doc, timeout=service.PREVIEW_TIMEOUT)

    return {
        "success": True,
        "camera": doc.name,
        "image": "data:image/jpeg;base64," + base64.b64encode(content).decode("ascii"),
        "ts": now_datetime(),
    }


@frappe.whitelist()
def capture_snapshot(camera, parent_doctype, parent_doc, weight_type=None,
                     dropoff=None, session=None, high_res=1):
    """Backend-fetch capture: this host pulls the JPEG and stores it.

    Only works when the Frappe server is on the camera LAN (dev / on-prem).
    In cloud production the terminal talks to the local agent instead, which
    calls receive_weight_photo() below.
    """
    check_pos_operator()

    return service.capture_to_weight_photo(
        camera,
        parent_doctype=parent_doctype,
        parent_doc=parent_doc,
        weight_type=weight_type,
        dropoff=dropoff,
        session=session,
        high_res=cint(high_res),
    )


@frappe.whitelist()
def test_connection(camera):
    """Verify a camera answers, without storing anything."""
    check_pos_operator()

    doc = service.get_camera(camera)

    try:
        content, channel = service.capture_bytes(doc, high_res=1)
    except Exception as e:
        return {
            "ok": False,
            "camera": doc.name,
            "error": str(e),
        }

    return {
        "ok": True,
        "camera": doc.name,
        "channel": channel,
        "bytes": len(content),
    }


@frappe.whitelist()
def receive_weight_photo(parent_doctype, parent_doc, weight_type=None, image_b64=None,
                         camera=None, dropoff=None, session=None):
    """Agent upload: store a JPEG the on-site agent already fetched.

    The agent authenticates with the API key/secret of a dedicated limited user
    ("Camera Agent") which must hold the POS Operator role.

    Tolerates a full data: URI as well as bare base64.
    """
    check_pos_operator()

    if not image_b64:
        frappe.throw(_("image_b64 is required"))

    # Strip a "data:image/jpeg;base64," prefix if the caller sent a data URI
    if "," in image_b64[:64] and image_b64.strip().startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]

    try:
        content = base64.b64decode(image_b64)
    except Exception:
        frappe.throw(_("image_b64 is not valid base64"))

    if not content:
        frappe.throw(_("Decoded image is empty"))

    return service.store_weight_photo_bytes(
        content,
        parent_doctype=parent_doctype,
        parent_doc=parent_doc,
        weight_type=weight_type,
        dropoff=dropoff,
        session=session,
        camera=camera,
    )
