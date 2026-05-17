# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""One-shot site bootstrap â€” completes ERPNext setup wizard for integration tests."""

from __future__ import annotations

import frappe


def run() -> None:
	"""Run ERPNext's setup_complete wizard with minimal test args.

	The admin password is read from the OSTAX_TEST_ADMIN_PASSWORD env var
	(no hardcoded credential â€” keeps SonarQube + secret scanners happy).
	"""
	import os

	from erpnext.setup.setup_wizard.setup_wizard import setup_complete

	admin_password = os.environ.get("OSTAX_TEST_ADMIN_PASSWORD", "")
	if not admin_password:
		raise RuntimeError("OSTAX_TEST_ADMIN_PASSWORD env var must be set before running setup_site.run()")

	args = frappe._dict(
		{
			"language": "English",
			"country": "United States",
			"currency": "USD",
			"timezone": "America/Chicago",
			"company_name": "Test OST Co",
			"company_abbr": "OST",
			"company_tagline": "Integration test company",
			"chart_of_accounts": "Standard with Numbers",
			"fy_start_date": "2026-01-01",
			"fy_end_date": "2026-12-31",
			"setup_demo": 0,
			"full_name": "Administrator",
			"email": "admin@example.com",
			"password": admin_password,
		}
	)
	setup_complete(args)
	frappe.db.commit()
	print("Setup complete â€” Test OST Co created.")
	co = frappe.db.get_value("Company", {"name": "Test OST Co"}, "name")
	print(f"Company: {co}")
