// Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Cargo Registration', {
	onload: function(frm){
		
		if(!frm.doc.posting_date) {
			frm.set_value('posting_date', frappe.datetime.nowdate());
			frm.set_df_property('posting_date', 'read_only', 1);
			frm.refresh_field('posting_date')
		}else{
			frm.set_df_property('posting_date', 'read_only', 1);
			frm.refresh_field('posting_date')
		}
	},
	refresh: function(frm){
		frm.doc.cargo_details.forEach(function(row) {
			if (row.creation) {
				row.cargo_id = row.name;
				frm.set_df_property('cargo_details','cargo_id', 'read_only', 1);
				frm.refresh_field('cargo_details');
			}
		});
		if (frm.doc.docstatus !== 2) {
			frm.add_custom_button(__("Create Sales Invoice"), function () {
				frm.events.create_invoice(frm);
			}, __("Create"));
		}
		// frm.add_custom_button(__('Manifest'), function() {
			// 	fetchManifestData();
			// });
		},
	setup: function(frm,cdt,cdn){
		frm.set_query("service_item", "cargo_details", function (doc, cdt, cdn) {
			return {
				filters: {
					item_group: "Services",
				}
			};
		});
		cargo_location_city_filter(frm,cdt,cdn);
		cargo_destination_city_filter(frm,cdt,cdn);
	},
	create_invoice: function(frm){
		if (frm.is_dirty()) {
			frappe.throw(__("Please Save First"));
			return;
		}

		// Filter uninvoiced cargo rows
		var uninvoiced = frm.doc.cargo_details.filter(function(row) {
			return !row.invoice;
		});

		if (!uninvoiced.length) {
			frappe.msgprint(__("All cargo rows are already invoiced."));
			return;
		}

		// Build dialog with selectable rows (works on submitted docs)
		var table_html = '<div class="results my-3" style="border: 1px solid #d1d8dd; border-radius: 3px; max-height: 400px; overflow: auto;">';
		table_html += '<div class="list-item list-item--head">';
		table_html += '<div class="list-item__content" style="flex: 0 0 30px;"><input type="checkbox" class="select-all-cargo" checked></div>';
		table_html += '<div class="list-item__content ellipsis"><span class="text-muted">BL Number</span></div>';
		table_html += '<div class="list-item__content ellipsis"><span class="text-muted">Cargo Type</span></div>';
		table_html += '<div class="list-item__content ellipsis"><span class="text-muted">Destination</span></div>';
		table_html += '<div class="list-item__content ellipsis"><span class="text-muted">Weight</span></div>';
		table_html += '<div class="list-item__content ellipsis"><span class="text-muted">Service Item</span></div>';
		table_html += '</div>';

		uninvoiced.forEach(function(row) {
			table_html += '<div class="list-item">';
			table_html += '<div class="list-item__content" style="flex: 0 0 30px;">';
			table_html += '<input type="checkbox" class="cargo-row-check" data-row-name="' + row.name + '" checked>';
			table_html += '</div>';
			table_html += '<div class="list-item__content ellipsis">' + (row.bl_number || '-') + '</div>';
			table_html += '<div class="list-item__content ellipsis">' + (row.cargo_type || '-') + '</div>';
			table_html += '<div class="list-item__content ellipsis">' + (row.cargo_destination_city || row.cargo_destination_country || '-') + '</div>';
			table_html += '<div class="list-item__content ellipsis">' + (row.net_weight || 0) + ' kg</div>';
			table_html += '<div class="list-item__content ellipsis">' + (row.service_item || '-') + '</div>';
			table_html += '</div>';
		});
		table_html += '</div>';

		var dialog = new frappe.ui.Dialog({
			title: __('Select Cargo for Invoice'),
			fields: [
				{ fieldtype: 'HTML', fieldname: 'cargo_rows', options: table_html }
			],
			size: 'large',
			primary_action_label: __('Create Sales Invoice'),
			primary_action: function() {
				var selected = [];
				dialog.$wrapper.find('.cargo-row-check:checked').each(function() {
					selected.push($(this).attr('data-row-name'));
				});
				if (!selected.length) {
					frappe.msgprint(__("Please select at least one cargo row."));
					return;
				}
				var selected_rows = frm.doc.cargo_details.filter(function(r) {
					return selected.includes(r.name);
				});
				frappe.call({
					method: "vsd_fleet_ms.vsd_fleet_ms.doctype.cargo_registration.cargo_registration.create_sales_invoice",
					args: {
						doc: frm.doc,
						rows: selected_rows
					},
					freeze: true,
					freeze_message: __("Creating invoice..."),
					callback: function (data) {
						dialog.hide();
						frappe.set_route('Form', data.message.doctype, data.message.name);
					}
				});
			}
		});

		// Select all checkbox
		dialog.$wrapper.find('.select-all-cargo').on('change', function() {
			var checked = $(this).prop('checked');
			dialog.$wrapper.find('.cargo-row-check').prop('checked', checked);
		});

		dialog.show();
	},
});

