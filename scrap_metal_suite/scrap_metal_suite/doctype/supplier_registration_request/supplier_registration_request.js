// Copyright (c) 2024, Scrap Metal Suite and contributors
// For license information, please see license.txt

frappe.ui.form.on("Supplier Registration Request", {
    refresh(frm) {
        // Add approve/reject buttons for Pending Approval status
        if (frm.doc.status === "Pending Approval" && frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Approve"), function() {
                frappe.confirm(
                    __("Are you sure you want to approve this registration and create a new Supplier?"),
                    function() {
                        frm.call({
                            method: "approve",
                            doc: frm.doc,
                            freeze: true,
                            freeze_message: __("Creating Supplier..."),
                            callback: function(r) {
                                if (r.message) {
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __("Actions")).addClass("btn-primary");

            frm.add_custom_button(__("Reject"), function() {
                frappe.prompt({
                    label: __("Rejection Reason"),
                    fieldname: "reason",
                    fieldtype: "Small Text",
                    reqd: 1
                }, function(values) {
                    frm.call({
                        method: "reject",
                        doc: frm.doc,
                        args: {
                            reason: values.reason
                        },
                        freeze: true,
                        freeze_message: __("Rejecting..."),
                        callback: function(r) {
                            frm.reload_doc();
                        }
                    });
                }, __("Reject Registration"), __("Reject"));
            }, __("Actions")).addClass("btn-danger");
        }

        // Show link to created supplier
        if (frm.doc.status === "Approved" && frm.doc.linked_supplier) {
            frm.add_custom_button(__("View Supplier"), function() {
                frappe.set_route("Form", "Supplier", frm.doc.linked_supplier);
            });
        }

        // Color-coded status indicator
        if (frm.doc.status) {
            let indicator = {
                "Draft": "gray",
                "Pending Approval": "orange",
                "Approved": "green",
                "Rejected": "red"
            }[frm.doc.status];

            frm.page.set_indicator(__(frm.doc.status), indicator);
        }
    }
});
