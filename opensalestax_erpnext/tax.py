# SPDX-License-Identifier: Apache-2.0
"""OpenSalesTax tax-computation hook.

Entry point: `apply_opensalestax(doc, method=None)` — registered as a
`doc_events: validate` handler in `hooks.py` for Sales Invoice, Sales
Order, and Quotation.

Flow:
  1. Gate checks (enabled, USD, US ship-to, valid ZIP).
  2. Cache lookup keyed on ZIP; engine call on miss.
  3. Clear `doc.taxes` and append per-jurisdiction lines.
  4. Re-run ERPNext's `calculate_taxes_and_totals(doc)` to refresh totals.

Fail-soft: on any engine error, the hook silently no-ops (default) or
throws on save (when `fail_soft = 0`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import frappe
from frappe import _

from . import cache
from .client_factory import build_client
from .exceptions import OstaxConfigError, OstaxError

# ---------------------------------------------------------------------------
# Public hook entry point
# ---------------------------------------------------------------------------


def apply_opensalestax(doc: Any, method: str | None = None) -> None:
	"""Replace `doc.taxes` with OpenSalesTax-computed per-jurisdiction lines.

	Registered for `validate` events on Sales Invoice, Sales Order, and
	Quotation. When the gate checks fail, this is a silent no-op — the
	user's existing tax template applies normally.
	"""
	try:
		settings = _settings()
	except Exception:
		# Settings doctype not yet installed — defensive guard during the
		# install→test gap. No-op.
		return

	if not _should_apply(doc, settings):
		return

	zip5 = _extract_zip(doc)
	if not zip5:
		return

	taxable_total, _items = _collect_taxable_items(doc, settings)
	if taxable_total <= 0:
		return

	try:
		result = _fetch_rate(zip5, taxable_total, settings)
	except OstaxError as e:
		if bool(getattr(settings, "fail_soft", 1)):
			_log_engine_error(doc, e)
			return
		frappe.throw(_("OpenSalesTax: tax computation failed — {0}").format(str(e)))
	except Exception as e:
		if bool(getattr(settings, "fail_soft", 1)):
			_log_engine_error(doc, e)
			return
		frappe.throw(_("OpenSalesTax: engine call failed — {0}").format(str(e)))

	if not result or not result.get("jurisdictions"):
		# Engine returned no taxable jurisdictions — leave doc.taxes alone
		return

	_replace_tax_lines(doc, result, settings)
	_refresh_totals(doc)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def _settings() -> Any:
	"""Return the OpenSalesTax Settings Single doc (cached per request)."""
	return frappe.get_cached_doc("OpenSalesTax Settings")


def _should_apply(doc: Any, settings: Any) -> bool:
	if not bool(getattr(settings, "enabled", 0)):
		return False
	if (doc.get("currency") or "").upper() != "USD":
		return False
	address = _resolve_shipping_address(doc)
	if address is None:
		return False
	if (address.get("country") or "").strip() != "United States":
		return False
	return True


def _resolve_shipping_address(doc: Any) -> Any:
	"""Pick the best Address record for the ship-to side of `doc`.

	Order of preference: `shipping_address_name` → `customer_address`.
	Returns None if no Address is linked.
	"""
	addr_name = doc.get("shipping_address_name") or doc.get("customer_address")
	if not addr_name:
		return None
	try:
		return frappe.get_cached_doc("Address", addr_name)
	except frappe.DoesNotExistError:
		return None


def _extract_zip(doc: Any) -> str | None:
	"""Return the 5-digit ZIP from the doc's shipping address, or None."""
	address = _resolve_shipping_address(doc)
	if not address:
		return None
	pincode = (address.get("pincode") or "").strip()
	if not pincode:
		return None
	# Reduce ZIP+4 ("12345-6789") to 5-digit
	first = pincode.split("-")[0]
	if len(first) == 5 and first.isdigit():
		return first
	return None


