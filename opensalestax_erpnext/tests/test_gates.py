# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""Gate-check unit tests for the tax hook.

These tests stub `frappe` enough to exercise tax.py's pure logic
without needing a real Frappe bench. The full integration test
suite runs via `bench run-tests`.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest import TestCase


def _make_settings(**overrides):
	defaults = {
		"enabled": 1,
		"base_url": "https://tax.example.com",
		"api_key": None,
		"verify_ssl": 1,
		"cache_ttl_seconds": 86400,
		"fail_soft": 1,
		"tax_account_head": "Sales Tax - Co",
		"shipping_account_head": None,
		"treat_item_tax_template_as_override": 1,
		"allow_private_networks": 0,
	}
	defaults.update(overrides)
	return SimpleNamespace(**defaults)


def _make_address(country="United States", pincode="55401"):
	return {"country": country, "pincode": pincode}


def _make_doc(currency="USD", items=None, shipping_address_name="addr1", company="Co"):
	return {
		"doctype": "Sales Invoice",
		"name": "SINV-0001",
		"company": company,
		"currency": currency,
		"shipping_address_name": shipping_address_name,
		"customer_address": None,
		"items": items or [{"item_code": "WIDGET", "qty": 1, "rate": 100, "amount": 100}],
		"taxes": [],
	}


class _DocWrapper:
	"""Thin wrapper that mimics the bits of `frappe.Document` the hook touches."""

	def __init__(self, data):
		self._data = data

	def get(self, key, default=None):
		return self._data.get(key, default)

	def set(self, key, value):
		self._data[key] = value

	def append(self, key, row):
		self._data.setdefault(key, []).append(row)

	@property
	def taxes(self):
		return self._data.get("taxes", [])

	def __getattr__(self, name):
		if name.startswith("_"):
			raise AttributeError(name)
		return self._data.get(name)


class _DoesNotExistError(Exception):
	pass


class _StubCache:
	"""In-memory stand-in for frappe.cache()."""

	def __init__(self):
		self.store: dict[str, str] = {}

	def get_value(self, key):
		return self.store.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.store[key] = value

	def get_keys(self, pattern):
		if pattern.endswith("*"):
			prefix = pattern[:-1]
			return [k for k in self.store if k.startswith(prefix)]
		return [k for k in self.store if k == pattern]

	def delete_keys(self, keys):
		for k in keys:
			self.store.pop(k, None)


def _install_frappe_stub(settings, address_map=None):
	"""Inject a fake `frappe` module that returns our settings + addresses."""
	address_map = address_map or {}
	cache_store = _StubCache()

	def _get_cached_doc(doctype, name=None):
		if doctype == "OpenSalesTax Settings":
			return settings
		if doctype == "Address":
			if name in address_map:
				return address_map[name]
			raise _DoesNotExistError(f"Address {name}")
		raise _DoesNotExistError(f"Unknown doctype {doctype}")

	def _get_cached_value(*_a, **_kw):
		return "Main"

	def _log_error(*_a, **_kw):
		return None

	def _throw(msg):
		raise RuntimeError(str(msg))

	frappe_stub = SimpleNamespace(
		get_cached_doc=_get_cached_doc,
		get_cached_value=_get_cached_value,
		log_error=_log_error,
		throw=_throw,
		cache=lambda: cache_store,
		DoesNotExistError=_DoesNotExistError,
		flags=SimpleNamespace(in_test=True, get=lambda k, default=None: True if k == "in_test" else default),
		in_test=True,
		_=lambda s: s,
	)
	# `_` is a Frappe translation helper; tax.py imports it via `from frappe import _`
	# so we expose it on the module too.
	frappe_stub._ = lambda s: s
	sys.modules["frappe"] = frappe_stub  # type: ignore[assignment]
	return frappe_stub


def _import_tax_fresh():
	for name in list(sys.modules):
		if name.startswith("opensalestax_erpnext"):
			del sys.modules[name]
	import opensalestax_erpnext.tax as tax_module

	return tax_module


