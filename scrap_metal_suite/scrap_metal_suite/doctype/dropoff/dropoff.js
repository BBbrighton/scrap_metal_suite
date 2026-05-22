frappe.ui.form.on('Dropoff', {
    refresh: function(frm) {
        if (frm.is_new()) {
            return;
        }

        const status = frm.doc.status;
        const group = __('Container Actions');

        // Pause (In Progress only)
        if (status === 'In Progress') {
            frm.add_custom_button(__('Pause Weighing'), () => {
                frappe.prompt(
                    [
                        {
                            fieldname: 'reason',
                            label: __('Reason'),
                            fieldtype: 'Small Text',
                        },
                    ],
                    (v) => {
                        frappe.call({
                            method: 'scrap_metal_suite.api.v1.dropoff.pause_dropoff',
                            args: {
                                dropoff: frm.doc.name,
                                reason: v.reason || '',
                            },
                            callback: () => frm.reload_doc(),
                        });
                    },
                    __('Pause Weighing'),
                    __('Pause')
                );
            }, group);
        }

        // Resume (Paused only) — prompts for session
        if (status === 'Paused') {
            frm.add_custom_button(__('Resume Weighing'), () => {
                frappe.prompt(
                    [
                        {
                            fieldname: 'session',
                            label: __('POS Session'),
                            fieldtype: 'Link',
                            options: 'POS Session',
                            reqd: 1,
                        },
                    ],
                    (v) => {
                        frappe.call({
                            method: 'scrap_metal_suite.api.v1.dropoff.resume_dropoff',
                            args: {
                                dropoff: frm.doc.name,
                                session: v.session,
                            },
                            callback: () => frm.reload_doc(),
                        });
                    },
                    __('Resume Weighing'),
                    __('Resume')
                );
            }, group);
        }

        // Switch Scale and Reassign Session: removed from the desk UI per the
        // "one scale, one session per dropoff" invariant. Mid-dropoff scale
        // swaps and session handovers are out of scope; if a real disruption
        // happens, the operator should void the dropoff and start fresh.
        // The underlying API endpoints (`switch_scale`, `reassign_dropoff`)
        // are kept for emergency console use by sysadmins, but no operator
        // path leads to them.

        // Mark Verified (Override) — Needs Review
        if (frm.doc.verification_status === 'Needs Review' && !frm.doc.verification_overridden) {
            frm.add_custom_button(__('Mark Verified (Override)'), () => {
                frappe.prompt(
                    [
                        {
                            fieldname: 'reason',
                            label: __('Override Reason'),
                            fieldtype: 'Small Text',
                            reqd: 1,
                        },
                    ],
                    (v) => {
                        frappe.call({
                            method: 'scrap_metal_suite.api.v1.dropoff.verify_dropoff',
                            args: {
                                dropoff: frm.doc.name,
                                override_reason: v.reason,
                            },
                            callback: () => frm.reload_doc(),
                        });
                    },
                    __('Mark Verified'),
                    __('Confirm')
                );
            });
        }

        // Print buttons (In Progress) — bulk per-container print
        if (status === 'In Progress') {
            frm.add_custom_button(__('Print all (thermal)'), () => {
                frappe.call({
                    method: 'scrap_metal_suite.api.v1.dropoff.list_containers',
                    args: { dropoff: frm.doc.name },
                    callback: (r) => {
                        (r.message || [])
                            .filter((c) => c.status === 'Active')
                            .forEach((c) => {
                                const url =
                                    '/printview?doctype=Scrap%20Weight%20Container' +
                                    '&name=' +
                                    encodeURIComponent(c.name) +
                                    '&format=Scrap%20Weight%20Container%20Thermal' +
                                    '&no_letterhead=1';
                                window.open(url, '_blank');
                            });
                    },
                });
            }, __('Print'));

            frm.add_custom_button(__('Print all (stickers)'), () => {
                frappe.call({
                    method: 'scrap_metal_suite.api.v1.dropoff.list_containers',
                    args: { dropoff: frm.doc.name },
                    callback: (r) => {
                        (r.message || [])
                            .filter((c) => c.status === 'Active')
                            .forEach((c) => {
                                const url =
                                    '/printview?doctype=Scrap%20Weight%20Container' +
                                    '&name=' +
                                    encodeURIComponent(c.name) +
                                    '&format=Scrap%20Weight%20Container%20Sticker' +
                                    '&no_letterhead=1';
                                window.open(url, '_blank');
                            });
                    },
                });
            }, __('Print'));
        }
    },

    dropoff_scheduled_start: function(frm) {
        // When start datetime changes, auto-set the end datetime
        if (frm.doc.dropoff_scheduled_start && !frm.doc.dropoff_scheduled_end) {
            // Get the date from start
            let start = frappe.datetime.str_to_obj(frm.doc.dropoff_scheduled_start);

            // Set end to same date, 2 hours later (default)
            let end = new Date(start);
            end.setHours(end.getHours() + 2);

            frm.set_value('dropoff_scheduled_end', frappe.datetime.obj_to_str(end));
        }
    },

    dropoff_scheduled_end: function(frm) {
        // Validate end > start
        if (frm.doc.dropoff_scheduled_start && frm.doc.dropoff_scheduled_end) {
            let start = frappe.datetime.str_to_obj(frm.doc.dropoff_scheduled_start);
            let end = frappe.datetime.str_to_obj(frm.doc.dropoff_scheduled_end);

            if (end <= start) {
                frappe.msgprint(__('Scheduled End must be after Scheduled Start'));
                frm.set_value('dropoff_scheduled_end', '');
            }
        }
    }
});

// Phase 8C: Auto-populate Expected Items from linked POS Orders
frappe.ui.form.on('Dropoff Order', {
    pos_order: function(frm, cdt, cdn) {
        // When a POS Order is added/changed, populate expected items
        let row = locals[cdt][cdn];
        if (row.pos_order) {
            populate_expected_items_from_orders(frm);
        }
    }
});

function populate_expected_items_from_orders(frm) {
    if (!frm.doc.orders || frm.doc.orders.length === 0) {
        return;
    }

    // Collect all order names
    let order_names = frm.doc.orders
        .map(row => row.pos_order)
        .filter(order => order); // Remove empty values

    if (order_names.length === 0) {
        return;
    }

    // Fetch items from all orders using our secure API
    frappe.call({
        method: 'scrap_metal_suite.api.v1.dropoff.get_items_from_orders',
        args: {
            order_names: order_names
        },
        error: function(r) {
            console.error('Failed to fetch items from orders:', r);
            // Don't show error to user - they can still manually add items
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                // Get existing items to avoid duplicates
                let existing_items = frm.doc.expected_items.map(row => row.item);

                // Track items we've added (for duplicates across orders)
                let added_items = new Set(existing_items);

                // Add unique items
                r.message.forEach(item => {
                    if (!added_items.has(item.item_code)) {
                        let child = frm.add_child('expected_items');
                        child.item = item.item_code;
                        child.item_name = item.item_name;
                        // indicated_weight left empty for user to fill

                        added_items.add(item.item_code);
                    }
                });

                frm.refresh_field('expected_items');

                if (r.message.length > existing_items.length) {
                    frappe.show_alert({
                        message: __('Expected items populated from orders'),
                        indicator: 'green'
                    });
                }
            }
        }
    });
}
