# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

MAIN_CHANNEL = "101"
DEFAULT_SUB_CHANNEL = "102"


class Camera(Document):
    def validate(self):
        # Match the Scale convention: the naming field is normalised uppercase
        if self.camera_name:
            self.camera_name = self.camera_name.upper().strip()

        if not self.port:
            self.port = 80

        if self.channel:
            self.channel = str(self.channel).strip()
        else:
            self.channel = DEFAULT_SUB_CHANNEL

        if self.ip_address:
            self.ip_address = self.ip_address.strip()

    def get_snapshot_url(self, channel=None):
        """Build the ISAPI snapshot URL for this camera.

        Args:
            channel: override the configured channel (e.g. "101" for main stream)

        Returns:
            str: full snapshot URL
        """
        if not self.ip_address:
            frappe.throw(_("Camera {0} has no IP address configured").format(self.name))

        ch = str(channel or self.channel or DEFAULT_SUB_CHANNEL).strip()
        port = self.port or 80

        return (
            "http://{ip}:{port}/ISAPI/Streaming/channels/{ch}/picture"
            "?snapShotImageType=JPEG".format(ip=self.ip_address, port=port, ch=ch)
        )
