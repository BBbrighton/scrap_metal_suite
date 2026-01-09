// Calendar configuration for Dropoff DocType
frappe.views.calendar["Dropoff"] = {
	field_map: {
		start: "dropoff_scheduled_start",
		end: "dropoff_scheduled_end",
		id: "name",
		title: "name",
		status: "status",
		allDay: false
	},
	get_events_method: "scrap_metal_suite.scrap_metal_suite.doctype.dropoff.dropoff.get_events"
};