frappe.ui.form.on('Cargo Detail', {
	form_render: function (frm, cdt, cdn) {
		const container = document.querySelector('[data-fieldname="assign_manifest"]');

		if (container) {
		// Find the button element within the container
		const button = container.querySelector('button');

		// Override the entire class of the button with the new class
		if (button) {
			button.className = 'btn btn-xs btn-default bold btn-primary';
		}
		}
	},
	loading_date: function(frm, cdt, cdn){
		var row = locals[cdt][cdn];
		if (row.loading_date > row.expected_offloading_date){
			frappe.msgprint("Expected Loading Date cannot be greater than Expected Offloading Date")
			row.loading_date = ''
			frm.refresh_field("cargo_details")
		}
	},
	net_weight: function(frm, cdt, cdn){
		var row = locals[cdt][cdn];
		console.log("hi");
		
		// Convert kg to tonnes (1 tonne = 1000 kg)
		if (row.net_weight) {
			row.net_weight_tonne = row.net_weight / 1000;
		} else {
			row.net_weight_tonne = 0;
		}

		// Refresh the field in the child table
		frm.refresh_field('cargo_details');
	},
	expected_offloading_date: function(frm, cdt, cdn){
		var row = locals[cdt][cdn];
		if (row.expected_offloading_date < row.loading_date){
			frappe.msgprint("Expected Offloading Date cannot be greater than Expected Loading Date")
			row.expected_offloading_date = ''
			frm.refresh_field("cargo_details")
		}
	},
	cargo_location_country: function(frm,cdt,cdn){
		cargo_location_city_filter(frm,cdt,cdn);
	},
	cargo_destination_country: function(frm,cdt,cdn){
		cargo_destination_city_filter(frm,cdt,cdn);
	},
	assign_manifest: function(frm,cdt,cdn){
		var row = locals[cdt][cdn];
		var filters = {
			docstatus:0,
			route: row.cargo_route

		}

    frappe.call({
        method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.manifest.manifest.get_manifests',
		args: {
			filter:filters
		},
        callback: function(response) {
            if (response.message) {
                // Create a dialog and set its content to the table of manifest data
                var dialog = new frappe.ui.Dialog({
                    title: 'Manifest Table',
                    fields: [
						{
                        fieldtype: 'HTML',
                        fieldname: 'manifest_table'
                    },
				],
				primary_action_label: 'Create Manifest',
				primary_action(values) {
					var args_array = {
						"cargo_id":row.name,
						"bl_number":row.bl_number,
						"cargo_route": row.cargo_route,
						"cargo_type":row.cargo_type,
						"number_of_package":row.number_of_packages,
						"weight":row.net_weight,
						"expected_loading_date":row.loading_date,
						"expected_offloading_date":row.expected_offloading_date,
						"customer_name":frm.doc.customer,
						"cargo_destination_country":row.cargo_destination_country,
						"cargo_destination_city":row.cargo_destination_city,
						"container_size":row.container_size,
						"seal_number":row.seal_number,
						"container_number":row.container_number,
						"cargo_loading_city":row.cargo_location_city,
						"cargo_location_country":row.cargo_location_country,
						"parent_doctype_name":cur_frm.doc.name
					}
					handle_create_manifest_Click(args_array);
					// Close the dialog
					dialog.hide();
				},
				secondary_action_label: 'Assign to Manifest',
				secondary_action(values) {
					var selectedRow = dialog.body.querySelector('input[type="checkbox"]:checked');
					if (selectedRow) {
						var manifestName = selectedRow.getAttribute('data-item-name');
						// Perform the desired action with the selected item
						// Example: Call a function with the selected item name
						var args_array = {
							"manifest":manifestName,
							"cargo_id":row.name,
							"bl_number":row.bl_number,
							"cargo_route": row.cargo_route,
							"cargo_type":row.cargo_type,
							"number_of_package":row.number_of_packages,
							"weight":row.net_weight,
							"expected_loading_date":row.loading_date,
							"expected_offloading_date":row.expected_offloading_date,
							"customer_name":frm.doc.customer,
							"cargo_destination_country":row.cargo_destination_country,
							"cargo_destination_city":row.cargo_destination_city,
							"container_size":row.container_size,
							"seal_number":row.seal_number,
							"container_number":row.container_number,
							"cargo_loading_city":row.cargo_location_city,
							"cargo_location_country":row.cargo_location_country,
							"parent_doctype_name":cur_frm.doc.name
						}
						handle_Assign_Button_Click(args_array);
						// Close the dialog
						dialog.hide();
					}
				}
                });

                // Generate the HTML table markup using the response data
                var tableHtml = generateManifestTable(response.message);

                // Set the table HTML in the dialog's field
                dialog.fields_dict.manifest_table.$wrapper.html(tableHtml);

				// Attach the event handler for checkbox change using event delegation
				dialog.fields_dict.manifest_table.$wrapper.on('change', 'input.list-row-check', function (event) {
					handleCheckboxChange(event.target);
				});

                // Show the dialog
                dialog.show();
            }
        }
    });
}
});