class TestGates(TestCase):
	def test_disabled_no_ops(self):
		settings = _make_settings(enabled=0)
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		tax.apply_opensalestax(doc)
		self.assertEqual(doc.taxes, [])

	def test_non_usd_no_ops(self):
		settings = _make_settings()
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc(currency="EUR"))
		tax.apply_opensalestax(doc)
		self.assertEqual(doc.taxes, [])

	def test_non_us_shipping_no_ops(self):
		settings = _make_settings()
		_install_frappe_stub(settings, address_map={"addr1": _make_address(country="Canada")})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		tax.apply_opensalestax(doc)
		self.assertEqual(doc.taxes, [])

	def test_missing_address_no_ops(self):
		settings = _make_settings()
		_install_frappe_stub(settings, address_map={})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc(shipping_address_name=None))
		tax.apply_opensalestax(doc)
		self.assertEqual(doc.taxes, [])

	def test_missing_zip_no_ops(self):
		settings = _make_settings()
		_install_frappe_stub(settings, address_map={"addr1": _make_address(pincode="")})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		tax.apply_opensalestax(doc)
		self.assertEqual(doc.taxes, [])

	def test_malformed_zip_no_ops(self):
		settings = _make_settings()
		# Non-US 5-letter postal code
		_install_frappe_stub(settings, address_map={"addr1": _make_address(pincode="SW1A1")})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		tax.apply_opensalestax(doc)
		self.assertEqual(doc.taxes, [])

	def test_zip_plus_four_reduces_to_5_digit(self):
		"""A ZIP+4 like '55401-1234' should be accepted and reduced to '55401'."""
		settings = _make_settings(enabled=0)  # disabled to avoid actual engine call
		# Re-enable just to test the gate path
		_install_frappe_stub(settings, address_map={"addr1": _make_address(pincode="55401-1234")})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		# With enabled=0 we no-op anyway; check the helper directly:
		self.assertEqual(tax._extract_zip(doc), "55401")


# --- CP-3 per-state nexus filter (v0.2.0) -----------------------------------


def _make_address_with_state(state, country="United States", pincode="55401"):
	return {"country": country, "pincode": pincode, "state": state}


class TestNexusFilter(TestCase):
	def test_parse_nexus_states_empty(self):
		_install_frappe_stub(_make_settings())
		tax = _import_tax_fresh()
		self.assertEqual(tax._parse_nexus_states(""), [])
		self.assertEqual(tax._parse_nexus_states("   "), [])

	def test_parse_nexus_states_comma_separated(self):
		_install_frappe_stub(_make_settings())
		tax = _import_tax_fresh()
		self.assertEqual(tax._parse_nexus_states("MN,WI,IA"), ["MN", "WI", "IA"])

	def test_parse_nexus_states_normalizes_and_dedupes(self):
		_install_frappe_stub(_make_settings())
		tax = _import_tax_fresh()
		self.assertEqual(
			tax._parse_nexus_states("mn, wi, MN, ia, wi"),
			["MN", "WI", "IA"],
		)

	def test_parse_nexus_states_drops_malformed(self):
		_install_frappe_stub(_make_settings())
		tax = _import_tax_fresh()
		self.assertEqual(
			tax._parse_nexus_states("MN, Minnesota, 12, ,WI"),
			["MN", "WI"],
		)

	def test_extract_state_two_letter_code(self):
		_install_frappe_stub(
			_make_settings(), address_map={"addr1": _make_address_with_state("MN")}
		)
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		self.assertEqual(tax._extract_state(doc), "MN")

	def test_extract_state_full_name_normalized(self):
		_install_frappe_stub(
			_make_settings(),
			address_map={"addr1": _make_address_with_state("Minnesota")},
		)
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		self.assertEqual(tax._extract_state(doc), "MN")

	def test_extract_state_lowercase_normalized(self):
		_install_frappe_stub(
			_make_settings(), address_map={"addr1": _make_address_with_state("mn")}
		)
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		self.assertEqual(tax._extract_state(doc), "MN")

	def test_extract_state_returns_none_when_missing(self):
		_install_frappe_stub(_make_settings(), address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		self.assertIsNone(tax._extract_state(doc))

	def test_filter_disabled_when_nexus_states_empty(self):
		settings = _make_settings(nexus_states="")
		_install_frappe_stub(
			settings, address_map={"addr1": _make_address_with_state("MN")}
		)
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		self.assertFalse(tax._should_skip_for_nexus(doc, settings))

	def test_filter_allows_listed_state(self):
		settings = _make_settings(nexus_states="MN,WI,IA")
		_install_frappe_stub(
			settings, address_map={"addr1": _make_address_with_state("MN")}
		)
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		self.assertFalse(tax._should_skip_for_nexus(doc, settings))

	def test_filter_blocks_out_of_state(self):
		settings = _make_settings(nexus_states="MN,WI,IA")
		_install_frappe_stub(
			settings, address_map={"addr1": _make_address_with_state("CA")}
		)
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		self.assertTrue(tax._should_skip_for_nexus(doc, settings))

	def test_filter_fails_closed_on_unresolvable_state(self):
		settings = _make_settings(nexus_states="MN,WI,IA")
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})  # no state
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		self.assertTrue(tax._should_skip_for_nexus(doc, settings))

	def test_apply_short_circuits_out_of_state(self):
		settings = _make_settings(nexus_states="MN,WI,IA")
		_install_frappe_stub(
			settings, address_map={"addr1": _make_address_with_state("CA")}
		)
		tax = _import_tax_fresh()
		# Stub _fetch_rate to fail loudly if called — it shouldn't be.
		tax._fetch_rate = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("engine called"))
		doc = _DocWrapper(_make_doc())
		tax.apply_opensalestax(doc)  # must not raise
		self.assertEqual(doc.taxes, [])