# ---------------------------------------------------------------------------
# Item collection
# ---------------------------------------------------------------------------


def _collect_taxable_items(doc: Any, settings: Any) -> tuple[float, list[Any]]:
	"""Sum the items eligible for OpenSalesTax computation.

	Skips items with an explicit `item_tax_template` when
	`treat_item_tax_template_as_override` is enabled (the default).
	"""
	respect_override = bool(getattr(settings, "treat_item_tax_template_as_override", 1))
	total = 0.0
	taxable_items: list[Any] = []

	for item in doc.get("items") or []:
		if respect_override and (item.get("item_tax_template") or "").strip():
			# Merchant has marked this item as having override rates — leave it alone
			continue
		amount = item.get("amount")
		if amount is None:
			rate = item.get("rate") or 0
			qty = item.get("qty") or 0
			amount = float(rate) * float(qty)
		total += float(amount)
		taxable_items.append(item)

	return total, taxable_items


# ---------------------------------------------------------------------------
# Engine call
# ---------------------------------------------------------------------------


def _fetch_rate(zip5: str, taxable_total: float, settings: Any) -> dict[str, Any]:
	"""Return the engine's calculate response for `zip5` and `taxable_total`.

	Cache first (keyed on ZIP only — rates don't depend on amount).
	On miss, builds a client and calls the engine's calculate endpoint.

	The cached entry contains a normalized response of the form::

		{
			"jurisdictions": [
				{"name": "Minnesota", "rate_pct": Decimal("6.875"), "kind": "state"},
				{"name": "Hennepin County", "rate_pct": Decimal("0.15"), "kind": "county"},
				...
			],
			"engine_version": "0.54.1",
		}

	Returned dict also contains a `tax_amounts` key (per-jurisdiction
	dollar amounts for `taxable_total`) computed at lookup time.
	"""
	ttl = int(getattr(settings, "cache_ttl_seconds", 86400) or 0)
	cached = cache.get(zip5)
	if cached is not None:
		return _apply_amount(cached, taxable_total)

	client = build_client(settings)
	raw = _call_engine(client, zip5, taxable_total)
	normalized = _normalize_response(raw)
	cache.put(zip5, normalized, ttl)
	return _apply_amount(normalized, taxable_total)


def _call_engine(client: Any, zip5: str, taxable_total: float) -> Any:
	"""Single chokepoint for the actual SDK call.

	Kept tiny so tests can monkeypatch this function instead of mocking
	the entire SDK client.
	"""
	# The SDK accepts a typed payload; for v0.1 we pass a single line item
	# representing the taxable subtotal. Per-line breakdown is deferred to v0.2
	# when we plumb item-level categories.
	return client.calculate(
		ship_to={"zip5": zip5, "country": "US"},
		line_items=[{"amount": str(Decimal(str(taxable_total)).quantize(Decimal("0.01"))), "quantity": 1}],
	)


def _normalize_response(raw: Any) -> dict[str, Any]:
	"""Reshape the SDK response into the cache-friendly schema.

	The SDK exposes per-jurisdiction breakdown; we collapse it into a list
	of `{name, rate_pct, kind}` rows. Resilient to slight schema drift —
	missing fields default to empty/zero.
	"""
	jurisdictions = []
	for j in _safe_iter(getattr(raw, "jurisdictions", None) or _dig(raw, "jurisdictions") or []):
		name = _dig(j, "name") or _dig(j, "label") or "Tax"
		rate = _dig(j, "rate_pct")
		if rate is None:
			rate = _dig(j, "rate") or 0
		kind = _dig(j, "kind") or _dig(j, "type") or ""
		try:
			rate_pct = Decimal(str(rate))
		except Exception:
			rate_pct = Decimal("0")
		jurisdictions.append({"name": str(name), "rate_pct": str(rate_pct), "kind": str(kind)})

	engine_version = _dig(raw, "engine_version") or _dig(raw, "version") or ""
	return {
		"jurisdictions": jurisdictions,
		"engine_version": str(engine_version),
	}