function generateManifestTable(data) {
    var tableHtml = '<div class="results my-3" style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;">';
    tableHtml += '<div class="list-item list-item--head">';
    tableHtml += '<div class="list-item__content" style="flex: 0 0 10px;">';
    tableHtml += '<input type="checkbox" class="list-row-check" data-item-name="undefined" disabled>';
    tableHtml += '</div>';
    tableHtml += '<div class="list-item__content ellipsis">';
    tableHtml += '<span class="ellipsis text-muted" title="Name">Name</span>';
    tableHtml += '</div>';
    // tableHtml += '<div class="list-item__content ellipsis">';
    // tableHtml += '<span class="ellipsis text-muted" title="Route">Route</span>';
    // tableHtml += '</div>';
    tableHtml += '<div class="list-item__content ellipsis">';
    tableHtml += '<span class="ellipsis text-muted" title="Truck">Truck</span>';
    tableHtml += '</div>';
    tableHtml += '<div class="list-item__content ellipsis">';
    tableHtml += '<span class="ellipsis text-muted" title="Driver">Driver</span>';
    tableHtml += '</div>';
    tableHtml += '</div>';

	if (data.length > 0){
		for (var i = 0; i < data.length; i++) {
			tableHtml += '<div class="list-item">';
			tableHtml += '<div class="list-item__content" style="flex: 0 0 10px;">';
			tableHtml += '<input type="checkbox" class="list-row-check" data-item-name="' + data[i].name + '">';
			tableHtml += '</div>';
			tableHtml += '<div class="list-item__content ellipsis">';
			tableHtml += '<span class="ellipsis text-muted" title="' + data[i].name + '">' + data[i].name + '</span>';
			tableHtml += '</div>';
			// tableHtml += '<div class="list-item__content ellipsis">';
			// tableHtml += '<span class="ellipsis text-muted" title="' + data[i].route + '">' + data[i].route + '</span>';
			// tableHtml += '</div>';
			tableHtml += '<div class="list-item__content ellipsis">';
			tableHtml += '<span class="ellipsis text-muted" title="' + data[i].truck_license_plate_no + '">' + data[i].truck_license_plate_no + '</span>';
			tableHtml += '</div>';
			tableHtml += '<div class="list-item__content ellipsis">';
			tableHtml += '<span class="ellipsis text-muted" title="' + data[i].driver_name + '">' + data[i].driver_name + '</span>';
			tableHtml += '</div>';
			tableHtml += '</div>';
		}
	}else{
		tableHtml += '<div class="list-item"><br>';
		tableHtml += '<div class="list-item__content ellipsis">';
		tableHtml += '<h2 class="ellipsis text-muted" title="undefined"> <br></h2';
		tableHtml += '</div>';
		tableHtml += '<div class="list-item__content ellipsis">';
		tableHtml += '<h2 class="ellipsis text-muted" title="undefined"> <br></h2';
		tableHtml += '</div>';
		tableHtml += '<div class="list-item__content ellipsis">';
		tableHtml += '<h3 class="ellipsis text-center text-info" title="undefined"> No Available Manifest with that Trip Route that<br> you can assign to </h3';
		tableHtml += '</div>';
		tableHtml += '</div>';
	}

    tableHtml += '</div>';
    return tableHtml;
}
function handle_Assign_Button_Click(args_array) {
	
	// console.log(args_array.manifest)
    frappe.call({
		args: {
			args_array:args_array
		},
		method: "vsd_fleet_ms.vsd_fleet_ms.doctype.manifest.manifest.add_to_existing_manifest",
		callback: function (r) {
			if (r.message){
				var doc = frappe.model.sync(r.message)[0];
			frappe.set_route("Form", doc.doctype, doc.name);
			}
		}
	})
}
function handle_create_manifest_Click(args_array) {
	
	// console.log(args_array.manifest)
    frappe.call({
		args: {
			args_array:args_array
		},
		method: "vsd_fleet_ms.vsd_fleet_ms.doctype.manifest.manifest.create_new_manifest",
		callback: function (r) {
			if (r.message){
				var doc = frappe.model.sync(r.message)[0];
			frappe.set_route("Form", doc.doctype, doc.name);
			}
		}
	})
}
var selectedCheckbox = null;

