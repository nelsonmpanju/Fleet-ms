// Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Trips', {
	refresh: function (frm) {
		render_fund_summaries(frm);
		render_fuel_summary(frm);
		render_location_map(frm);
		toggle_fuel_columns(frm);

		// --- Action Buttons ---
		if (frm.doc.docstatus === 1 && !frm.doc.trip_completed && frm.doc.trip_status !== "Breakdown") {
			// Start Trip: Pending -> In Transit
			if (frm.doc.trip_status === "Pending") {
				frm.add_custom_button(__("Start Trip"), function () {
					frappe.call({
						method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.start_trip',
						args: { docname: frm.doc.name },
						callback: function (r) {
							if (r.message) {
								frm.reload_doc();
								frappe.msgprint(__("Trip started successfully"));
							}
						}
					});
				}, __('Actions'));
			}

			// Complete Trip: In Transit -> Completed
			if (frm.doc.trip_status === "In Transit") {
				frm.add_custom_button(__("Complete Trip"), function () {
					frappe.confirm(__("Are you sure you want to complete this trip?"), function () {
						frappe.call({
							method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.complete_trip',
							args: { docname: frm.doc.name },
							callback: function (r) {
								if (r.message) {
									frm.reload_doc();
									frappe.msgprint(__("Trip completed successfully"));
								}
							}
						});
					});
				}, __('Actions'));
			}
		}

		// Create Breakdown Entry (only before submit, when Pending or In Transit)
		if (!frm.doc.trip_completed && (frm.doc.trip_status === "Pending" || frm.doc.trip_status === "In Transit") && frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Create Breakdown Entry'), function () {
				frappe.confirm(__('Do you want to create a breakdown entry?'), function () {
					frappe.call({
						method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_breakdown',
						args: { docname: frm.doc.name },
						callback: function (r) {
							if (r.message) {
								frm.reload_doc();
								frappe.msgprint(__("Breakdown entry created"));
							}
						}
					});
				});
			}, __('Actions'));
		}

		// Allocate New Vehicle Trip (on breakdown, not yet re-assigned)
		if (!frm.doc.resumption_trip && frm.doc.trip_status === "Breakdown" && frm.doc.status !== "Re-Assigned") {
			frm.add_custom_button(__('Allocate New Vehicle Trip'), function () {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_resumption_trip',
					args: { docname: frm.doc.name },
					callback: function (r) {
						if (r.message) {
							var doc = frappe.model.sync(r.message)[0];
							frappe.set_route("Form", doc.doctype, doc.name);
						}
					}
				});
			}, __('Actions'));
		}
	},

	setup: function (frm) {
		// Color-code request_status and fuel status in child tables
		$(frm.wrapper).on("grid-row-render", function (e, grid_row) {
			var status_field = grid_row.doc.request_status || grid_row.doc.status;
			var field_name = grid_row.doc.request_status ? "request_status" : "status";

			if (status_field === "Requested" || status_field === "Open") {
				$(grid_row.columns[field_name]).css({"font-weight": "bold", "color": "blue"});
			} else if (status_field === "Approved") {
				$(grid_row.columns[field_name]).css({"font-weight": "bold", "color": "green"});
			} else if (status_field === "Rejected") {
				$(grid_row.columns[field_name]).css({"font-weight": "bold", "color": "red"});
			}
		});
	},

	fuel_source_type: function (frm) {
		frm.refresh_fields();
	},

	reduce_stock: function (frm) {
		if (frm.doc.stock_out_entry) return;
		frappe.call({
			method: "vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_stock_out_entry",
			args: {
				doc: frm.doc,
				fuel_stock_out: frm.doc.fuel_stock_out
			},
			callback: function (data) {
				frappe.set_route('Form', data.message.doctype, data.message.name);
			}
		});
	},

	route: function (frm) {
		if (!frm.doc.route) return;
		frappe.model.with_doc('Trip Routes', frm.doc.route, function () {
			var reference_route = frappe.model.get_doc('Trip Routes', frm.doc.route);
			frm.clear_table('main_route_steps');
			reference_route.trip_steps.forEach(function (row) {
				var new_row = frm.add_child('main_route_steps');
				new_row.location = row.location;
				new_row.distance = row.distance;
				new_row.fuel_consumption_qty = row.fuel_consumption_qty;
				new_row.location_type = row.location_type;
			});
			frm.refresh_field('main_route_steps');

			frm.clear_table('requested_fund_accounts_table');
			reference_route.fixed_expenses.forEach(function (row) {
				frappe.model.with_doc('Fixed Expenses', row.expense, function () {
					var fixed_expense_doc = frappe.model.get_doc("Fixed Expenses", row.expense);
					var new_row = frm.add_child('requested_fund_accounts_table');
					new_row.requested_date = frappe.datetime.nowdate();
					new_row.request_amount = row.amount;
					new_row.request_currency = row.currency;
					new_row.request_status = "Requested";
					new_row.expense_type = row.expense;
					new_row.expense_account = fixed_expense_doc.expense_account;
					new_row.payable_account = fixed_expense_doc.cash_bank_account;
					new_row.party_type = row.party_type;
					frm.refresh_field('requested_fund_accounts_table');
				});
			});
		});
	},

	date_of_departure_from_border: function (frm) {
		calculate_border_days(frm);
	},

	arrival_date_at_border: function (frm) {
		calculate_border_days(frm);
	}
});

