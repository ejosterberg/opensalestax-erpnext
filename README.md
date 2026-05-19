# OpenSalesTax for ERPNext

> Destination-based **US sales tax** for [ERPNext](https://erpnext.com) — computed live by the [OpenSalesTax](https://github.com/ejosterberg/open-sales-tax) engine and applied automatically to Quotations, Sales Orders, and Sales Invoices.

> [!IMPORTANT]
> **Calculation only.** This app calculates sales tax. It does **not** file returns and does **not** remit payments. The merchant is solely responsible for tax-collection accuracy and remittance to the appropriate jurisdictions. Verify against your state Department of Revenue before remitting.

## What this is

A Frappe app that hooks ERPNext's tax-computation lifecycle and replaces the manual "Sales Taxes and Charges Template" workflow with destination-based calculation driven by a self-hosted OpenSalesTax engine. No per-transaction fees, no third-party SaaS contract — you point it at your own OpenSalesTax instance and it works.

Designed for **small US-based businesses** running ERPNext who currently either (a) miscompute tax because they're picking a single fixed template, or (b) pay Avalara/TaxJar a per-transaction fee for accuracy they could get for free.

## Compatibility

| Frappe / ERPNext | Branch | Python | Status |
|---|---|---|---|
| **v16** (current stable, GA 2026-01-12) | `version-16` | 3.14 | ✅ Supported |
| **v15** (previous stable) | `version-15` | 3.10–3.14 | ✅ Supported |
| v14 (maintenance) | — | — | ❌ Not supported |

## Install

```bash
# In your bench directory:
bench get-app https://github.com/ejosterberg/opensalestax-erpnext --branch version-15
bench --site <your-site> install-app opensalestax_erpnext
bench restart
```

For ERPNext v16, swap `--branch version-15` → `--branch version-16`.

## Configure

1. Open the ERPNext desk → search **OpenSalesTax Settings**.
2. Fill in:
   - **Engine Base URL** — your OpenSalesTax instance (e.g. `https://tax.mycompany.com` or `http://10.0.0.50:8080` if running on your LAN)
   - **API Key** (optional) — Bearer token if your engine requires auth
   - **Tax Account Head** — the GL account tax lines should post to (typically "Sales Tax Payable" or similar liability account)
3. Click **Test Connection** — should show the engine version and round-trip time.
4. Tick **Enable OpenSalesTax**.
5. Save.

For LAN-hosted engines (RFC-1918 addresses like `10.x`, `192.168.x`), also tick **Allow Private Networks** in the Advanced section.

## Verify

Create a Sales Invoice with:
- A US customer
- A shipping address that has a 5-digit ZIP code
- `Currency = USD`
- At least one taxable item

Save the invoice. Under the **Taxes and Charges** table you should see one or more lines like:

```
OpenSalesTax — Minnesota          0.06875   $6.88
OpenSalesTax — Hennepin County    0.00150   $0.15
OpenSalesTax — Minneapolis        0.00500   $0.50
OpenSalesTax — Metro Transit      0.00500   $0.50
```

…with `grand_total` reflecting the computed tax.

## How it works

The app registers `doc_events: validate` hooks for `Sales Invoice`, `Sales Order`, and `Quotation`. When a document is saved:

1. Gate checks: app enabled? Currency = USD? Ship-to country = United States? Valid 5-digit ZIP?
2. Cache lookup keyed on ZIP (24h TTL, configurable).
3. On cache miss, call the engine's `POST /v1/calculate` endpoint via the `opensalestax` Python SDK.
4. Clear `doc.taxes` and append per-jurisdiction lines with `charge_type="Actual"`.
5. Call `erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals(doc)` to refresh `grand_total`.

When any gate fails, the hook silently no-ops and ERPNext's normal template-based tax math runs as before.

## Behavior matrix

| Condition | Behavior |
|---|---|
| `enabled = 0` | Hook no-ops; user's tax template applies. |
| `doc.currency ≠ USD` | Hook no-ops; user's tax template applies. |
| Ship-to country ≠ United States | Hook no-ops. |
| Missing or non-5-digit ZIP | Hook no-ops. |
| Item has `item_tax_template` set | Item excluded from OST compute (respects merchant override). Toggleable via Settings. |
| Engine unreachable + `fail_soft = 1` | Silent fallback to user's template. Error logged. |
| Engine unreachable + `fail_soft = 0` | Save throws with a clear error message. |
| `nexus_states` set AND ship-to state NOT in list | Hook no-ops; ERPNext's default tax (typically: no tax) applies. v0.2 (CP-3). |
| `nexus_states` set AND ship-to state missing/unresolvable | Hook no-ops (fail-closed). v0.2 (CP-3). |

### Per-state nexus filter (CP-3, v0.2.0)

Most US merchants only collect sales tax in a small set of states. Without
a filter, every invoice goes to the engine even when the merchant has
no collection obligation for the destination.

In **OpenSalesTax Settings → Per-State Nexus Filter**, set
`Nexus States (comma-separated)` to e.g. `MN,WI,IA` to restrict engine
round-trips to invoices shipping to those states. Carts to any other
state short-circuit to ERPNext's default tax behavior (no tax line).

Leave blank to call the engine for every US/USD invoice (pre-v0.2
behavior — fully backward compatible).

ERPNext stores `Address.state` as free text; we accept the 2-letter
form (`MN`) directly and normalize the 50 full state names
(`Minnesota` → `MN`). Anything that doesn't resolve to a 2-letter US
code with the filter active is fail-closed (no engine call).

Brings this connector in line with WooCommerce v0.5, Vendure v1.2,
and Odoo v0.3, which already shipped this filter.

## Caveats

- **US only.** ERPNext supports multi-currency but OpenSalesTax is USD-only (engine constitution §5).
- **Sales side only in v0.1.** Purchase Invoice / use-tax accrual is deferred to v0.2.
- **Compose with other tax apps at your own risk.** If you have TaxJar, Avalara, or another tax-calculator app installed and `enabled`, behavior is undefined. Install only one tax provider.
- **Per-product category mapping is not in v0.1.** When the engine adds product-category gating, this will follow.

## Security

This app:

- Stores the engine API key as a Frappe `Password` field (encrypted at rest).
- Validates the engine `base_url` against an SSRF allow-list — rejects loopback, link-local, multicast, broadcast, RFC-1918 private, and CGNAT addresses unless **Allow Private Networks** is explicitly enabled (for LAN deployments).
- Sends only the ZIP code to the engine — no customer name, no street, no email.
- Defaults SSL verification ON.
- Permission-gates Settings doctype to `System Manager` and `Accounts Manager` only.

A full security review is at [`docs/SECURITY-REVIEW.md`](docs/SECURITY-REVIEW.md). Responsible disclosure: see [`SECURITY.md`](SECURITY.md).

## Architecture deep-dive

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full hook-flow walkthrough, including the rationale for picking `validate` over `before_save` / `before_validate` / `override_doctype_class`.

## Development

```bash
# In a Frappe bench at the version-15 or version-16 branch:
bench get-app file:///path/to/your/local/clone/opensalestax-erpnext --branch version-15
bench --site test.localhost install-app opensalestax_erpnext
bench --site test.localhost run-tests --app opensalestax_erpnext
```

For unit-tests outside a bench:
```bash
pip install -r requirements-dev.txt
pytest
```

Linting:
```bash
ruff check .
ruff format --check .
mypy opensalestax_erpnext/
```

## Contributing

Contributions welcome. Every commit must be DCO-signed off (`git commit -s`). See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Dual-licensed under your choice of [Apache-2.0](LICENSE-APACHE.txt) OR [GPL-2.0-or-later](LICENSE-GPL.txt). See [`LICENSE`](LICENSE).

## Related

- [OpenSalesTax engine](https://github.com/ejosterberg/open-sales-tax) — the tax-calculation engine this app integrates with
- [opensalestax-python SDK](https://github.com/ejosterberg/opensalestax-python) — the Python HTTP client this app depends on
- Other OpenSalesTax connectors:
  [WooCommerce](https://github.com/ejosterberg/opensalestax-woocommerce),
  [Medusa](https://github.com/ejosterberg/opensalestax-medusa),
  [Odoo](https://github.com/ejosterberg/opensalestax-odoo)

## Acknowledgements

The hook pattern follows the official [`frappe/taxjar_integration`](https://github.com/frappe/taxjar_integration) (MIT) as a convention reference. Apache 2.0 compatibility analysis verified the GPL ERPNext / Apache plugin pattern is structurally identical to the MIT TaxJar integration.
