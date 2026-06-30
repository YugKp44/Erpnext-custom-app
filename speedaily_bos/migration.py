from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

MAX_ITEM_BATCH_SIZE = 200


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
			results.append(
				{
					"row_number": row_number,
					"status": "ERROR",
					"reference": None,
					"message": _clean_error(exception),
				}
			)

	return {"results": results}


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


def _clean_error(exception: Exception) -> str:
	message = str(exception).strip() or exception.__class__.__name__
	return message[:500]
