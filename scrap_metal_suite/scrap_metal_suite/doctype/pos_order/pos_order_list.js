frappe.listview_settings['POS Order'] = {
    add_fields: ['status'],
    get_indicator: function(doc) {
        const status_map = {
            'Pending': ['Pending', 'grey', 'status,=,Pending'],
            'Processing': ['Processing', 'orange', 'status,=,Processing'],
            'Processed': ['Processed', 'green', 'status,=,Processed'],
            'Cancelled': ['Cancelled', 'red', 'status,=,Cancelled']
        };
        return status_map[doc.status] || ['Unknown', 'grey'];
    }
};
