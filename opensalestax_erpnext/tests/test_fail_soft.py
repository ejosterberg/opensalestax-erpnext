# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""Fail-soft / fail-strict tests for engine errors."""

from __future__ import annotations

from unittest import TestCase

from .test_apply import _patch_client_factory
from .test_gates import (
	_DocWrapper,
	_import_tax_fresh,
	_install_frappe_stub,
	_make_address,
	_make_doc,
	_make_settings,
)


def _explode(*_a, **_kw):
	raise RuntimeError("engine 500: internal error")


class TestFailSoft(TestCase):
	def test_engine_error_with_fail_soft_no_ops(self):
		settings = _make_settings(fail_soft=1)
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		_patch_client_factory(tax)
		tax._call_engine = _explode  # type: ignore[assignment]
		doc = _DocWrapper(_make_doc())
		# Should NOT raise
		tax.apply_opensalestax(doc)
		# No lines appended, original (empty) taxes preserved
		self.assertEqual(doc.taxes, [])

	def test_engine_error_with_strict_mode_throws(self):
		settings = _make_settings(fail_soft=0)
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		_patch_client_factory(tax)
		tax._call_engine = _explode  # type: ignore[assignment]
		doc = _DocWrapper(_make_doc())
		with self.assertRaises(RuntimeError) as ctx:
			tax.apply_opensalestax(doc)
		# Our stub raises RuntimeError via frappe.throw
		self.assertIn("engine", str(ctx.exception).lower())

	def test_config_error_with_fail_soft_no_ops(self):
		"""Missing base_url in build_client â†’ OstaxConfigError â†’ soft no-op."""
		settings = _make_settings(fail_soft=1, base_url="")
		_install_frappe_stub(settings, address_map={"addr1": _make_address()})
		tax = _import_tax_fresh()
		doc = _DocWrapper(_make_doc())
		# Should NOT raise â€” config error caught by fail_soft path
		tax.apply_opensalestax(doc)
		self.assertEqual(doc.taxes, [])