def _apply_amount(normalized: dict[str, Any], taxable_total: float) -> dict[str, Any]:
	"""Multiply each jurisdiction's rate against `taxable_total`.

	Returns a copy with `tax_amounts` populated (one entry per jurisdiction)
	plus a `total_tax` summary.
	"""
	total_amount = Decimal("0")
	tax_amounts: list[dict[str, Any]] = []
	base = Decimal(str(taxable_total)).quantize(Decimal("0.0001"))
	for j in normalized.get("jurisdictions", []):
		try:
			rate_pct = Decimal(str(j.get("rate_pct") or "0"))
		except Exception:
			rate_pct = Decimal("0")
		amount = (base * rate_pct / Decimal("100")).quantize(Decimal("0.01"))
		total_amount += amount
		tax_amounts.append({"name": j.get("name", ""), "kind": j.get("kind", ""), "amount": str(amount)})
	return {
		"jurisdictions": normalized.get("jurisdictions", []),
		"engine_version": normalized.get("engine_version", ""),
		"tax_amounts": tax_amounts,
		"total_tax": str(total_amount),
	}


# ---------------------------------------------------------------------------
# Tax-line writeback
# ---------------------------------------------------------------------------


def _replace_tax_lines(doc: Any, result: dict[str, Any], settings: Any) -> None:
	"""Clear `doc.taxes` and append one row per jurisdiction.

	Each row uses `charge_type="Actual"` with our computed amount so
	ERPNext doesn't recompute via percentage math against an internally
	derived net total (which could differ from our taxable_total when
	item-tax-template items are present).
	"""
	tax_account = getattr(settings, "tax_account_head", None)
	if not tax_account:
		raise OstaxConfigError("OpenSalesTax Settings: 'Tax Account Head' is required")

	cost_center = (
		frappe.get_cached_value("Company", doc.get("company"), "cost_center") if doc.get("company") else None
	)

	doc.set("taxes", [])
	for entry in result.get("tax_amounts", []):
		label_parts = ["OpenSalesTax"]
		kind = entry.get("kind") or ""
		name = entry.get("name") or "US"
		if kind:
			label_parts.append(kind.title())
		label_parts.append(name)
		description = " — ".join(filter(None, [label_parts[0], " ".join(label_parts[1:])]))

		row = {
			"charge_type": "Actual",
			"account_head": tax_account,
			"description": description,
			"tax_amount": float(entry.get("amount", 0)),
			"cost_center": cost_center,
		}
		doc.append("taxes", row)


def _refresh_totals(doc: Any) -> None:
	"""Re-run ERPNext's totals math against our just-appended tax lines."""
	from erpnext.controllers.taxes_and_totals import calculate_taxes_and_totals

	calculate_taxes_and_totals(doc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dig(obj: Any, key: str) -> Any:
	"""Read attribute-or-key from an object/dict. Returns None on miss."""
	if obj is None:
		return None
	if isinstance(obj, dict):
		return obj.get(key)
	return getattr(obj, key, None)


def _safe_iter(obj: Any) -> Any:
	"""Iterate over `obj` even if it's None — yields nothing in that case."""
	if obj is None:
		return iter(())
	try:
		return iter(obj)
	except TypeError:
		return iter(())


def _log_engine_error(doc: Any, error: Exception) -> None:
	"""Log an engine error to Frappe's Error Log, sanitizing the doc reference."""
	doctype = doc.get("doctype") if hasattr(doc, "get") else getattr(doc, "doctype", "Unknown")
	name = doc.get("name") if hasattr(doc, "get") else getattr(doc, "name", "")
	title = "OpenSalesTax engine error"
	message = f"doc={doctype}/{name}: {type(error).__name__}: {error}"
	try:
		frappe.log_error(message=message, title=title)
	except Exception:  # noqa: S110 — never let logging failure mask the original error
		pass
