// Copyright (c) 2026, Scrap Metal Suite and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scrap Weight Container", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		const status = frm.doc.status;

		if (status === "Active") {
			// Reweigh
			frm.add_custom_button(__("Reweigh"), () => {
				frappe.prompt(
					[
						{
							fieldname: "new_weight",
							label: __("New Net Weight (kg)"),
							fieldtype: "Float",
							reqd: 1,
						},
						{
							fieldname: "reason",
							label: __("Reason"),
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					(values) => {
						frappe.call({
							method: "scrap_metal_suite.api.v1.dropoff.reweigh_container",
							args: {
								container: frm.doc.name,
								net_weight: values.new_weight,
								reason: values.reason,
							},
							callback: () => frm.reload_doc(),
						});
					},
					__("Reweigh Container"),
					__("Save")
				);
			});

			// Void
			frm.add_custom_button(__("Void"), () => {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							label: __("Reason"),
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					(values) => {
						frappe.call({
							method: "scrap_metal_suite.api.v1.dropoff.void_container",
							args: {
								container: frm.doc.name,
								reason: values.reason,
							},
							callback: () => frm.reload_doc(),
						});
					},
					__("Void Container"),
					__("Confirm")
				);
			});

			// Print Sticker (the container has no thermal — the per-Dropoff
			// thermal receipt is on the Scrap Weight document, not on the
			// container; see DROPOFF_CONTAINER_REDESIGN.md §14.14).
			frm.add_custom_button(
				__("Print Sticker"),
				() => {
					const url =
						"/printview?doctype=Scrap%20Weight%20Container" +
						"&name=" +
						encodeURIComponent(frm.doc.name) +
						"&format=Scrap%20Weight%20Container%20Sticker" +
						"&no_letterhead=1";
					window.open(url, "_blank");
				},
				__("Print")
			);
		}

		// Grade-mix deviation moved to the Dropoff level (Wave 9). Containers
		// are pure measurement records; deviation reconciliation happens once
		// at completion, on the Dropoff form.
	},
});
