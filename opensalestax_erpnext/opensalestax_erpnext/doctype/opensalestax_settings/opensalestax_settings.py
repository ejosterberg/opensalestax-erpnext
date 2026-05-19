# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""OpenSalesTax Settings Single doctype controller."""

from __future__ import annotations

import time

import frappe
from frappe import _
from frappe.model.document import Document

from opensalestax_erpnext.client_factory import build_client
from opensalestax_erpnext.exceptions import OstaxConfigError
from opensalestax_erpnext.url_validator import is_safe_url, reason_unsafe


class OpenSalesTaxSettings(Document):
	"""Controller for the OpenSalesTax Settings single doctype.

	Validates the engine URL against the SSRF allow-list whenever the
	doc is saved with `enabled = 1`. Exposes a whitelisted
	`test_connection` method for the desk-side **Test Connection** button.
	"""

	def validate(self) -> None:
		"""Reject save when configuration is inconsistent.

		Only enforces URL validation when the app is being enabled -- that
		way an admin can save a draft URL while it's still wrong without
		being blocked.
		"""
		if not self.enabled:
			return
		if not (self.base_url or "").strip():
			frappe.throw(_("Engine Base URL is required when OpenSalesTax is enabled."))

		allow_private = bool(self.allow_private_networks)
		if not is_safe_url(self.base_url, allow_private=allow_private):
			reason = reason_unsafe(self.base_url, allow_private=allow_private)
			frappe.throw(_("Engine Base URL rejected: {0}").format(reason))

		if not self.tax_account_head:
			frappe.throw(_("Tax Account Head is required when OpenSalesTax is enabled."))


@frappe.whitelist()
def test_connection() -> dict:
	"""Probe the engine and return its health.

	Returns a dict with keys: status (ok/error), message, engine_version, rtt_ms.
	"""
	try:
		settings = frappe.get_cached_doc("OpenSalesTax Settings")
	except Exception as e:
		return {"status": "error", "message": f"Settings unavailable: {e}"}

	try:
		client = build_client(settings)
	except OstaxConfigError as e:
		return {"status": "error", "message": str(e)}
	except Exception as e:
		return {"status": "error", "message": f"client build failed: {e}"}

	start = time.perf_counter()
	try:
		health = client.health()
	except Exception as e:
		return {"status": "error", "message": f"engine call failed: {e}"}
	rtt_ms = int((time.perf_counter() - start) * 1000)

	version = ""
	if isinstance(health, dict):
		version = str(health.get("version") or health.get("engine_version") or "")
	else:
		version = str(getattr(health, "version", None) or getattr(health, "engine_version", "") or "")

	return {
		"status": "ok",
		"message": "Engine reachable",
		"engine_version": version,
		"rtt_ms": rtt_ms,
	}
