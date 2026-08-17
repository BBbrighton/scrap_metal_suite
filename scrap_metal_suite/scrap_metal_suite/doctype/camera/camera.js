// Copyright (c) 2026, Scrap Metal Suite and contributors
// For license information, please see license.txt

frappe.ui.form.on("Camera", {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__("Test Connection"), () => test_connection(frm));

        frm.add_custom_button(__("Live Frame"), () => live_frame(frm));

        frm.set_intro(null);
        if (!frm.doc.is_active) {
            frm.set_intro(__("This camera is inactive and hidden from the terminals."), "orange");
        } else if (!frm.doc.password) {
            // Expected in cloud/agent mode - flag it so it isn't mistaken for a mistake
            frm.set_intro(
                __("No password set. Correct for cloud deployments (the on-site agent holds the credentials), but the server cannot fetch this camera itself."),
                "blue"
            );
        }
    },
});

function test_connection(frm) {
    frappe.dom.freeze(__("Testing {0}...", [frm.doc.name]));

    frappe.call({
        method: "scrap_metal_suite.api.v1.camera.test_connection",
        args: { camera: frm.doc.name },
        callback(r) {
            frappe.dom.unfreeze();
            const res = r.message || {};

            if (res.ok) {
                frappe.msgprint({
                    title: __("Camera reachable"),
                    indicator: "green",
                    message: __("Channel {0} returned {1} KB.", [
                        res.channel,
                        (res.bytes / 1024).toFixed(1),
                    ]) + (res.channel === "102"
                        ? "<br><br>" + __("Note: fell back to the sub-stream, so the main stream (101) did not respond. This is normal on some units.")
                        : ""),
                });
            } else {
                frappe.msgprint({
                    title: __("Camera unreachable"),
                    indicator: "red",
                    message: frappe.utils.escape_html(res.error || __("Unknown error")),
                });
            }
        },
        error() {
            frappe.dom.unfreeze();
        },
    });
}

function live_frame(frm) {
    frappe.dom.freeze(__("Fetching frame..."));

    frappe.call({
        method: "scrap_metal_suite.api.v1.camera.live_frame",
        args: { camera: frm.doc.name },
        callback(r) {
            frappe.dom.unfreeze();
            const image = r.message && r.message.image;

            if (!image) {
                frappe.msgprint({
                    title: __("No frame"),
                    indicator: "red",
                    message: __("The camera returned no image."),
                });
                return;
            }

            new frappe.ui.Dialog({
                title: __("Live Frame — {0}", [frm.doc.name]),
                size: "large",
                fields: [{
                    fieldtype: "HTML",
                    options: `<img src="${image}" style="max-width:100%;border-radius:6px;">`,
                }],
            }).show();
        },
        error() {
            frappe.dom.unfreeze();
        },
    });
}
