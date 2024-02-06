# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import base64
import datetime
import requests
import frappe
import json
import re
from frappe import _
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
from erpnext_shipstation.erpnext_shipstation.utils import show_error_alert

SHIPSTATION_PROVIDER = 'ShipStation'
BASE_URL = 'https://ssapi.shipstation.com'
CARRIER_CODE = 'stamps_com'

class ShipStation(Document): pass

class ShipStationUtils():
    def __init__(self):
        self.api_password = get_decrypted_password('ShipStation', 'ShipStation', 'api_password', raise_exception=False)
        self.api_id, self.enabled = frappe.db.get_value('ShipStation', 'ShipStation', ['api_id', 'enabled'])

        if not self.enabled:
            link = frappe.utils.get_link_to_form('ShipStation', 'ShipStation', frappe.bold('ShipStation Settings'))
            frappe.throw(_('Please enable ShipStation Integration in {0}'.format(link)), title=_('Mandatory'))

    def get_available_services(self, delivery_to_type, pickup_address,
        delivery_address, shipment_parcel, description_of_content, pickup_date,
        value_of_goods, pickup_contact=None, delivery_contact=None):
        # Retrieve rates at LetMeShip from specification stated.
        if not self.enabled or not self.api_id or not self.api_password:
            return []
        
        self.set_shipstation_specific_fields(pickup_contact, delivery_contact)
        pickup_address.address_title = self.trim_address(pickup_address)
        delivery_address.address_title = self.trim_address(delivery_address)
        parcel_list = self.get_parcel_list(json.loads(shipment_parcel), description_of_content)

        url = BASE_URL + '/shipments/getrates'
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Access-Control-Allow-Origin': 'string'
        }

        payload = {
            "carrierCode": CARRIER_CODE,
            "serviceCode": None,
            "packageCode": None,
            "fromPostalCode": pickup_address.pincode,
            "toState": delivery_address.state,
            "toCountry": delivery_address.country_code,
            "toPostalCode": delivery_address.pincode,
            "toCity": delivery_address.city,
            "weight": {
                "value": parcel_list[0]["weight"] * 1000,
                "units": "grams"
            },
            "dimensions": {
                "units": "centimeters",
                "length": parcel_list[0]["length"],
                "width": parcel_list[0]["width"],
                "height": parcel_list[0]["height"]
            },
            "confirmation": "delivery",
            "residential": delivery_to_type == 'Company'
        }

        try:
            available_services = []
            response_data = requests.post(
                url=url,
                auth=(self.api_id, self.api_password),
                headers=headers,
                data=json.dumps(payload)
            )
            response_data = json.loads(response_data.text)
            
            if 'ExceptionMessage' not in response_data:
                for response in response_data:
                    available_service = self.get_service_dict(response)
                    available_services.append(available_service)

                return available_services
            else:
                frappe.throw(_('An Error occurred while fetching ShipStation prices: {0}')
                .format(response_data['Message']))
        except Exception:
            show_error_alert("fetching ShipStation prices")

        return []

    def create_shipment(self, pickup_address, delivery_address, shipment_parcel, description_of_content,
		pickup_date, value_of_goods, service_info, pickup_contact=None, delivery_contact=None):
        # Create a transaction at ShipStation
        if not self.enabled or not self.api_id or not self.api_password:
            return []
      
        self.set_shipstation_specific_fields(pickup_contact, delivery_contact)
        pickup_address.address_title = self.trim_address(pickup_address)
        delivery_address.address_title = self.trim_address(delivery_address)
        parcel_list = self.get_parcel_list(json.loads(shipment_parcel), description_of_content)
        url = f'{BASE_URL}/shipments/createlabel'

        ship_from_info = self.get_pickup_delivery_info(pickup_address, pickup_contact)
        ship_to_info = self.get_pickup_delivery_info(delivery_address, delivery_contact)

        # Basic Authentication 헤더 생성
        auth_header = base64.b64encode(f"{self.api_id}:{self.api_password}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/json"
        }

        carrier_code = CARRIER_CODE
        service_code = service_info["service_code"]
        package_code = "package"
        confirmation = "delivery"
        ship_date = pickup_date
        weight = {
            "value": parcel_list[0]["weight"] * 1000,
            "units": "grams"
        }
        dimensions = {
            "units": "centimeters",
            "length": parcel_list[0]["length"],
            "width": parcel_list[0]["width"],
            "height": parcel_list[0]["height"]
        }

        ship_from = {
            "name": ship_from_info["person"]["firstname"] + " " + ship_from_info["person"]["lastname"],
            "company": ship_from_info["company"],
            "street1": ship_from_info["address"]["street"],
            "street2": ship_from_info["address"]["addressInfo1"],
            "street3": None,
            "city": ship_from_info["address"]["city"],
            "state": pickup_address["state"],
            "postalCode": ship_from_info["address"]["zip"],
            "country": ship_from_info["address"]["countryCode"],
            "phone": ship_from_info["phone"]["phoneNumberPrefix"] + " " + ship_from_info["phone"]["phoneNumber"],
            "residential": False
        }

        ship_to = {
            "name": ship_to_info["person"]["firstname"] + " " + ship_to_info["person"]["lastname"],
            "company": ship_to_info["company"],
            "street1": ship_to_info["address"]["street"],
            "street2": ship_to_info["address"]["addressInfo1"],
            "street3": None,
            "city": ship_to_info["address"]["city"],
            "state": delivery_address["state"],
            "postalCode": ship_to_info["address"]["zip"],
            "country": ship_to_info["address"]["countryCode"],
            "phone": ship_to_info["phone"]["phoneNumberPrefix"] + " " + ship_to_info["phone"]["phoneNumber"],
            "residential": False
        }

        insurance_options = None
        internationalOptions = None
        advanced_options = None
        test_label = True

        body = {
            "carrierCode": carrier_code,
            "serviceCode": service_code,
            "packageCode": package_code,
            "confirmation": confirmation,
            "shipDate": ship_date,
            "weight": weight,
            "dimensions": dimensions,
            "shipFrom": ship_from,
            "shipTo": ship_to,
            "insuranceOptions": insurance_options,
            "internationalOptions": internationalOptions,
            "advancedOptions": advanced_options,
            "testLabel": test_label
        }

        try:
            response_data = requests.post(
                url=url,
                auth=(self.api_id, self.api_password),
                headers=headers,
                data=json.dumps(body)
            )

            response_data = json.loads(response_data.text)
            
            if 'shipmentId' in response_data:
                awb_number = ''
                tracking_response_data = response_data["trackingNumber"]
                if 'trackingData' in tracking_response_data:
                   for parcel in tracking_response_data['trackingData']['parcelList']:
                      if 'awbNumber' in parcel:
                         awb_number = parcel['awbNumber']

                # Todo return위로 올리기, test
                shipment_data = {
                    'shipment_id': response_data.get('shipmentId'),
                    'order_id': response_data.get('orderId'),
                    'order_key': response_data.get('orderKey'),
                    'user_id': response_data.get('userId'),
                    'ship_date': response_data.get('shipDate'),
                    'shipment_cost': response_data.get('shipmentCost'),
                    'insurance_cost': response_data.get('insuranceCost'),
                    'tracking_number': response_data.get('trackingNumber'),
                    'carrier_code': response_data.get('carrierCode'),
                    'service_code': response_data.get('serviceCode'),
                    'label_data': response_data.get('labelData'),
                    'url_reference': response_data.get('urlReference'),
                    # parent, parentfield, parenttype 필드는 이 예제에서는 처리하지 않습니다.
                }

                shipment_id = shipment_data.get('shipment_id')  # Shipment ID를 가져옵니다.

                if frappe.db.exists('Shipstation Label', shipment_id):
                    # 문서가 존재하면, 각 필드를 업데이트합니다.
                    for field, value in shipment_data.items():
                        if value is not None:  # 값이 None이 아닌 경우에만 설정
                            frappe.db.set_value('Shipstation Label', shipment_id, field, value)
                else:
                    # 존재하지 않으면, 새 문서를 삽입하기 위한 fields와 values 리스트를 준비합니다.
                    fields = ["name"] + [field for field in shipment_data.keys() if shipment_data[field] is not None]
                    values = [[shipment_id] + [shipment_data[field] for field in fields if field != "name"]]
    
                    # bulk_insert 메서드를 사용하여 새 문서를 데이터베이스에 삽입합니다.
                    frappe.db.bulk_insert('Shipstation Label', fields, values, ignore_duplicates=False)


                return {
                  'service_provider': SHIPSTATION_PROVIDER,
                  'shipment_id': response_data['shipmentId'],
                  'carrier': carrier_code,
                  'carrier_service': service_code,
                  'shipment_amount': response_data["shipmentCost"],
                  'awb_number': awb_number,
               }
            elif 'Message' in response_data:
                frappe.throw(_('An Error occurred while creating Shipment: {0}')
                 .format(response_data['ExceptionMessage']))
            
        except Exception as e:
            print(f"에러 발생: {e}")


    def get_tracking_data(self, shipment_id):
        tracking_number = frappe.db.get_value('Shipstation Label', shipment_id, ['tracking_number'])
        return tracking_number
    
    def get_label(self, shipment_id):
        label_data = frappe.db.get_value('Shipstation Label', shipment_id, ['label_data'])
        return label_data

    def trim_address(self, address):
        # LetMeShip has a limit of 30 characters for Company field
        if len(address.address_title) > 30:
            return address.address_title[:30]
        return address.address_title

    def get_service_dict(self, response):
        """Returns a dictionary with service info."""
        available_service = frappe._dict()
        available_service.service_provider = SHIPSTATION_PROVIDER
        available_service.service_code = response['serviceCode']
        available_service.servicename = response['serviceName']
        available_service.carriername = 'Stamps.com'
        available_service.is_preferred = 0
        available_service.total_price = response["shipmentCost"]
        available_service.price_info = response["shipmentCost"]
        available_service.other_cost = response["otherCost"]

        return available_service

    def set_shipstation_specific_fields(self, pickup_contact, delivery_contact):
        pickup_contact.phone_prefix = pickup_contact.phone[:3]
        pickup_contact.phone = re.sub('[^A-Za-z0-9]+', '', pickup_contact.phone[3:])

        pickup_contact.title = 'MS'
        if pickup_contact.gender == 'Male':
            pickup_contact.title = 'MR'

        delivery_contact.phone_prefix = delivery_contact.phone[:3]
        delivery_contact.phone = re.sub('[^A-Za-z0-9]+', '', delivery_contact.phone[3:])

        delivery_contact.title = 'MS'
        if delivery_contact.gender == 'Male':
            delivery_contact.title = 'MR'

    def get_parcel_list(self, shipment_parcel, description_of_content):
        parcel_list = []
        for parcel in shipment_parcel:
            formatted_parcel = {}
            formatted_parcel['height'] = parcel.get('height')
            formatted_parcel['width'] = parcel.get('width')
            formatted_parcel['length'] = parcel.get('length')
            formatted_parcel['weight'] = parcel.get('weight')
            formatted_parcel['quantity'] = parcel.get('count')
            formatted_parcel['contentDescription'] = description_of_content
            parcel_list.append(formatted_parcel)
        return parcel_list

    def get_pickup_delivery_info(self, address, contact):
        return {
            'address': {
                'countryCode': address.country_code,
                'zip': address.pincode,
                'city': address.city,
                'street': address.address_line1,
                'addressInfo1': address.address_line2,
                'houseNo': '',
            },
            'company': address.address_title,
            'person': {
                'title': contact.title,
                'firstname': contact.first_name,
                'lastname': contact.last_name
            },
            'phone': {
                'phoneNumber': contact.phone,
                'phoneNumberPrefix': contact.phone_prefix
            },
            'email': contact.email
        }