// --- Truck Trip Location Update child table ---
frappe.ui.form.on('Truck Trip Location Update', {
	view_on_map: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.latitude && row.longitude) {
			var url = 'https://www.google.com/maps/search/?api=1&query=' + row.latitude + ',' + row.longitude;
			window.open(url, '_blank');
		} else {
			frappe.msgprint(__("Latitude and Longitude are required to view on map"));
		}
	}
});

// --- Fuel Requests Table child table ---
frappe.ui.form.on('Fuel Requests Table', {
	quantity: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.cost_per_litre) {
			row.total_cost = row.quantity * row.cost_per_litre;
			frm.refresh_field("fuel_request_history");
		}
	},
	cost_per_litre: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.quantity) {
			row.total_cost = row.quantity * row.cost_per_litre;
			frm.refresh_field("fuel_request_history");
		}
	}
});

// --- Requested Fund Details child table ---
// Ledger Entry is now auto-created on approval in Requested Payment.
// Keep a manual fallback for edge cases where auto-creation may have failed.
frappe.ui.form.on('Requested Fund Details', {
	create_ledger_entry: function (frm, cdt, cdn) {
		if (frm.is_dirty()) {
			frappe.throw(__("Please Save First"));
			return;
		}
		var row = locals[cdt][cdn];
		if (row.ledger_entry) {
			frappe.msgprint(__("Ledger Entry already exists: {0}", [row.ledger_entry]));
			return;
		}
		if (row.request_status !== "Approved") {
			frappe.msgprint(__("Request must be approved first."));
			return;
		}
		frappe.call({
			method: "vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_trip_expense_ledger_entry",
			args: {
				doc: frm.doc,
				row: row
			},
			callback: function (data) {
				frm.reload_doc();
				var new_url = window.location.origin + '/app/ledger-entry/' + data.message.name;
				window.open(new_url, '_blank');
			}
		});
	}
});

// --- Helper Functions ---

function calculate_border_days(frm) {
	if (frm.doc.date_of_departure_from_border && frm.doc.arrival_date_at_border) {
		var date1 = frappe.datetime.str_to_obj(frm.doc.date_of_departure_from_border);
		var date2 = frappe.datetime.str_to_obj(frm.doc.arrival_date_at_border);
		var difference_days = Math.floor((date1 - date2) / (1000 * 60 * 60 * 24));
		frm.set_value("total_days_at_the_border", difference_days);
	}
}

