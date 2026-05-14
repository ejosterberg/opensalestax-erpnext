# SPDX-License-Identifier: Apache-2.0
"""Cache layer unit tests — mocks frappe.cache()."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock


class _InMemoryCache:
	"""Minimal stand-in for the frappe.cache() interface used by cache.py."""

	def __init__(self):
		self.store: dict[str, str] = {}

	def get_value(self, key):
		return self.store.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.store[key] = value

	def get_keys(self, pattern):
		# Naive pattern: only supports trailing '*'
		if pattern.endswith("*"):
			prefix = pattern[:-1]
			return [k for k in self.store if k.startswith(prefix)]
		return [k for k in self.store if k == pattern]

	def delete_keys(self, keys):
		for k in keys:
			self.store.pop(k, None)


def _install_frappe_stub() -> tuple[_InMemoryCache, object]:
	"""Install a minimal `frappe` module so cache.py can be imported."""
	cache = _InMemoryCache()
	mod = SimpleNamespace(cache=MagicMock(return_value=cache))
	sys.modules["frappe"] = mod  # type: ignore[assignment]
	return cache, mod


class TestCache(TestCase):
	def setUp(self):
		self.cache, self.frappe_stub = _install_frappe_stub()
		# Re-import cache module fresh so it binds against our stub
		if "opensalestax_erpnext.cache" in sys.modules:
			del sys.modules["opensalestax_erpnext.cache"]
		import opensalestax_erpnext.cache as cache_module

		self.module = cache_module

	def test_miss_returns_none(self):
		self.assertIsNone(self.module.get("55401"))

	def test_round_trip(self):
		payload = {"jurisdictions": [{"name": "MN", "rate_pct": "6.875"}], "engine_version": "0.54"}
		self.module.put("55401", payload, ttl_seconds=86400)
		got = self.module.get("55401")
		self.assertEqual(got, payload)

	def test_corrupt_entry_treated_as_miss(self):
		# Write a non-JSON string directly
		self.cache.store["ostax:rate:55401"] = "not-json{{"
		self.assertIsNone(self.module.get("55401"))

	def test_zero_ttl_skips_write(self):
		self.module.put("55401", {"x": 1}, ttl_seconds=0)
		self.assertIsNone(self.module.get("55401"))

	def test_negative_ttl_skips_write(self):
		self.module.put("55401", {"x": 1}, ttl_seconds=-5)
		self.assertIsNone(self.module.get("55401"))

	def test_flush_removes_only_ostax_keys(self):
		self.cache.store["ostax:rate:55401"] = json.dumps({"a": 1})
		self.cache.store["ostax:rate:90210"] = json.dumps({"b": 2})
		self.cache.store["other:unrelated:key"] = "leave-me-alone"
		removed = self.module.flush()
		self.assertEqual(removed, 2)
		self.assertIn("other:unrelated:key", self.cache.store)

	def test_dict_passthrough(self):
		# If the cache backend returns a dict instead of JSON, accept it
		self.cache.store["ostax:rate:55401"] = {"already": "decoded"}  # type: ignore[assignment]
		self.assertEqual(self.module.get("55401"), {"already": "decoded"})