function handleCheckboxChange(checkbox) {
	if (checkbox.checked) {
		if (selectedCheckbox && selectedCheckbox !== checkbox) {
			selectedCheckbox.checked = false;
		}
		selectedCheckbox = checkbox;
	} else {
		selectedCheckbox = null;
	}
}

function cargo_location_city_filter(frm,cdt,cdn){
	frm.set_query("cargo_location_city","cargo_details",  function (doc,cdt,cdn) {
		const row = locals[cdt][cdn];
		return {
			filters: {
				country: row.cargo_location_country,
			}
		};
	});
}
function cargo_destination_city_filter(frm,cdt,cdn){
	frm.set_query("cargo_destination_city","cargo_details",  function (doc,cdt,cdn) {
		const row = locals[cdt][cdn];
		return {
			filters: {
				country: row.cargo_destination_country,
			}
		};
	});
}

frappe.ui.form.on('Requested Fund Details', {
    create_ledger_entry: function (frm, cdt, cdn) {
        if (frm.is_dirty()) {
            frappe.throw(__("Plase Save First"));
            return;
        }
        const row = locals[cdt][cdn];
        if (row.ledger_entry) return;
        frappe.call({
            method: "vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_trip_expense_ledger_entry",
            args: {
                doc: frm.doc,
                row: row
            },
            callback: function (data) {
                frm.reload_doc();
                const new_url = `${window.location.origin}/app/ledger-entry/${data.message.name}`;
                window.open(new_url, '_blank');
            }
        });
    }
});
