"""Permanent price safety-net for the POS.

No item should ever block a sale because it has no selling price. When the POS
loads items and one has no price on the active price list, we create a *sentinel*
Item Price so the sale can proceed — inline, on demand, only for items actually
loaded (there is no mass backfill).

The sentinel rate is deliberately ``0.01`` (one cent), never a plausible amount:

* it can never be mistaken for a real price,
* it makes an unpriced item glaringly obvious on screen and on the receipt,
* it still unblocks the till.

Because the rate is exactly ``0.01``, every auto-priced item is findable later —
``Item Price`` list filtered to ``price_list_rate = 0.01`` is the worklist of
things that still need a real price. Nothing else in the system prices at 1 cent.

Wired via ``hooks.override_whitelisted_methods`` on the POS ``get_items`` call, so
it runs exactly when an item is loaded for use. Safe by construction: any failure
in here falls back to ERPNext's own result and is logged, never breaking the POS.
"""

import frappe

FALLBACK_RATE = 0.01

#: Item field holding the generated, scannable POS barcode. Optional — sites
#: without it degrade to no barcode on the tile rather than erroring.
FIELD_POS_BARCODE = "custom_pos_barcode"


@frappe.whitelist()
def get_items(start, page_length, price_list, item_group, pos_profile, search_term="", **kwargs):
	"""Drop-in replacement for erpnext's POS get_items that never returns a
	price-less item: any item with no price on ``price_list`` is given a 0.01
	sentinel price (persisted), so the POS can always add it to the cart.

	``**kwargs`` absorbs any extra arguments a future ERPNext POS might send, so a
	signature change upstream can never break this override."""
	from erpnext.selling.page.point_of_sale.point_of_sale import get_items as erp_get_items

	result = erp_get_items(start, page_length, price_list, item_group, pos_profile, search_term)

	try:
		if price_list and isinstance(result, dict):
			for item in result.get("items", []):
				if item.get("price_list_rate"):
					continue
				_ensure_sentinel_price(
					item.get("item_code"),
					price_list,
					item.get("uom") or item.get("stock_uom"),
				)
				item["price_list_rate"] = FALLBACK_RATE
	except Exception:
		# Never let the safety-net break the till — log and return erpnext's result.
		frappe.log_error(frappe.get_traceback(), "nest_home.pos_pricing.get_items")

	return result


@frappe.whitelist()
def get_pos_barcodes(item_codes):
	"""Return the scannable POS barcode for each of ``item_codes``.

	Used by the nest_help POS shim to print the number under each item tile, so a
	cashier can confirm they have the right product — and key the number in by
	hand if the shelf sticker is missing or unreadable.

	Returns ``{"barcodes": {item_code: barcode}}`` — always a truthy dict, even
	when empty (see gotcha 2026-05-13: a whitelisted method must return truthy).
	Sites without the ``custom_pos_barcode`` field simply get an empty map, so
	this is safe on any NestERP install.
	"""
	import json

	if isinstance(item_codes, str):
		try:
			item_codes = json.loads(item_codes)
		except ValueError:
			item_codes = [item_codes]

	out = {}

	if not item_codes:
		return {"barcodes": out}

	if not frappe.get_meta("Item").has_field(FIELD_POS_BARCODE):
		return {"barcodes": out}

	try:
		rows = frappe.get_all(
			"Item",
			filters={"name": ["in", list(item_codes)[:500]]},
			fields=["name", FIELD_POS_BARCODE],
		)
		for row in rows:
			value = row.get(FIELD_POS_BARCODE)
			if value:
				out[row.get("name")] = value
	except Exception:
		# Never let a display nicety break the till.
		frappe.log_error(frappe.get_traceback(), "nest_home.pos_pricing.get_pos_barcodes")

	return {"barcodes": out}


def _ensure_sentinel_price(item_code, price_list, uom=None):
	"""Create a 0.01 selling Item Price for ``item_code`` on ``price_list`` if it
	has none. Idempotent — a second call is a no-op once the price exists."""
	if not item_code or not price_list:
		return

	if frappe.db.exists(
		"Item Price",
		{"item_code": item_code, "price_list": price_list, "selling": 1},
	):
		return

	doc = frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"selling": 1,
			"price_list_rate": FALLBACK_RATE,
			"uom": uom or None,
		}
	)
	doc.insert(ignore_permissions=True)
