frappe.listview_settings['Dropoff'] = {
    add_fields: ['status'],
    get_indicator: function(doc) {
        const status_map = {
            'Draft': ['Draft', 'grey', 'status,=,Draft'],
            'Scheduled': ['Scheduled', 'blue', 'status,=,Scheduled'],
            'Weighing': ['Weighing', 'orange', 'status,=,Weighing'],
            'Unloading': ['Unloading', 'yellow', 'status,=,Unloading'],
            'Verified': ['Verified', 'green', 'status,=,Verified'],
            'Needs Attention': ['Needs Attention', 'red', 'status,=,Needs Attention'],
            'Closed': ['Closed', 'purple', 'status,=,Closed'],
            'Cancelled': ['Cancelled', 'darkgrey', 'status,=,Cancelled']
        };
        return status_map[doc.status] || ['Unknown', 'grey'];
    }
};
