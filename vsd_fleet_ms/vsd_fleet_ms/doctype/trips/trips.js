// Copyright (c) 2023, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Trips', {
	refresh: function (frm) {
		render_fund_summaries(frm);
		render_fuel_summary(frm);
		render_location_map(frm);

		// --- Trip Status Indicator ---
		var status_color = { "Pending": "orange", "In Transit": "blue", "Completed": "green", "Breakdown": "red" };
		if (frm.doc.trip_status) {
			frm.page.set_indicator(__(frm.doc.trip_status), status_color[frm.doc.trip_status] || "grey");
		}

		// --- Workflow "Next Steps" Dashboard ---
		if (frm.doc.transporter_type === "In House" && frm.doc.docstatus !== 2) {
			if (!frm.doc.fuel_source_type && (frm.doc.fuel_request_history || []).length) {
				frm.dashboard.set_headline_alert(
					__("Please set <b>Fuel Source</b> on the Fuel tab to enable fuel workflow actions."),
					"orange"
				);
			} else {
				let pending_fuel = (frm.doc.fuel_request_history || []).filter(
					r => r.status === "Open" || r.status === "Requested"
				).length;
				let approved_fuel_unpaid = (frm.doc.fuel_request_history || []).filter(
					r => r.status === "Approved" && !r.ledger_entry
				).length;
				let pending_expenses = (frm.doc.requested_fund_accounts_table || []).filter(
					r => ["Requested", "Recommended", "Pre-Approved"].includes(r.request_status)
				).length;
				let unpaid_expenses = (frm.doc.requested_fund_accounts_table || []).filter(
					r => !r.journal_entry && (
						r.request_status === "Accounts Approved" ||
						(r.request_status === "Approved" && r.expense_account && r.payable_account)
					)
				).length;

				let actions = [];
				if (frm.doc.trip_status === "Pending") actions.push(__("Start Trip"));
				if (pending_fuel) actions.push(__(("{0} fuel request(s) to approve"), [pending_fuel]));
				if (approved_fuel_unpaid) {
					if (frm.doc.fuel_source_type === "From Inventory" && !frm.doc.stock_out_entry) {
						actions.push(__("Stock deduction pending"));
					} else if (frm.doc.fuel_source_type === "Cash Purchase") {
						actions.push(__(("{0} fuel payment(s) to create"), [approved_fuel_unpaid]));
					}
				}
				if (pending_expenses) actions.push(__(("{0} expense(s) to approve"), [pending_expenses]));
				if (unpaid_expenses) actions.push(__(("{0} payment(s) to make"), [unpaid_expenses]));

				if (actions.length) {
					frm.dashboard.set_headline_alert(
						'<span style="font-weight:500">' + __("Next steps") + ':</span> ' + actions.join(' &middot; '),
						"blue"
					);
				}
			}
		}

		// --- Trip Status Buttons (any non-cancelled trip) ---
		if (frm.doc.docstatus !== 2 && !frm.doc.trip_completed && frm.doc.trip_status !== "Breakdown") {

			// Start Trip: Pending -> In Transit (standalone — always visible)
			if (frm.doc.trip_status === "Pending") {
				frm.add_custom_button(__("Start Trip"), function () {
					frappe.confirm(
						__("Start this trip? The truck will be marked as <b>On Trip</b> and the driver will be marked as unavailable."),
						function () {
							frappe.call({
								method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.start_trip',
								args: { docname: frm.doc.name },
								freeze: true,
								freeze_message: __("Starting trip..."),
								callback: function (r) {
									if (r.message) {
										frm.reload_doc();
										frappe.show_alert({ message: __("Trip started — truck is now On Trip"), indicator: "blue" });
									}
								}
							});
						}
					);
				});
				frm.change_custom_button_type(__("Start Trip"), null, "primary");
			}

			// End Trip: In Transit -> Completed (standalone — always visible)
			if (frm.doc.trip_status === "In Transit") {
				frm.add_custom_button(__("End Trip"), function () {
					frappe.confirm(
						__("Mark trip as <b>Completed</b>? The truck and driver will be released back to Idle/Available."),
						function () {
							frappe.call({
								method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.complete_trip',
								args: { docname: frm.doc.name },
								freeze: true,
								freeze_message: __("Completing trip..."),
								callback: function (r) {
									if (r.message) {
										frm.reload_doc();
										frappe.show_alert({ message: __("Trip completed — truck is now Idle"), indicator: "green" });
									}
								}
							});
						}
					);
				});
				frm.change_custom_button_type(__("End Trip"), null, "primary");
			}

			// Sync GPS — manually fetch latest position for this trip's truck
		if (frm.doc.trip_status === "In Transit" && frm.doc.truck_number) {
			frm.add_custom_button(__("Sync GPS"), function () {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.utils.traccar.sync_vehicle_position',
					args: { truck_name: frm.doc.truck_number },
					freeze: true,
					freeze_message: __("Fetching GPS position..."),
					callback: function (r) {
						if (r.message) {
							frappe.show_alert({
								message: r.message,
								indicator: "blue"
							});
							frm.reload_doc();
						}
					}
				});
			}, __('Actions'));
		}

		// Report Breakdown — kept in Actions group
			frm.add_custom_button(__("Report Breakdown"), function () {
				frappe.confirm(
					__("Report a <b>Breakdown</b>? The truck will be set to Under Maintenance, the driver will be released, and a Trip Breakdown document will be created."),
					function () {
						frappe.call({
							method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_breakdown',
							args: { docname: frm.doc.name },
							freeze: true,
							freeze_message: __("Recording breakdown..."),
							callback: function (r) {
								if (r.message) {
									frappe.show_alert({ message: __("Breakdown recorded — opening Trip Breakdown"), indicator: "red" });
									frappe.set_route("Form", "Trip Breakdown", r.message);
								}
							}
						});
					}
				);
			}, __('Actions'));
		}

		// Allocate New Vehicle Trip (on breakdown, not yet re-assigned)
		if (!frm.doc.resumption_trip && frm.doc.trip_status === "Breakdown" && frm.doc.status !== "Re-Assigned") {
			frm.add_custom_button(__('Allocate New Vehicle Trip'), function () {
				frappe.call({
					method: 'vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_resumption_trip',
					args: { docname: frm.doc.name },
					freeze: true,
					freeze_message: __("Creating resumption trip..."),
					callback: function (r) {
						if (r.message) {
							var doc = frappe.model.sync(r.message)[0];
							frappe.set_route("Form", doc.doctype, doc.name);
						}
					}
				});
			}, __('Actions'));
		}

		// ── Expenses quick-action buttons (In House trips, not cancelled) ────────
		if (frm.doc.transporter_type === "In House" && frm.doc.docstatus !== 2) {

			// Approve Fuel — fuel rows waiting approval (both Cash Purchase and From Inventory)
			const pendingFuel = (frm.doc.fuel_request_history || []).filter(
				r => r.status === "Open" || r.status === "Requested"
			);
			if (pendingFuel.length) {
				frm.add_custom_button(__("Approve Fuel"), function () {
					if (frm.is_dirty()) { frappe.msgprint(__("Please save the form first.")); return; }
					show_approve_fuel_dialog(frm);
				}, __("Expenses"));
			}

			// Reduce Stock — From Inventory: approved fuel rows but stock not yet deducted
			if (frm.doc.fuel_source_type === "From Inventory" && !frm.doc.stock_out_entry) {
				const approvedInventoryFuel = (frm.doc.fuel_request_history || []).filter(
					r => r.status === "Approved"
				);
				if (approvedInventoryFuel.length) {
					frm.add_custom_button(__("Reduce Stock"), function () {
						if (frm.is_dirty()) { frappe.msgprint(__("Please save the form first.")); return; }
						frappe.confirm(
							__("Create a Stock Entry (Material Issue) to deduct <b>{0} litres</b> of fuel from the warehouse?", [frm.doc.fuel_stock_out]),
							function () {
								frappe.call({
									method: "vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_stock_out_entry",
									args: {
										doc: frm.doc,
										fuel_stock_out: frm.doc.fuel_stock_out
									},
									freeze: true,
									freeze_message: __("Creating stock entry..."),
									callback: function (data) {
										frappe.show_alert({ message: __("Stock Entry created"), indicator: "green" });
										frm.reload_doc();
									}
								});
							}
						);
					}, __("Expenses"));
				}
			}

			// Create Fuel Payment — Cash Purchase: approved fuel rows without payment yet
			if (frm.doc.fuel_source_type === "Cash Purchase") {
				const approvedUnpaidFuel = (frm.doc.fuel_request_history || []).filter(
					r => r.status === "Approved" && !r.ledger_entry
				);
				if (approvedUnpaidFuel.length) {
					frm.add_custom_button(__("Create Fuel Payment"), function () {
						if (frm.is_dirty()) { frappe.msgprint(__("Please save the form first.")); return; }
						show_fuel_payment_dialog(frm, approvedUnpaidFuel);
					}, __("Expenses"));
				}
			}

			// Approve Expenses — expense rows waiting manager/accounts approval
			const pendingExp = (frm.doc.requested_fund_accounts_table || []).filter(
				r => ["Requested", "Recommended", "Pre-Approved"].includes(r.request_status)
			);
			if (pendingExp.length) {
				frm.add_custom_button(__("Approve Expenses"), function () {
					if (frm.is_dirty()) { frappe.msgprint(__("Please save the form first.")); return; }
					show_approve_expenses_dialog(frm);
				}, __("Expenses"));
			}

			// Make Payment — Approved or Accounts Approved rows not yet paid
			const payableExp = (frm.doc.requested_fund_accounts_table || []).filter(
				r => !r.journal_entry && (
					r.request_status === "Accounts Approved" ||
					(r.request_status === "Approved" && r.expense_account && r.payable_account)
				)
			);
			if (payableExp.length) {
				frm.add_custom_button(__("Make Payment"), function () {
					if (frm.is_dirty()) { frappe.msgprint(__("Please save the form first.")); return; }
					show_make_payment_dialog(frm);
				}, __("Expenses"));
			}
		}
	},

	setup: function (frm) {
		// Color-code request_status and fuel status in child tables
		var status_colors = {
			"Open": { color: "#7c3aed", bg: "#ede9fe" },
			"Requested": { color: "#2563eb", bg: "#dbeafe" },
			"Recommended": { color: "#0891b2", bg: "#cffafe" },
			"Pre-Approved": { color: "#0891b2", bg: "#cffafe" },
			"Approved": { color: "#059669", bg: "#d1fae5" },
			"Accounts Approved": { color: "#d97706", bg: "#fef3c7" },
			"Paid": { color: "#16a34a", bg: "#bbf7d0" },
			"Rejected": { color: "#dc2626", bg: "#fee2e2" },
			"Accounts Cancelled": { color: "#9ca3af", bg: "#f3f4f6" },
		};
		$(frm.wrapper).on("grid-row-render", function (e, grid_row) {
			var status_field = grid_row.doc.request_status || grid_row.doc.status;
			var field_name = grid_row.doc.request_status ? "request_status" : "status";
			var style = status_colors[status_field];
			if (style && grid_row.columns[field_name]) {
				$(grid_row.columns[field_name]).css({
					"font-weight": "600",
					"color": style.color,
				});
			}
			// Show payment indicator
			if (grid_row.doc.journal_entry && grid_row.columns.journal_entry) {
				$(grid_row.columns.journal_entry).css({ "color": "#16a34a", "font-weight": "600" });
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
	expense_type: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.expense_type) return;
		frappe.db.get_value(
			'Fixed Expenses', row.expense_type,
			['expense_account', 'cash_bank_account', 'currency', 'fixed_value'],
			function (v) {
				if (!v) return;
				if (v.expense_account)   frappe.model.set_value(cdt, cdn, 'expense_account',  v.expense_account);
				if (v.cash_bank_account) frappe.model.set_value(cdt, cdn, 'payable_account',   v.cash_bank_account);
				if (v.currency)          frappe.model.set_value(cdt, cdn, 'request_currency',  v.currency);
				if (v.fixed_value && !row.request_amount)
					frappe.model.set_value(cdt, cdn, 'request_amount', v.fixed_value);
			}
		);
	},

	party: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.party || row.party_type !== 'Supplier') return;
		// Auto-fill payable account from the Supplier record
		frappe.db.get_value('Supplier', row.party, 'payable_account', function (v) {
			if (v && v.payable_account) {
				frappe.model.set_value(cdt, cdn, 'payable_account', v.payable_account);
			}
		});
	},

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
	var totals = {
		Requested: { TZS: 0, USD: 0, count: 0 },
		Approved: { TZS: 0, USD: 0, count: 0 },
		Paid: { TZS: 0, USD: 0, count: 0 },
		Rejected: { TZS: 0, USD: 0, count: 0 },
	};

	(frm.doc.requested_fund_accounts_table || []).forEach(function (row) {
		var key = row.request_status;
		var cur = row.request_currency;
		// Map statuses to summary buckets
		if (key === "Recommended" || key === "Pre-Approved") key = "Requested";
		if (key === "Accounts Approved") key = row.journal_entry ? "Paid" : "Approved";
		if (key === "Approved") key = "Approved";

		if (totals[key] && (cur === "TZS" || cur === "USD")) {
			totals[key][cur] += row.request_amount || 0;
			totals[key].count++;
		}
	});

	function _card(label, icon_color, data) {
		var usd = data.USD.toLocaleString(undefined, { maximumFractionDigits: 0 });
		var tzs = data.TZS.toLocaleString(undefined, { maximumFractionDigits: 0 });
		return '<div style="border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;background:#fff;min-width:160px">'
			+ '<div style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#64748b;margin-bottom:6px">'
			+ '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + icon_color + ';margin-right:6px"></span>'
			+ label + ' <span style="color:#94a3b8">(' + data.count + ')</span></div>'
			+ '<div style="font-size:14px;font-weight:600;color:#1e293b">USD ' + usd + '</div>'
			+ '<div style="font-size:13px;color:#475569">TZS ' + tzs + '</div>'
			+ '</div>';
	}

	var html_field = frm.get_field("html");
	if (html_field) {
		html_field.wrapper.innerHTML = _card("Requested", "#3b82f6", totals.Requested);
	}
	var html2_field = frm.get_field("html2");
	if (html2_field) {
		html2_field.wrapper.innerHTML = _card("Approved", "#f59e0b", totals.Approved);
	}
	var html3_field = frm.get_field("html3");
	if (html3_field) {
		html3_field.wrapper.innerHTML = _card("Paid", "#10b981", totals.Paid)
			+ '<div style="height:8px"></div>'
			+ _card("Rejected", "#ef4444", totals.Rejected);
	}
}

