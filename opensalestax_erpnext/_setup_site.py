# SPDX-License-Identifier: Apache-2.0
"""One-shot site bootstrap — completes ERPNext setup wizard for integration tests."""

from __future__ import annotations

import frappe


def run() -> None:
	from erpnext.setup.setup_wizard.setup_wizard import setup_complete

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
			"password": "admin",
		}
	)
	setup_complete(args)
	frappe.db.commit()
	print("Setup complete — Test OST Co created.")
	co = frappe.db.get_value("Company", {"name": "Test OST Co"}, "name")
	print(f"Company: {co}")
