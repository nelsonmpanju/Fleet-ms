# Copyright (c) 2024, VV SYSTEMS DEVELOPER LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns, data = [], []
	columns = get_columns()
	data = get_data(filters)
	return columns, data, None

def get_columns():
	# Define the columns to be displayed in the report
	return [
		{"fieldname": "vehicle_trip", "fieldtype": "Link", "label": "Vehicle Trip", "options": "Trips", "width": 120},
		{"fieldname": "date", "fieldtype": "Date", "label": "Trip Date", "width": 100},
		{"fieldname": "driver_name", "fieldtype": "Data", "label": "Driver Name", "width": 150},
		{"fieldname": "truck_number", "fieldtype": "Data", "label": "Truck Number", "width": 120},
		{"fieldname": "transporter_type", "fieldtype": "Data", "label": "Transporter Type", "width": 130},
		{"fieldname": "trip_status", "fieldtype": "Data", "label": "Trip Status", "width": 100},
		{"fieldname": "truck_licence_plate", "fieldtype": "Data", "label": "Licence Plate", "width": 120},
		{"fieldname": "route", "fieldtype": "Link", "label": "Route", "options": "Trip Routes", "width": 180},
		{"fieldname": "item_name", "fieldtype": "Data", "label": "Item Name", "width": 120},
		{"fieldname": "uom", "fieldtype": "Data", "label": "UOM", "width": 70},
		{"fieldname": "quantity", "fieldtype": "Float", "label": "Quantity", "width": 100},
		{"fieldname": "cost_per_litre", "fieldtype": "Float", "label": "Cost Per Litre", "width": 110},
		{"fieldname": "currency", "fieldtype": "Link", "label": "Currency", "options": "Currency", "width": 80},
		{"fieldname": "total_cost", "fieldtype": "Currency", "options": "currency", "label": "Total Cost", "width": 130},
		{"fieldname": "disbursement_type", "fieldtype": "Data", "label": "Disbursement Type", "width": 140},
		{"fieldname": "status", "fieldtype": "Data", "label": "Status", "width": 100},
		{"fieldname": "approved_by", "fieldtype": "Data", "label": "Approved By", "width": 130},
		{"fieldname": "approved_date", "fieldtype": "Date", "label": "Approved Date", "width": 110},
		{"fieldname": "round_trip", "fieldtype": "Check", "label": "Round Trip", "width": 90},
		{"fieldname": "trip_complited", "fieldtype": "Check", "label": "Trip Completed", "width": 110},
	]

def get_data(filters):
	data = []
	vehicle_trips = frappe.db.sql("SELECT * FROM tabTrips T INNER JOIN `tabFuel Requests Table` FL ON FL.parent = T.name",as_dict=True)
	for trip in vehicle_trips:
		data.append({
			"round_trip": trip.round_trip,
			"driver_name": trip.driver_name,
			"trip_complited": trip.trip_complited,
			"truck_number": trip.truck_number,
			"transporter_type": trip.transporter_type,
			"trip_status": trip.trip_status,
			"truck_number": trip.truck_number,
			"truck_licence_plate": trip.truck_licence_plate,
			"route": trip.route,
			"vehicle_trip": trip.parent,
			"item_code": trip.item_code,
			"item_name": trip.item_name,
			"uom": trip.uom,
			"quantity": trip.quantity,
			"cost_per_litre": trip.cost_per_litre,
			"currency": trip.currency,
			"total_cost": trip.total_cost,
			"disbursement_type": trip.disbursement_type,
			"status": trip.status,
			"approved_by": trip.approved_by,
			"date": trip.date,
			"approved_date": trip.approved_date

		})
	return data