# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""App install hook -- creates default OpenSalesTax Settings row."""

from __future__ import annotations

import frappe


def after_install() -> None:
	"""Create the default OpenSalesTax Settings record on first install.

	Single doctypes auto-create on first read in modern Frappe, but
	explicit creation is more discoverable and lets us set defaults.
	"""
	doctype = "OpenSalesTax Settings"
	if frappe.db.exists(doctype, doctype):
		return

	s = frappe.new_doc(doctype)
	s.enabled = 0
	s.cache_ttl_seconds = 86400
	s.fail_soft = 1
	s.verify_ssl = 1
	s.treat_item_tax_template_as_override = 1
	s.allow_private_networks = 0
	s.insert(ignore_permissions=True)
