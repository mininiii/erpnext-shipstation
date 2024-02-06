# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
import json
from six import string_types
from frappe import _
from frappe.utils import flt
from erpnext.stock.doctype.shipment.shipment import get_company_contact
from erpnext_shipstation.erpnext_shipstation.utils import get_address, get_contact, match_parcel_service_type_carrier
from erpnext_shipstation.erpnext_shipstation.doctype.shipstation.shipstation import SHIPSTATION_PROVIDER, ShipStationUtils

@frappe.whitelist()
def fetch_shipping_rates(pickup_from_type, delivery_to_type, pickup_address_name, delivery_address_name,
	shipment_parcel, description_of_content, pickup_date, value_of_goods,
	pickup_contact_name=None, delivery_contact_name=None):
	# Return Shipping Rates for the various Shipping Providers
	shipment_prices = []
	shipstation_enabled = frappe.db.get_single_value('ShipStation','enabled')
	pickup_address = get_address(pickup_address_name)
	delivery_address = get_address(delivery_address_name)

	if shipstation_enabled:
		pickup_contact = None
		delivery_contact = None
		if pickup_from_type != 'Company':
			pickup_contact = get_contact(pickup_contact_name)
		else:
			pickup_contact = get_company_contact(user=pickup_contact_name)

		if delivery_to_type != 'Company':
			delivery_contact = get_contact(delivery_contact_name)
		else:
			delivery_contact = get_company_contact(user=pickup_contact_name)

		shipstaion = ShipStationUtils()
		shipstaion_prices = shipstaion.get_available_services(
			delivery_to_type=delivery_to_type,
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel,
			description_of_content=description_of_content,
			pickup_date=pickup_date,
			value_of_goods=value_of_goods,
			pickup_contact=pickup_contact,
			delivery_contact=delivery_contact,
		) or []
		shipstaion_prices = match_parcel_service_type_carrier(shipstaion_prices, ['carrier', 'carrier_name'])
		shipment_prices = shipment_prices + shipstaion_prices
	shipment_prices = sorted(shipment_prices, key=lambda k:k['total_price'])
	return shipment_prices

@frappe.whitelist()
def create_shipment(shipment, pickup_from_type, delivery_to_type, pickup_address_name,
		delivery_address_name, shipment_parcel, description_of_content, pickup_date,
		value_of_goods, service_data, shipment_notific_email=None, tracking_notific_email=None,
		pickup_contact_name=None, delivery_contact_name=None, delivery_notes=[]):
	# Create Shipment for the selected provider
	service_info = json.loads(service_data)
	shipment_info, pickup_contact,  delivery_contact = None, None, None
	pickup_address = get_address(pickup_address_name)
	delivery_address = get_address(delivery_address_name)

	if pickup_from_type != 'Company':
		pickup_contact = get_contact(pickup_contact_name)
	else:
		pickup_contact = get_company_contact(user=pickup_contact_name)

	if delivery_to_type != 'Company':
		delivery_contact = get_contact(delivery_contact_name)
	else:
		delivery_contact = get_company_contact(user=pickup_contact_name)

	if service_info['service_provider'] == SHIPSTATION_PROVIDER:
		shipstation = ShipStationUtils()
		shipment_info = shipstation.create_shipment(
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel,
			description_of_content=description_of_content,
			pickup_date=pickup_date,
			value_of_goods=value_of_goods,
			pickup_contact=pickup_contact,
			delivery_contact=delivery_contact,
			service_info=service_info
		)

	if shipment_info:
		fields = ['service_provider', 'carrier', 'carrier_service', 'shipment_id', 'shipment_amount', 'awb_number']
		for field in fields:
			frappe.db.set_value('Shipment', shipment, field, shipment_info.get(field))
		frappe.db.set_value('Shipment', shipment, 'status', 'Booked')

		if delivery_notes:
			update_delivery_note(delivery_notes=delivery_notes, shipment_info=shipment_info)

	return shipment_info

@frappe.whitelist()
def print_shipping_label(service_provider, shipment_id):
	if service_provider == SHIPSTATION_PROVIDER:
		shipstation = ShipStationUtils()
		shipping_label = shipstation.get_label(shipment_id)
	return shipping_label

@frappe.whitelist()
def show_tracking(shipment, service_provider, shipment_id, delivery_notes=[]):
	if service_provider == SHIPSTATION_PROVIDER:
		shipstation = ShipStationUtils()
		tracking_data = shipstation.get_tracking_data(shipment_id)
		return tracking_data

def update_delivery_note(delivery_notes, shipment_info=None, tracking_info=None):
	# Update Shipment Info in Delivery Note
	# Using db_set since some services might not exist
	if isinstance(delivery_notes, string_types):
		delivery_notes = json.loads(delivery_notes)

	delivery_notes = list(set(delivery_notes))

	for delivery_note in delivery_notes:
		dl_doc = frappe.get_doc('Delivery Note', delivery_note)
		if tracking_info:
			dl_doc.db_set('tracking_number', tracking_info.get('awb_number'))
			dl_doc.db_set('tracking_url', tracking_info.get('tracking_url'))
			dl_doc.db_set('tracking_status', tracking_info.get('tracking_status'))
			dl_doc.db_set('tracking_status_info', tracking_info.get('tracking_status_info'))