function render_fund_summaries(frm) {
	var totals = { Requested: { TZS: 0, USD: 0 }, Approved: { TZS: 0, USD: 0 }, Rejected: { TZS: 0, USD: 0 } };

	(frm.doc.requested_fund_accounts_table || []).forEach(function (row) {
		var key = row.request_status;
		var cur = row.request_currency;
		if (totals[key] && (cur === "TZS" || cur === "USD")) {
			totals[key][cur] += row.request_amount || 0;
		}
	});

	var html_field = frm.get_field("html");
	if (html_field) {
		html_field.wrapper.innerHTML = '<p class="text-muted small">Total Amount Requested</p><b>USD '
			+ totals.Requested.USD.toLocaleString() + ' <br> TZS ' + totals.Requested.TZS.toLocaleString() + '</b>';
	}
	var html2_field = frm.get_field("html2");
	if (html2_field) {
		html2_field.wrapper.innerHTML = '<p class="text-muted small">Total Amount Approved</p><b>USD '
			+ totals.Approved.USD.toLocaleString() + ' <br> TZS ' + totals.Approved.TZS.toLocaleString() + '</b>';
	}
	var html3_field = frm.get_field("html3");
	if (html3_field) {
		html3_field.wrapper.innerHTML = '<p class="text-muted small">Total Amount Rejected</p><b>USD '
			+ totals.Rejected.USD.toLocaleString() + ' <br> TZS ' + totals.Rejected.TZS.toLocaleString() + '</b>';
	}
}

function render_fuel_summary(frm) {
	var approved = 0, requested = 0, rejected = 0;
	(frm.doc.fuel_request_history || []).forEach(function (row) {
		if (row.status === "Approved") approved += row.quantity || 0;
		if (row.status === "Requested") requested += row.quantity || 0;
		if (row.status === "Rejected") rejected += row.quantity || 0;
	});
	var html4_field = frm.get_field("html4");
	if (html4_field) {
		html4_field.wrapper.innerHTML =
			'<p class="text-muted small">Total Fuel Requested: <b>' + requested.toLocaleString() + ' L</b></p>'
			+ '<p class="text-muted small">Total Fuel Approved: <b>' + approved.toLocaleString() + ' L</b></p>'
			+ '<p class="text-muted small">Total Fuel Rejected: <b>' + rejected.toLocaleString() + ' L</b></p>';
	}
}

function render_location_map(frm) {
	var map_field = frm.get_field("location_map");
	if (!map_field) return;

	var locations = (frm.doc.location_update || []).filter(function (row) {
		return row.latitude && row.longitude;
	});

	if (!locations.length) {
		map_field.wrapper.innerHTML = '<p class="text-muted small">No location data with coordinates available. Add location updates with latitude and longitude to see the map.</p>';
		return;
	}

	// Build map HTML using Leaflet (OpenStreetMap)
	var map_id = 'trip-location-map-' + frm.doc.name;
	map_field.wrapper.innerHTML = '<div id="' + map_id + '" style="height: 400px; width: 100%; border-radius: 8px; border: 1px solid var(--border-color);"></div>';

	// Load Leaflet CSS and JS if not already loaded
	if (!window.L) {
		var link = document.createElement('link');
		link.rel = 'stylesheet';
		link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
		document.head.appendChild(link);

		var script = document.createElement('script');
		script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
		script.onload = function () {
			_draw_map(map_id, locations);
		};
		document.head.appendChild(script);
	} else {
		setTimeout(function () {
			_draw_map(map_id, locations);
		}, 100);
	}
}


function _draw_map(map_id, locations) {
	var el = document.getElementById(map_id);
	if (!el || !window.L) return;

	var map = L.map(map_id);
	L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
		attribution: '&copy; OpenStreetMap contributors'
	}).addTo(map);

	var bounds = [];
	var polyline_points = [];

	locations.forEach(function (loc, idx) {
		var lat = parseFloat(loc.latitude);
		var lng = parseFloat(loc.longitude);
		if (isNaN(lat) || isNaN(lng)) return;

		var point = [lat, lng];
		bounds.push(point);
		polyline_points.push(point);

		var label = loc.location || ('Point ' + (idx + 1));
		var time_str = loc.timestamp ? frappe.datetime.str_to_user(loc.timestamp) : '';
		var popup = '<b>' + label + '</b>';
		if (time_str) popup += '<br>' + time_str;
		if (loc.comment) popup += '<br><i>' + loc.comment + '</i>';

		L.marker(point).addTo(map).bindPopup(popup);
	});

	// Draw route line
	if (polyline_points.length > 1) {
		L.polyline(polyline_points, { color: '#2490EF', weight: 3 }).addTo(map);
	}

	if (bounds.length) {
		map.fitBounds(bounds, { padding: [30, 30] });
	}
}
