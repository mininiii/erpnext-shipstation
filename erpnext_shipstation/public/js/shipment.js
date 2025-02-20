// Copyright (c) 2020, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Shipment', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && !frm.doc.shipment_id) {
			frm.add_custom_button(__('Fetch Shipping Rates'), function() {
				return frm.events.fetch_shipping_rates(frm);
			});
		}
		if (frm.doc.shipment_id) {
			frm.add_custom_button(__('Print Shipping Label'), function() {
				return frm.events.print_shipping_label(frm);
			}, __('Tools'));
			if (frm.doc.tracking_status != 'Delivered') {
			// 	frm.add_custom_button(__('Show Tracking'), function() {
			// 		return frm.events.update_tracking(frm, frm.doc.service_provider, frm.doc.shipment_id);
			// 	}, __('Tools'));

				frm.add_custom_button(__('Track Status'), function() {
					// if (frm.doc.tracking_url) {
					// 	const urls = frm.doc.tracking_url.split(', ');
					// 	urls.forEach(url => window.open(url));
					// } else {
					// 	let msg = __("Please complete Shipment (ID: {0}) on {1} and Update Tracking.", [frm.doc.shipment_id, frm.doc.service_provider]);
					// 	frappe.msgprint({message: msg, title: __("Incomplete Shipment")});
					// }
					return frm.events.show_tracking(frm, frm.doc.service_provider, frm.doc.shipment_id);
				}, __('Tools'));
			}
		}
	},

	fetch_shipping_rates: function(frm) {
		if (!frm.doc.shipment_id) {
			frappe.call({
				method: "erpnext_shipstation.erpnext_shipstation.shipping.fetch_shipping_rates",
				freeze: true,
				freeze_message: __("Fetching Shipping Rates"),
				args: {
					pickup_from_type: frm.doc.pickup_from_type,
					delivery_to_type: frm.doc.delivery_to_type,
					pickup_address_name: frm.doc.pickup_address_name,
					delivery_address_name: frm.doc.delivery_address_name,
					shipment_parcel: frm.doc.shipment_parcel,
					description_of_content: frm.doc.description_of_content,
					pickup_date: frm.doc.pickup_date,
					pickup_contact_name: frm.doc.pickup_from_type === 'Company' ? frm.doc.pickup_contact_person : frm.doc.pickup_contact_name,
					delivery_contact_name: frm.doc.delivery_contact_name,
					value_of_goods: frm.doc.value_of_goods
				},
				callback: function(r) {
					if (r.message && r.message.length) {
						select_from_available_services(frm, r.message);
					}
					else {
						frappe.msgprint({message:__("No Shipment Services available"), title:__("Note")});
					}
				}
			});
		}
		else {
			frappe.throw(__("Shipment already created"));
		}
	},

	print_shipping_label: function(frm) {
		frappe.call({
			method: "erpnext_shipstation.erpnext_shipstation.shipping.print_shipping_label",
			freeze: true,
			freeze_message: __("Printing Shipping Label"),
			args: {
				shipment_id: frm.doc.shipment_id,
				service_provider: frm.doc.service_provider
			},
			callback: function(r) {
				if (r.message) {
					if (frm.doc.service_provider == "ShipStation") {
						var array = base64ToArrayBuffer(r.message); // base64를 ArrayBuffer로 변환

						const file = new Blob([array], {type: "application/pdf"}); // Blob 객체로 변환

						const file_url = URL.createObjectURL(file); // Blob 객체의 URL 생성

						window.open(file_url); // 새 창을 열어 PDF 파일 표시

						function base64ToArrayBuffer(base64) {
							var binary_string = window.atob(base64);
							var len = binary_string.length;
							var bytes = new Uint8Array(len);
							for (var i = 0; i < len; i++) {
								bytes[i] = binary_string.charCodeAt(i);
							}
							return bytes.buffer;
}
					}
					else {
						if (Array.isArray(r.message)) {
							r.message.forEach(url => window.open(url));
						} else {
							window.open(r.message);
						}
					}
				}
			}
		});
	},

	show_tracking: function(frm, service_provider, shipment_id) {
		let delivery_notes = [];
		(frm.doc.shipment_delivery_note || []).forEach((d) => {
			delivery_notes.push(d.delivery_note);
		});
		
		frappe.call({
			method: "erpnext_shipstation.erpnext_shipstation.shipping.show_tracking",
			freeze: true,
			freeze_message: __("Updating Tracking"),
			args: {
				shipment: frm.doc.name,
				shipment_id: shipment_id,
				service_provider: service_provider,
				delivery_notes: delivery_notes
			},
			callback: function(r) {
				if (r.message) {
					
					// URL 변수를 추출합니다.
					let tracking_number = r.message;
					// 추적 번호를 URL에 삽입합니다.
					let url = `https://tools.usps.com/go/TrackConfirmAction?tRef=fullpage&tLc=2&text28777=&tLabels=${tracking_number}%2C&tABt=true`;
				
					// 작은 창으로 열기 위한 JavaScript 코드입니다.
					window.open(url, "_blank", "width=600,height=400");
				}
			}
		});
	}
});