function render_fuel_summary(frm) {
	var totals = {
		Requested: { qty: 0, cost: 0, count: 0 },
		Approved: { qty: 0, cost: 0, count: 0 },
		Paid: { qty: 0, cost: 0, count: 0 },
		Rejected: { qty: 0, cost: 0, count: 0 },
	};

	(frm.doc.fuel_request_history || []).forEach(function (row) {
		var key = row.status;
		if (key === "Open") key = "Requested";
		if (key === "Approved" && row.ledger_entry) key = "Paid";
		if (totals[key]) {
			totals[key].qty += flt(row.quantity);
			totals[key].cost += flt(row.total_cost);
			totals[key].count++;
		}
	});

	function _fuel_card(label, icon_color, data) {
		var qty = data.qty.toLocaleString(undefined, { maximumFractionDigits: 1 });
		var cost = data.cost.toLocaleString(undefined, { maximumFractionDigits: 0 });
		return '<div style="display:inline-block;border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;background:#fff;min-width:140px;margin-right:10px;margin-bottom:8px;vertical-align:top">'
			+ '<div style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#64748b;margin-bottom:4px">'
			+ '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + icon_color + ';margin-right:5px"></span>'
			+ label + ' <span style="color:#94a3b8">(' + data.count + ')</span></div>'
			+ '<div style="font-size:14px;font-weight:600;color:#1e293b">' + qty + ' L</div>'
			+ (data.cost > 0 ? '<div style="font-size:12px;color:#475569">' + cost + '</div>' : '')
			+ '</div>';
	}

	var html4_field = frm.get_field("html4");
	if (html4_field) {
		html4_field.wrapper.innerHTML = '<div style="padding:4px 0">'
			+ _fuel_card("Requested", "#3b82f6", totals.Requested)
			+ _fuel_card("Approved", "#f59e0b", totals.Approved)
			+ _fuel_card("Paid", "#10b981", totals.Paid)
			+ _fuel_card("Rejected", "#ef4444", totals.Rejected)
			+ '</div>';
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


// ── Expense quick-action dialogs ──────────────────────────────────────────────

function show_approve_fuel_dialog(frm) {
	// Fetch fuel rows AND trip-level settings in parallel so we can tell the
	// user exactly what will happen when they approve (stock deduction vs GL booking).
	Promise.all([
		frappe.xcall(
			"vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.get_trip_fuel_rows",
			{ trip_name: frm.doc.name, status_filter: JSON.stringify(["Open", "Requested"]) }
		),
		frappe.xcall(
			"vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.get_fuel_approval_preview",
			{ trip_name: frm.doc.name }
		),
	]).then(([rows, preview]) => {
		if (!rows || !rows.length) {
			frappe.msgprint(__("No pending fuel requests found."));
			return;
		}

		const is_inventory = preview && preview.fuel_source_type === "From Inventory";

		const d = new frappe.ui.Dialog({
			title: __("Approve Fuel Requests"),
			fields: [{ fieldtype: "HTML", fieldname: "fuel_rows_html", options: build_fuel_row_table(rows, preview) }],
			primary_action_label: __("Approve Selected"),
			primary_action() {
				const checked = d.$wrapper.find(".fuel-row-check:checked").map((_, el) => $(el).val()).get();
				if (!checked.length) { frappe.msgprint(__("Please select at least one row.")); return; }
				d.hide();
				frappe.xcall(
					"vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.trip_approve_fuel_rows",
					{ trip_name: frm.doc.name, row_names: JSON.stringify(checked) }
				).then(r => {
					let msg = __("{0} fuel row(s) approved.", [r.approved.length]);
					if (is_inventory) {
						msg += "<br>" + __("Use <b>Expenses → Reduce Stock</b> to create a Stock Entry.");
					} else {
						msg += "<br>" + __("Use <b>Expenses → Create Fuel Payment</b> to create a Payment Entry.");
					}
					if (r.errors.length) msg += "<br><b>" + __("Errors:") + "</b> " + r.errors.join("<br>");
					frappe.msgprint({ title: __("Fuel Approved"), message: msg, indicator: r.errors.length ? "orange" : "green" });
					frm.reload_doc();
				});
			},
		});
		d.show();
		d.$wrapper.on("change", "#fuel-chk-all", function () {
			d.$wrapper.find(".fuel-row-check").prop("checked", this.checked);
		});
	});
}

function show_approve_expenses_dialog(frm) {
	frappe.xcall(
		"vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.get_trip_expense_rows",
		{ trip_name: frm.doc.name, status_filter: JSON.stringify(["Requested", "Recommended", "Pre-Approved"]) }
	).then(rows => {
		if (!rows || !rows.length) {
			frappe.msgprint(__("No pending expense requests found."));
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("Approve Expenses"),
			fields: [{ fieldtype: "HTML", fieldname: "exp_rows_html", options: build_expense_row_table(rows, true) }],
			primary_action_label: __("Approve Selected"),
			primary_action() {
				const checked = d.$wrapper.find(".exp-row-check:checked").map((_, el) => $(el).val()).get();
				if (!checked.length) { frappe.msgprint(__("Please select at least one row.")); return; }
				d.hide();
				frappe.xcall(
					"vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.trip_approve_expense_rows",
					{ trip_name: frm.doc.name, row_names: JSON.stringify(checked) }
				).then(r => {
					frappe.show_alert({
						message: __("{0} expense(s) approved.", [r.approved.length])
							+ (r.errors.length ? "\n" + r.errors.join("\n") : ""),
						indicator: r.errors.length ? "orange" : "green"
					});
					frm.reload_doc();
				});
			}
		});
		d.show();
		d.$wrapper.on("change", "#exp-chk-all", function () {
			d.$wrapper.find(".exp-row-check").prop("checked", this.checked);
		});
	});
}

function show_make_payment_dialog(frm) {
	frappe.xcall(
		"vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.get_trip_expense_rows",
		{ trip_name: frm.doc.name, status_filter: JSON.stringify(["Approved", "Accounts Approved"]) }
	).then(allRows => {
		const rows = (allRows || []).filter(r => !r.journal_entry && (
			r.request_status === "Accounts Approved" ||
			(r.request_status === "Approved" && r.expense_account && r.payable_account)
		));
		if (!rows.length) {
			frappe.msgprint(__("No payable expenses found. Rows must be Approved (with accounts set) or Accounts Approved."));
			return;
		}

		// Calculate total
		var total = {};
		rows.forEach(r => {
			var cur = r.request_currency || "TZS";
			total[cur] = (total[cur] || 0) + flt(r.request_amount);
		});
		var total_str = Object.keys(total).map(c => c + " " + total[c].toLocaleString(undefined, {maximumFractionDigits: 0})).join(" + ");

		const d = new frappe.ui.Dialog({
			title: __("Create Expense Payment Entry"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "info_banner",
					options: '<div class="alert alert-info" style="font-size:12px;padding:8px 12px;margin-bottom:10px">'
						+ __("A Payment Entry will be created for each selected expense. Total: <b>{0}</b>", [total_str])
						+ '<br>' + __("Rows marked <b>Approved</b> will have accounts approval applied automatically.")
						+ '</div>',
				},
				{
					fieldtype: "Link",
					fieldname: "cash_bank_account",
					label: __("Cash / Bank Account"),
					options: "Account",
					reqd: 1,
					get_query: () => ({ filters: { account_sub_type: ["in", ["Cash", "Bank"]], is_group: 0 } }),
				},
				{
					fieldtype: "Select",
					fieldname: "mode_of_payment",
					label: __("Mode of Payment"),
					options: "Cash\nBank Transfer\nCheque\nMobile Money",
					default: "Cash",
				},
				{ fieldtype: "HTML", fieldname: "exp_rows_html", options: build_payment_row_table(rows) },
			],
			primary_action_label: __("Create Payment Entry"),
			primary_action(values) {
				if (!values.cash_bank_account) { frappe.msgprint(__("Please select a Cash / Bank Account.")); return; }
				const checked = d.$wrapper.find(".exp-row-check:checked").map((_, el) => $(el).val()).get();
				if (!checked.length) { frappe.msgprint(__("Please select at least one row.")); return; }
				d.hide();
				frappe.xcall(
					"vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.trip_make_payment",
					{
						trip_name: frm.doc.name,
						row_names: JSON.stringify(checked),
						cash_bank_account: values.cash_bank_account,
						mode_of_payment: values.mode_of_payment || "Cash",
					}
				).then(r => {
					let msg = __("{0} Payment Entry(ies) created.", [r.created]);
					if (r.payment_entries && r.payment_entries.length) {
						msg += "<br>" + r.payment_entries.join(", ");
					}
					if (r.errors && r.errors.length) {
						msg += "<br><b>" + __("Errors:") + "</b><br>" + r.errors.join("<br>");
					}
					frappe.msgprint({
						title: __("Expense Payment"),
						message: msg,
						indicator: (r.errors && r.errors.length) ? "orange" : "green"
					});
					frm.reload_doc();
				});
			}
		});
		d.show();
		d.$wrapper.on("change", "#exp-chk-all", function () {
			d.$wrapper.find(".exp-row-check").prop("checked", this.checked);
		});
	});
}

