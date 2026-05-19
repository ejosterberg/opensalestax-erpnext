# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""Item Tax Template precedence tests."""

from __future__ import annotations

from unittest import TestCase

from .test_apply import _patch_client_factory, _patch_engine_call
from .test_gates import (
	_DocWrapper,
	_import_tax_fresh,
	_install_frappe_stub,
	_make_address,
	_make_doc,
	_make_settings,
)


class TestItemTaxTemplatePrecedence(TestCase):
	def test_item_with_template_excluded_from_compute_by_default(self):
		items = [
			{"item_code": "TAXABLE", "qty": 1, "rate": 100, "amount": 100, "item_tax_template": None},
			{
				"item_code": "EXEMPT",
				"qty": 1,
				"rate": 50,
				"amount": 50,
				"item_tax_template": "Exempt - Food",
			},
		]
		settings = _make_settings(treat_item_tax_template_as_override=1)
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		_patch_engine_call(tax)
		_patch_client_factory(tax)
		doc = _DocWrapper(_make_doc(items=items))
		taxable_total, taxable = tax._collect_taxable_items(doc, settings)
		# Only the first item (no template) is included
		self.assertEqual(taxable_total, 100.0)
		self.assertEqual(len(taxable), 1)
		self.assertEqual(taxable[0]["item_code"], "TAXABLE")

	def test_item_with_template_included_when_override_disabled(self):
		items = [
			{"item_code": "TAXABLE", "qty": 1, "rate": 100, "amount": 100, "item_tax_template": None},
			{"item_code": "EXEMPT", "qty": 1, "rate": 50, "amount": 50, "item_tax_template": "Exempt - Food"},
		]
		settings = _make_settings(treat_item_tax_template_as_override=0)
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		_patch_engine_call(tax)
		_patch_client_factory(tax)
		doc = _DocWrapper(_make_doc(items=items))
		taxable_total, taxable = tax._collect_taxable_items(doc, settings)
		# Both items included when override is disabled
		self.assertEqual(taxable_total, 150.0)
		self.assertEqual(len(taxable), 2)

	def test_no_taxable_items_no_op(self):
		"""All items have item_tax_template -> no engine call, no tax lines."""
		items = [
			{"item_code": "EXEMPT1", "qty": 1, "rate": 100, "amount": 100, "item_tax_template": "Exempt"},
			{"item_code": "EXEMPT2", "qty": 1, "rate": 50, "amount": 50, "item_tax_template": "Exempt"},
		]
		settings = _make_settings(treat_item_tax_template_as_override=1)
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		_patch_engine_call(tax)
		_patch_client_factory(tax)
		doc = _DocWrapper(_make_doc(items=items))
		tax.apply_opensalestax(doc)
		# No OST lines appended -- every item carried an override
		self.assertEqual(doc.taxes, [])
