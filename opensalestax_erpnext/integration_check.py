# SPDX-License-Identifier: Apache-2.0
"""Live integration check.

Invoked from a bench console session via:

    bench --site <site> execute opensalestax_erpnext.integration_check.run

Not a unit test — exercises the full end-to-end path against a live
OpenSalesTax engine. Used for manual / on-VM verification only.
"""

from __future__ import annotations

import datetime
import json

import frappe


def _find_account(filters: dict, fallback_filters: dict | None = None) -> str | None:
	acc = frappe.db.get_value("Account", filters, "name")
	if acc:
		return acc
	if fallback_filters:
		return frappe.db.get_value("Account", fallback_filters, "name")
	return None


def run() -> None:
	# Console-mode locale fix — num2words needs frappe.local.lang
	frappe.local.lang = "en"

	results: dict = {}

	# 1. Verify doctype installed
	results["doctype_installed"] = bool(frappe.db.exists("DocType", "OpenSalesTax Settings"))

	# 2. Configure Settings
	settings = frappe.get_doc("OpenSalesTax Settings")
	settings.enabled = 1
	settings.base_url = "http://10.32.161.126:8080"
	settings.cache_ttl_seconds = 86400
	settings.fail_soft = 1
	settings.verify_ssl = 0
	settings.allow_private_networks = 1
	settings.treat_item_tax_template_as_override = 1
	tax_acc = _find_account(
		{"account_type": "Tax", "is_group": 0},
		{"root_type": "Liability", "is_group": 0},
	)
	settings.tax_account_head = tax_acc
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	results["settings_saved"] = True
	results["tax_account_head"] = tax_acc

	# 3. Test connection
	from opensalestax_erpnext.opensalestax_erpnext.doctype.opensalestax_settings.opensalestax_settings import (
		test_connection,
	)

	results["test_connection"] = test_connection()

	# 4. Customer + US Address
	co = frappe.db.get_value("Company", {}, "name")
	results["company"] = co

	cust_name = "_Test OSX Customer"
	if not frappe.db.exists("Customer", cust_name):
		cust = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": cust_name,
				"customer_type": "Company",
				"customer_group": "Commercial",
				"territory": "United States",
			}
		)
		cust.insert(ignore_permissions=True)
	results["customer_exists"] = True

	addr_full_name = "_Test OSX Shipping-Shipping"
	if not frappe.db.exists("Address", addr_full_name):
		addr = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test OSX Shipping",
				"address_type": "Shipping",
				"address_line1": "1 Main St",
				"city": "Minneapolis",
				"state": "MN",
				"country": "United States",
				"pincode": "55401",
				"links": [{"link_doctype": "Customer", "link_name": cust_name}],
			}
		)
		addr.insert(ignore_permissions=True)
	else:
		addr = frappe.get_doc("Address", addr_full_name)
	results["address_name"] = addr.name

	# 5. Item
	item_code = "_Test OSX Widget"
	if not frappe.db.exists("Item", item_code):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": "Widget",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"include_item_in_manufacturing": 0,
			}
		)
		item.insert(ignore_permissions=True)
	results["item_exists"] = True

	# 6. US/USD Sales Invoice — hook should fire
	income_acc = _find_account(
		{"account_type": "Income Account", "is_group": 0, "company": co},
		{"root_type": "Income", "is_group": 0, "company": co},
	)
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": cust_name,
			"company": co,
			"currency": "USD",
			"shipping_address_name": addr.name,
			"posting_date": datetime.date.today().isoformat(),
			"due_date": datetime.date.today().isoformat(),
			"items": [{"item_code": item_code, "qty": 1, "rate": 100.0, "income_account": income_acc}],
		}
	)
	si.insert(ignore_permissions=True)
	results["si_name"] = si.name
	results["si_currency"] = si.currency
	results["si_net_total"] = float(si.net_total or 0)
	results["si_grand_total"] = float(si.grand_total or 0)
	results["si_taxes"] = [
		{
			"description": t.description,
			"tax_amount": float(t.tax_amount or 0),
			"charge_type": t.charge_type,
		}
		for t in si.taxes
	]
	results["si_total_tax"] = sum(float(t.tax_amount or 0) for t in si.taxes)

	# 7. Non-USD invoice — hook should no-op
	si2 = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": cust_name,
			"company": co,
			"currency": "EUR",
			"conversion_rate": 1.10,
			"shipping_address_name": addr.name,
			"posting_date": datetime.date.today().isoformat(),
			"due_date": datetime.date.today().isoformat(),
			"items": [{"item_code": item_code, "qty": 1, "rate": 100.0, "income_account": income_acc}],
		}
	)
	try:
		si2.insert(ignore_permissions=True)
		results["non_usd_si"] = {
			"name": si2.name,
			"currency": si2.currency,
			"taxes_count": len(si2.taxes),
		}
	except Exception as e:
		results["non_usd_si"] = {"error": str(e)}

	frappe.db.commit()

	print("=" * 70)
	print("INTEGRATION CHECK RESULTS")
	print("=" * 70)
	print(json.dumps(results, indent=2, default=str))
	print("=" * 70)