// ── Dialog table builders ─────────────────────────────────────────────────────

function build_expense_row_table(rows, show_accounts) {
	let html = `<div style="max-height:400px;overflow-y:auto">
		<table class="table table-bordered table-sm" style="font-size:13px">
		<thead><tr>
			<th style="width:32px"><input type="checkbox" id="exp-chk-all" checked title="Select all"></th>
			<th>${__("Expense Type")}</th>
			<th>${__("Amount")}</th>
			<th>${__("Status")}</th>`;
	if (show_accounts) {
		html += `<th>${__("Expense Acct")}</th><th>${__("Payable Acct")}</th>`;
	}
	html += `</tr></thead><tbody>`;

	rows.forEach(r => {
		const amt = parseFloat(r.request_amount || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
		const expAcc = r.expense_account  || `<span style="color:red">NOT SET</span>`;
		const payAcc = r.payable_account  || `<span style="color:red">NOT SET</span>`;
		html += `<tr>
			<td><input type="checkbox" class="exp-row-check" value="${r.name}" checked></td>
			<td>${r.expense_type || "—"}</td>
			<td>${r.request_currency || ""} ${amt}</td>
			<td>${r.request_status || "—"}</td>`;
		if (show_accounts) {
			html += `<td>${expAcc}</td><td>${payAcc}</td>`;
		}
		html += `</tr>`;
	});
	html += `</tbody></table></div>`;
	return html;
}

function build_payment_row_table(rows) {
	let html = `<div style="max-height:400px;overflow-y:auto;margin-top:10px">
		<table class="table table-bordered table-sm" style="font-size:13px">
		<thead><tr>
			<th style="width:32px"><input type="checkbox" id="exp-chk-all" checked title="Select all"></th>
			<th>${__("Expense Type")}</th>
			<th>${__("Party")}</th>
			<th class="text-right">${__("Amount")}</th>
			<th>${__("Currency")}</th>
			<th>${__("Status")}</th>
		</tr></thead><tbody>`;

	rows.forEach(r => {
		const amt = parseFloat(r.request_amount || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
		const status_badge = r.request_status === "Accounts Approved"
			? '<span style="color:#d97706;font-weight:600">Accounts Approved</span>'
			: '<span style="color:#059669;font-weight:600">Approved</span>';
		html += `<tr>
			<td><input type="checkbox" class="exp-row-check" value="${r.name}" checked></td>
			<td>${r.expense_type || "—"}</td>
			<td>${r.party || "—"}</td>
			<td class="text-right"><b>${amt}</b></td>
			<td>${r.request_currency || "—"}</td>
			<td>${status_badge}</td>
		</tr>`;
	});
	html += `</tbody></table></div>`;
	return html;
}

function build_fuel_row_table(rows, preview) {
	// ── Action banner — tells the user what will happen on approval ───────────
	const is_inventory = preview && preview.fuel_source_type === "From Inventory";
	let banner = "";
	if (preview) {
		if (is_inventory) {
			const wh = preview.warehouse || __("(warehouse not set)");
			banner = `
			<div class="alert alert-primary" style="font-size:12px;padding:8px 12px;margin-bottom:10px;border-radius:6px">
				<b>${__("From Inventory")}</b><br>
				${__("After approval, use <b>Expenses → Reduce Stock</b> to create a Stock Entry and deduct fuel from warehouse: <b>{0}</b>.", [wh])}
			</div>`;
		} else {
			const exp = preview.expense_account || __("(not set)");
			const cash = preview.cash_account || __("(not set)");
			banner = `
			<div class="alert alert-warning" style="font-size:12px;padding:8px 12px;margin-bottom:10px;border-radius:6px">
				<b>${__("Cash Purchase")}</b><br>
				${__("After approval, use <b>Expenses → Create Fuel Payment</b> to create a Payment Entry.")}
				${__("Accounts: <b>{0}</b> Dr / <b>{1}</b> Cr.", [exp, cash])}
			</div>`;
		}
	}

	let html = banner + `<div style="max-height:340px;overflow-y:auto">
		<table class="table table-bordered table-sm" style="font-size:13px">
		<thead><tr>
			<th style="width:32px"><input type="checkbox" id="fuel-chk-all" checked title="Select all"></th>
			<th>${__("Fuel Item")}</th>
			<th>${__("Qty (L)")}</th>
			<th>${__("Total Cost")}</th>
			<th>${__("Status")}</th>
		</tr></thead><tbody>`;

	rows.forEach(r => {
		const cost = parseFloat(r.total_cost || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
		html += `<tr>
			<td><input type="checkbox" class="fuel-row-check" value="${r.name}" checked></td>
			<td>${r.item_name || r.item_code || "—"}</td>
			<td>${r.quantity || 0}</td>
			<td>${r.currency || ""} ${cost}</td>
			<td>${r.status || "—"}</td>
		</tr>`;
	});
	html += `</tbody></table></div>`;
	return html;
}


function show_fuel_payment_dialog(frm, approvedRows) {
	// Build row selection table
	let html = `<div style="max-height:400px;overflow-y:auto">
		<table class="table table-bordered table-sm" style="font-size:13px">
		<thead><tr>
			<th style="width:32px"><input type="checkbox" id="fuel-pay-chk-all" checked title="Select all"></th>
			<th>${__("Fuel Item")}</th>
			<th>${__("Qty (L)")}</th>
			<th>${__("Cost/L")}</th>
			<th>${__("Total Cost")}</th>
			<th>${__("Currency")}</th>
		</tr></thead><tbody>`;

	approvedRows.forEach(r => {
		const cost = parseFloat(r.total_cost || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
		const cpl = parseFloat(r.cost_per_litre || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
		html += `<tr>
			<td><input type="checkbox" class="fuel-pay-check" value="${r.name}" checked></td>
			<td>${r.item_name || r.item_code || "—"}</td>
			<td>${r.quantity || 0}</td>
			<td>${cpl}</td>
			<td>${cost}</td>
			<td>${r.currency || "—"}</td>
		</tr>`;
	});
	html += `</tbody></table></div>`;

	const d = new frappe.ui.Dialog({
		title: __("Create Fuel Payment Entry"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "info_banner",
				options: `<div class="alert alert-info" style="font-size:12px;padding:8px 12px;margin-bottom:10px">
					${__("A Payment Entry will be created for each selected fuel row using the Fuel Expense Account and Fuel Cash Account from <b>Transport Settings</b>.")}
				</div>`,
			},
			{ fieldtype: "HTML", fieldname: "fuel_rows_html", options: html },
		],
		primary_action_label: __("Create Payment Entry"),
		primary_action() {
			const checked = d.$wrapper.find(".fuel-pay-check:checked").map((_, el) => $(el).val()).get();
			if (!checked.length) { frappe.msgprint(__("Please select at least one row.")); return; }
			d.hide();
			frappe.xcall(
				"vsd_fleet_ms.vsd_fleet_ms.doctype.trips.trips.create_fuel_payment_entry",
				{ trip_name: frm.doc.name, fuel_row_names: JSON.stringify(checked) }
			).then(r => {
				let msg = __("{0} Payment Entry(ies) created.", [r.created]);
				if (r.payment_entries.length) {
					msg += "<br>" + r.payment_entries.join(", ");
				}
				if (r.errors.length) {
					msg += "<br><b>" + __("Errors:") + "</b><br>" + r.errors.join("<br>");
				}
				frappe.msgprint({
					title: __("Fuel Payment"),
					message: msg,
					indicator: r.errors.length ? "orange" : "green"
				});
				frm.reload_doc();
			});
		},
	});
	d.show();
	d.$wrapper.on("change", "#fuel-pay-chk-all", function () {
		d.$wrapper.find(".fuel-pay-check").prop("checked", this.checked);
	});
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
