// SPDX-License-Identifier: Apache-2.0

frappe.ui.form.on("OpenSalesTax Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), function () {
			frappe.call({
				method: "opensalestax_erpnext.opensalestax_erpnext.doctype.opensalestax_settings.opensalestax_settings.test_connection",
				callback(r) {
					if (!r || !r.message) {
						frappe.msgprint({
							title: __("Connection Test"),
							message: __("No response from server."),
							indicator: "red",
						});
						return;
					}
					const m = r.message;
					if (m.status === "ok") {
						frappe.msgprint({
							title: __("Connection OK"),
							message: __(
								"Engine reachable. Version: {0} — round-trip {1} ms",
								[m.engine_version || __("unknown"), m.rtt_ms]
							),
							indicator: "green",
						});
					} else {
						frappe.msgprint({
							title: __("Connection Failed"),
							message: m.message || __("Unknown error"),
							indicator: "red",
						});
					}
				},
			});
		});
	},
});
