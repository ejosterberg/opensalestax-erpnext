# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""Happy-path unit tests for the tax hook."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

from .test_gates import _DocWrapper, _install_frappe_stub, _make_address, _make_doc, _make_settings


def _fake_engine_response():
	return SimpleNamespace(
		jurisdictions=[
			{"name": "Minnesota", "rate_pct": "6.875", "kind": "state"},
			{"name": "Hennepin County", "rate_pct": "0.15", "kind": "county"},
			{"name": "Minneapolis", "rate_pct": "0.5", "kind": "city"},
			{"name": "Metro Transit", "rate_pct": "0.5", "kind": "district"},
			{"name": "Special District 1", "rate_pct": "0.5", "kind": "district"},
			{"name": "Special District 2", "rate_pct": "0.5", "kind": "district"},
		],
		engine_version="0.54.1",
	)


def _patch_engine_call(tax_module):
	"""Replace _call_engine + _refresh_totals with no-op stubs."""

	def _fake_call_engine(client, zip5, taxable_total):
		return _fake_engine_response()

	def _fake_refresh_totals(doc):
		# We don't have erpnext in unit-test scope, so skip the real call.
		# The behavior we want to test is the tax-line appending; totals
		# math is covered by the bench integration test.
		return None

	tax_module._call_engine = _fake_call_engine  # type: ignore[assignment]
	tax_module._refresh_totals = _fake_refresh_totals  # type: ignore[assignment]


def _patch_client_factory(tax_module):
	"""Replace the SDK client builder with a stub."""

	def _fake_build_client(settings):
		return MagicMock()

	tax_module.build_client = _fake_build_client  # type: ignore[assignment]


class TestApply(TestCase):
	def _setup(self, *, items=None, address=None, settings_overrides=None):
		settings = _make_settings(**(settings_overrides or {}))
		address = address or _make_address()
		_install_frappe_stub(settings, address_map={"addr1": address})
		from .test_gates import _import_tax_fresh

		tax = _import_tax_fresh()
		_patch_engine_call(tax)
		_patch_client_factory(tax)
		doc = _DocWrapper(_make_doc(items=items))
		return tax, doc, settings

	def test_happy_path_appends_per_jurisdiction_lines(self):
		tax, doc, _settings = self._setup()
		tax.apply_opensalestax(doc)
		# 6 jurisdictions in fake response
		self.assertEqual(len(doc.taxes), 6)
		# Each line has the expected structure
		for line in doc.taxes:
			self.assertEqual(line["charge_type"], "Actual")
			self.assertEqual(line["account_head"], "Sales Tax - Co")
			self.assertTrue(line["description"].startswith("OpenSalesTax"))
			self.assertGreater(line["tax_amount"], 0)

	def test_existing_template_lines_replaced(self):
		tax, doc, _settings = self._setup()
		# Pre-populate with template lines
		doc._data["taxes"] = [
			{
				"charge_type": "On Net Total",
				"account_head": "Sales Tax - Co",
				"description": "Flat 7% tax",
				"rate": 7.0,
			}
		]
		tax.apply_opensalestax(doc)
		# Template line should be gone; 6 OST lines instead
		self.assertEqual(len(doc.taxes), 6)
		for line in doc.taxes:
			self.assertNotIn("Flat 7%", line["description"])

	def test_total_tax_amount_matches_expected_rate(self):
		"""Sum of per-jurisdiction amounts == taxable * combined rate."""
		tax, doc, _settings = self._setup()
		tax.apply_opensalestax(doc)
		total = sum(line["tax_amount"] for line in doc.taxes)
		# Combined rate from fake response: 6.875 + 0.15 + 0.5*4 = 9.025%
		# $100 * 9.025% = $9.025 â†’ rounded per-line to 0.01 may differ slightly
		self.assertAlmostEqual(total, 9.03, places=2)

	def test_multi_item_invoice(self):
		items = [
			{"item_code": "WIDGET", "qty": 2, "rate": 50, "amount": 100},
			{"item_code": "GIZMO", "qty": 1, "rate": 50, "amount": 50},
		]
		tax, doc, _settings = self._setup(items=items)
		tax.apply_opensalestax(doc)
		total = sum(line["tax_amount"] for line in doc.taxes)
		# $150 * 9.025% = $13.5375 â†’ rounded per-jurisdiction at 2 decimals
		# (ROUND_HALF_EVEN) drifts ~$0.01 from the math total. Accept Â±$0.05.
		self.assertAlmostEqual(total, 13.54, delta=0.05)

	def test_empty_engine_jurisdictions_leaves_taxes_unchanged(self):
		tax, doc, _settings = self._setup()
		doc._data["taxes"] = [{"charge_type": "On Net Total", "rate": 7.0, "description": "existing"}]

		def _empty_call_engine(*_a, **_kw):
			return SimpleNamespace(jurisdictions=[], engine_version="0.54")

		tax._call_engine = _empty_call_engine  # type: ignore[assignment]
		# Force cache miss by flushing the in-test cache
		from opensalestax_erpnext import cache

		try:
			cache.flush()
		except Exception:  # noqa: S110 â€” best-effort test-cleanup helper
			pass
		tax.apply_opensalestax(doc)
		# Engine returned no jurisdictions â€” existing template line preserved
		self.assertEqual(len(doc.taxes), 1)
		self.assertEqual(doc.taxes[0]["description"], "existing")
