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
