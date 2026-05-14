# SPDX-License-Identifier: Apache-2.0
"""Frappe app hooks for opensalestax_erpnext.

Registers doc_events for Sales Invoice / Sales Order / Quotation
so OpenSalesTax replaces the user's tax template at validate-time.
"""

from . import __version__ as app_version  # noqa: F401  (re-exported for Frappe)

app_name = "opensalestax_erpnext"
app_title = "OpenSalesTax for ERPNext"
app_publisher = "Eric Osterberg"
app_description = "Destination-based US sales tax via the OpenSalesTax engine"
app_email = "ejosterberg@gmail.com"
app_license = "apache-2.0"
required_apps = ["erpnext"]

# Document events
# - validate: replaces tax template with OpenSalesTax computation
# - on_submit / on_cancel: audit-log slots (no-op in v0.1; reserved for v0.2)
doc_events = {
	"Sales Invoice": {
		"validate": "opensalestax_erpnext.tax.apply_opensalestax",
		"on_submit": "opensalestax_erpnext.audit.record_submission",
		"on_cancel": "opensalestax_erpnext.audit.record_cancellation",
	},
	"Sales Order": {
		"validate": "opensalestax_erpnext.tax.apply_opensalestax",
	},
	"Quotation": {
		"validate": "opensalestax_erpnext.tax.apply_opensalestax",
	},
}

# Install hook — creates default Settings row
after_install = "opensalestax_erpnext.install.after_install"