function select_from_available_services(frm, available_services) {

	var headers = [ __("Service Provider"), __("Parcel Service"), __("Parcel Service Type"), __("Price"), "" ];

	frm.render_available_services = function(dialog, headers, available_services) {
		frappe.require('assets/erpnext_shipstation/js/shipment.js', function() {
			dialog.fields_dict.available_services.$wrapper.html(`
			<div style="overflow-x:scroll;">
				<table class="table table-bordered table-hover">
					<thead class="grid-heading-row">
						<tr>
							${headers.map(header => `<th style="padding-left: 12px;">${header}</th>`).join('')}
						</tr>
					</thead>
					<tbody>
						${available_services.map((service, i) => `
							<tr id="data-other-${i}">
								<td class="service-info" style="width:20%;">${service.service_provider}</td>
								<td class="service-info" style="width:20%;">${service.carriername}</td>
								<td class="service-info" style="width:40%;">${service.servicename}</td>
								<td class="service-info" style="width:20%;">${format_currency(service.total_price, "USD", 2)}</td>
								<td style="width:10%;vertical-align: middle;">
									<button
										data-type="other_services"
										id="data-other-${i}" type="button" class="btn">
										Select
									</button>
								</td>
							</tr>
						`).join('')}
					</tbody>
				</table>
			</div>
		`);
		});
	};
	

	const dialog = new frappe.ui.Dialog({
		title: __("Select Service to Create Shipment"),
		fields: [
			{
				fieldtype:'HTML',
				fieldname:"available_services",
				label: __('Available Services')
			}
		]
	});

	let delivery_notes = [];
	(frm.doc.shipment_delivery_note || []).forEach((d) => {
		delivery_notes.push(d.delivery_note);
	});

	frm.render_available_services(dialog, headers, available_services);

	dialog.$body.on('click', '.btn', function() {
		// let service_type = $(this).attr("data-type");
		let service_index = cint($(this).attr("id").split("-")[2]);
		let service_data = available_services[service_index];
		frm.select_row(service_data);
	});

	frm.select_row = function(service_data){
		frappe.call({
			method: "erpnext_shipstation.erpnext_shipstation.shipping.create_shipment",
			freeze: true,
			freeze_message: __("Creating Shipment"),
			args: {
				shipment: frm.doc.name,
				pickup_from_type: frm.doc.pickup_from_type,
				delivery_to_type: frm.doc.delivery_to_type,
				pickup_address_name: frm.doc.pickup_address_name,
				delivery_address_name: frm.doc.delivery_address_name,
				shipment_parcel: frm.doc.shipment_parcel,
				description_of_content: frm.doc.description_of_content,
				pickup_date: frm.doc.pickup_date,
				pickup_contact_name: frm.doc.pickup_from_type === 'Company' ? frm.doc.pickup_contact_person : frm.doc.pickup_contact_name,
				delivery_contact_name: frm.doc.delivery_contact_name,
				value_of_goods: frm.doc.value_of_goods,
				service_data: service_data,
				delivery_notes: delivery_notes,
			},
			callback: function(r) {
				if (!r.exc) {
					frm.reload_doc();
					frappe.msgprint({
							message: __("Shipment {1} has been created with {0}.", [r.message.service_provider, r.message.shipment_id]),
							title: __("Shipment Created"),
							indicator: "green"
						});
					frm.events.update_tracking(frm, r.message.service_provider, r.message.shipment_id);
				}
			}
		});
		dialog.hide();
	};
	dialog.show();
}