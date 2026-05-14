# SPDX-License-Identifier: Apache-2.0
"""Diagnostic helper — survey the site state on a fresh ERPNext install."""

from __future__ import annotations

import frappe


def run() -> None:
	co_list = frappe.get_all("Company", fields=["name", "default_currency", "country", "abbr"])
	print(f"Companies: {co_list}")
	if not co_list:
		print("No companies — site setup not completed. ERPNext needs a company before tax accounts exist.")
		return
	co = co_list[0]["name"]

	print(f"\n--- Accounts in {co} ---")
	accs = frappe.get_all(
		"Account",
		filters={"company": co},
		fields=["name", "account_type", "root_type", "is_group"],
		limit=200,
	)
	for a in accs[:50]:
		print(f"  {a['root_type']:12s} {a['account_type'] or '-':18s} group={a['is_group']} {a['name']}")
	print(f"... ({len(accs)} total)")

	# Surface tax accounts specifically
	tax_accs = [a for a in accs if a["account_type"] == "Tax" and not a["is_group"]]
	print(f"\nTax accounts (account_type=Tax, leaf): {[a['name'] for a in tax_accs]}")

	# Surface income accounts
	income_accs = [a for a in accs if a["account_type"] == "Income Account" and not a["is_group"]]
	print(f"Income accounts: {[a['name'] for a in income_accs][:5]}...")

	# Customer groups
	cgs = frappe.get_all("Customer Group", fields=["name"])
	print(f"\nCustomer Groups: {[c['name'] for c in cgs]}")

	# Territories
	terrs = frappe.get_all("Territory", fields=["name"])
	print(f"Territories: {[t['name'] for t in terrs]}")
