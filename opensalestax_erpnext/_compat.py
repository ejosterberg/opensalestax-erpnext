# SPDX-License-Identifier: Apache-2.0
"""Cross-version compatibility shims for Frappe v15 and v16.

Isolates the few API differences between branches so the rest of the
codebase reads identically on either version.
"""

from __future__ import annotations

try:
	# Frappe v16 path
	from frappe.tests import IntegrationTestCase as FrappeTestCase
except ImportError:  # pragma: no cover
	# Frappe v15 path
	from frappe.tests.utils import FrappeTestCase  # type: ignore[no-redef]


def in_test() -> bool:
	"""Return True if the current request is running under the test harness.

	Frappe v15 exposes `frappe.flags.in_test`; v16 promoted it to
	`frappe.in_test`. This helper checks both so callers don't care.
	"""
	import frappe

	if getattr(frappe, "in_test", None):
		return True
	flags = getattr(frappe, "flags", None)
	if flags is None:
		return False
	return bool(flags.get("in_test"))


__all__ = ["FrappeTestCase", "in_test"]
