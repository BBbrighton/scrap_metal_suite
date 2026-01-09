frappe.listview_settings['Dropoff'] = {
    add_fields: ['status', 'verification_status'],
    get_indicator: function(doc) {
        // Phase 8A: Simplified status flow (5 statuses)
        const status_map = {
            'Draft': ['Draft', 'grey', 'status,=,Draft'],
            'Scheduled': ['Scheduled', 'blue', 'status,=,Scheduled'],
            'In Progress': ['In Progress', 'orange', 'status,=,In Progress'],
            'Completed': ['Completed', 'green', 'status,=,Completed'],
            'Cancelled': ['Cancelled', 'darkgrey', 'status,=,Cancelled']
        };
        return status_map[doc.status] || ['Unknown', 'grey'];
    }
};
