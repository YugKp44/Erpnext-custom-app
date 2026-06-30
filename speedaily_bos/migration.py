from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

MAX_ITEM_BATCH_SIZE = 200
MAX_CUSTOMER_BATCH_SIZE = 200


@frappe.whitelist(methods=["POST"])
def import_items(items: str | list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
	"""Create or update a bounded batch of migration Items and their prices."""
	frappe.only_for("System Manager")
	items = frappe.parse_json(items) if isinstance(items, str) else items
	if not isinstance(items, list) or not items:
		frappe.throw(_("At least one Item is required"))
	if len(items) > MAX_ITEM_BATCH_SIZE:
		frappe.throw(
			_("A maximum of {0} Items can be imported at once").format(
				MAX_ITEM_BATCH_SIZE
			)
		)

	results = []
	for index, values in enumerate(items):
		row_number = values.get("row_number", index + 1)
		save_point = f"speedaily_item_{index}"
		frappe.db.savepoint(save_point)
		try:
			item_code, created = _upsert_item(values)
			_upsert_item_price(
				item_code,
				values.get("selling_price_list"),
				values.get("selling_price"),
				selling=True,
			)
			_upsert_item_price(
				item_code,
				values.get("buying_price_list"),
				values.get("purchase_price"),
				selling=False,
			)
			results.append(
				{
					"row_number": row_number,
					"status": "IMPORTED",
					"reference": item_code,
					"message": "Created" if created else "Updated",
				}
			)
		except Exception as exception:
			frappe.db.rollback(save_point=save_point)
			frappe.log_error(
				title=f"Speedaily item import failed at row {row_number}",
				message=frappe.get_traceback(),
			)
			results.append(
				{
					"row_number": row_number,
					"status": "ERROR",
					"reference": None,
					"message": _clean_error(exception),
				}
			)

	return {"results": results}


@frappe.whitelist(methods=["POST"])
def import_customers(
	customers: str | list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
	"""Create or update a bounded batch of Customers and their contact details."""
	frappe.only_for("System Manager")
	customers = (
		frappe.parse_json(customers)
		if isinstance(customers, str)
		else customers
	)
	if not isinstance(customers, list) or not customers:
		frappe.throw(_("At least one Customer is required"))
	if len(customers) > MAX_CUSTOMER_BATCH_SIZE:
		frappe.throw(
			_("A maximum of {0} Customers can be imported at once").format(
				MAX_CUSTOMER_BATCH_SIZE
			)
		)

	results = []
	for index, values in enumerate(customers):
		row_number = values.get("row_number", index + 1)
		save_point = f"speedaily_customer_{index}"
		frappe.db.savepoint(save_point)
		try:
			customer_name, created = _upsert_customer(values)
			results.append(
				{
					"row_number": row_number,
					"status": "IMPORTED",
					"reference": customer_name,
					"message": "Created" if created else "Updated",
				}
			)
		except Exception as exception:
			frappe.db.rollback(save_point=save_point)
			frappe.log_error(
				title=f"Speedaily customer import failed at row {row_number}",
				message=frappe.get_traceback(),
			)
			results.append(
				{
					"row_number": row_number,
					"status": "ERROR",
					"reference": None,
					"message": _clean_error(exception),
				}
			)

	return {"results": results}


def _upsert_customer(values: dict[str, Any]) -> tuple[str, bool]:
	customer_label = _required(values.get("customer_name"), "customer_name")
	existing = frappe.db.get_value(
		"Customer",
		{"customer_name": customer_label},
		"name",
	)
	doc = frappe.get_doc("Customer", existing) if existing else frappe.new_doc("Customer")

	doc.customer_name = customer_label
	doc.customer_type = (
		"Individual"
		if str(values.get("customer_type") or "").strip().lower() == "individual"
		else "Company"
	)
	doc.customer_group = _required(values.get("customer_group"), "customer_group")
	doc.territory = _required(values.get("territory"), "territory")
	doc.default_currency = values.get("default_currency") or "INR"
	doc.tax_id = values.get("tax_id") or ""
	if doc.meta.has_field("gst_category"):
		doc.gst_category = values.get("gst_category") or "Unregistered"
	if doc.meta.has_field("gstin"):
		doc.gstin = values.get("gstin") or ""
	doc.website = values.get("website") or ""
	doc.customer_details = values.get("customer_details") or ""
	doc.disabled = 0
	doc.flags.ignore_permissions = True

	if existing:
		doc.save()
	else:
		doc.insert()

	contact_name = _upsert_customer_contact(doc.name, values)
	address_name = _upsert_customer_address(doc.name, customer_label, values)
	if contact_name:
		doc.customer_primary_contact = contact_name
	if address_name:
		doc.customer_primary_address = address_name
	if contact_name or address_name:
		doc.save()
	return doc.name, not bool(existing)


def _upsert_customer_contact(
	customer_name: str,
	values: dict[str, Any],
) -> str | None:
	email = _text(values.get("email"))
	phone = _text(values.get("phone"))
	mobile = _text(values.get("mobile"))
	contact_name = _text(values.get("contact_name"))
	if not any((email, phone, mobile, contact_name)):
		return None

	existing = frappe.db.get_value(
		"Dynamic Link",
		{
			"link_doctype": "Customer",
			"link_name": customer_name,
			"parenttype": "Contact",
		},
		"parent",
	)
	doc = frappe.get_doc("Contact", existing) if existing else frappe.new_doc("Contact")
	doc.first_name = contact_name or customer_name
	doc.set("email_ids", [])
	if email:
		doc.append("email_ids", {"email_id": email, "is_primary": 1})
	doc.set("phone_nos", [])
	if phone:
		doc.append("phone_nos", {"phone": phone, "is_primary_phone": 1})
	if mobile and mobile != phone:
		doc.append("phone_nos", {"phone": mobile, "is_primary_mobile_no": 1})
	doc.set(
		"links",
		[{"link_doctype": "Customer", "link_name": customer_name}],
	)
	doc.flags.ignore_permissions = True
	if existing:
		doc.save()
	else:
		doc.insert()
	return doc.name


def _upsert_customer_address(
	customer_name: str,
	customer_label: str,
	values: dict[str, Any],
) -> str | None:
	address_line1 = _text(values.get("address_line1"))
	city = _text(values.get("city"))
	if not address_line1 or not city:
		return None

	existing = frappe.db.get_value(
		"Dynamic Link",
		{
			"link_doctype": "Customer",
			"link_name": customer_name,
			"parenttype": "Address",
		},
		"parent",
	)
	doc = frappe.get_doc("Address", existing) if existing else frappe.new_doc("Address")
	doc.address_title = customer_label
	doc.address_type = "Billing"
	doc.address_line1 = address_line1
	doc.address_line2 = _text(values.get("address_line2")) or ""
	doc.city = city
	doc.state = _text(values.get("state")) or ""
	doc.country = _text(values.get("country")) or "India"
	doc.pincode = _text(values.get("pincode")) or ""
	doc.email_id = _text(values.get("email")) or ""
	doc.phone = _text(values.get("phone")) or _text(values.get("mobile")) or ""
	if doc.meta.has_field("gst_category"):
		doc.gst_category = values.get("gst_category") or "Unregistered"
	if doc.meta.has_field("gstin"):
		doc.gstin = values.get("gstin") or ""
	doc.set(
		"links",
		[{"link_doctype": "Customer", "link_name": customer_name}],
	)
	doc.flags.ignore_permissions = True
	if existing:
		doc.save()
	else:
		doc.insert()
	return doc.name


def _upsert_item(values: dict[str, Any]) -> tuple[str, bool]:
	item_code = _required(values.get("item_code"), "item_code")
	item_name = _required(values.get("item_name"), "item_name")
	existing = frappe.db.exists("Item", item_code)
	doc = frappe.get_doc("Item", item_code) if existing else frappe.new_doc("Item")

	doc.item_code = item_code
	doc.item_name = item_name
	doc.item_group = _required(values.get("item_group"), "item_group")
	doc.stock_uom = _required(values.get("stock_uom"), "stock_uom")
	doc.is_stock_item = int(bool(values.get("is_stock_item", 1)))
	doc.disabled = 0
	doc.description = values.get("description") or ""
	doc.gst_hsn_code = values.get("gst_hsn_code") or ""
	doc.flags.ignore_permissions = True

	if existing:
		doc.save()
	else:
		doc.insert()
	return doc.name, not bool(existing)


def _upsert_item_price(
	item_code: str,
	price_list: str | None,
	rate: Any,
	*,
	selling: bool,
) -> None:
	if not price_list or rate is None or flt(rate) <= 0:
		return

	filters = {"item_code": item_code, "price_list": price_list}
	existing = frappe.db.get_value("Item Price", filters, "name")
	doc = (
		frappe.get_doc("Item Price", existing)
		if existing
		else frappe.new_doc("Item Price")
	)
	doc.item_code = item_code
	doc.price_list = price_list
	doc.price_list_rate = flt(rate)
	doc.selling = int(selling)
	doc.buying = int(not selling)
	doc.flags.ignore_permissions = True
	if existing:
		doc.save()
	else:
		doc.insert()


def _required(value: Any, fieldname: str) -> str:
	text = str(value or "").strip()
	if not text:
		frappe.throw(_("{0} is required").format(fieldname))
	return text


def _text(value: Any) -> str | None:
	text = str(value or "").strip()
	return text or None


def _clean_error(exception: Exception) -> str:
	message = str(exception).strip() or exception.__class__.__name__
	return message[:500]
