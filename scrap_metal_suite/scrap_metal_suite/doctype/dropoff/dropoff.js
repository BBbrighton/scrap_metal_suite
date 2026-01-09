frappe.ui.form.on('Dropoff', {
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
        populate_expected_items_from_orders(frm);
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
