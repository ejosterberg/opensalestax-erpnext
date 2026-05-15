# Constitution — opensalestax-erpnext

> Non-negotiable principles. Read before writing code; flag conflicts
> explicitly before deviating.

## §1. Mission

A Frappe app that wires destination-based US sales tax into
ERPNext's tax-computation lifecycle, driven by a self-hosted
OpenSalesTax engine. Merchant value proposition: no
per-transaction fees, no SaaS lock-in, no third-party API
keys.

## §2. Architecture (locked)

**In-process Frappe doc_event hook.** The app registers
`doc_events.validate` for `Sales Invoice`, `Sales Order`, and
`Quotation`. On validate, the hook replaces the user's tax
template with OpenSalesTax-computed per-jurisdiction lines and
calls `erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals(doc)`.

The trust boundary is the merchant's ERPNext install; there is
no inbound HTTP surface, no webhook receiver, no JWT to manage.

## §3. License

Apache-2.0. DCO sign-off mandatory on every commit. No AI
co-author trailers.

## §4. Engine-call contract

The OST engine HTTP API v1 is the source of truth. The app
calls (via the `opensalestax` Python SDK):

- `POST /v1/calculate` — per-line tax calculation, destination ZIP
- `GET /v1/health` — Test Connection + startup probe
- `GET /v1/states` — coverage tiers (used by Settings UI)
- `GET /v1/rates` — per-ZIP rates (used by diagnostics)

The app NEVER imports OST internals. The HTTP API is the
contract; the v1 surface is pinned in the README's
compatibility matrix.

## §5. USD-only / US-only

The engine is US-only / USD-only by design. The app's
`validate` hook gates: app enabled? `currency == "USD"`?
`shipping_address.country == "United States"`? ZIP matches
`^\d{5}(-\d{4})?$`? If any gate fails, the hook silently
no-ops and ERPNext's normal template-based tax math runs.

## §6. Calculation only

Never file returns, never remit collected tax, never validate
addresses. The app computes tax; the merchant remits. Every
README and disclaimer carries this statement.

## §7. Trust boundary

The app runs inside the merchant's Frappe process; whatever
code loaded the app is already trusted. Configuration comes
from two trusted sources:

1. The `OpenSalesTax Settings` doctype (merchant-edited in
   the Frappe UI; API key encrypted by Frappe's standard
   encrypted-field mechanism)
2. The `after_install` hook's defaults

Engine URL is validated at save time AND at runtime by
`UrlValidator`. The validator rejects loopback / RFC-1918 /
link-local / CGNAT / multicast / broadcast unless the merchant
explicitly enables `Allow Private Networks` (for LAN-hosted
engines).

## §8. Fail-soft policy

When the engine is unreachable or returns 5xx, the validate
hook silently falls back to the user's tax template
(default). The merchant can opt into strict mode in Settings,
in which case a Frappe Validation Error throws at save time.

## §9. Test environment

- Unit tests via `pytest` + Frappe's `FrappeTestCase` (v15) /
  `IntegrationTestCase` (v16). Compat shim in
  `opensalestax_erpnext/tests/compat.py`.
- Integration tests run on a real Frappe bench with MariaDB +
  Redis via GitHub Actions matrices (one workflow per major
  branch).

## §10. Out of scope

- Tax filing / remittance
- Address validation / autocomplete
- Non-USD currency / non-US jurisdictions
- POS Invoice — deferred to v0.2
- Purchase Invoice / use-tax accrual — deferred to v0.2
- Per-product category mapping — deferred to v0.2 (gated on
  engine adding a category surface)
- Transaction record-back on `on_submit` — engine has no
  `/v1/transactions` endpoint yet; deferred indefinitely
- Standalone HTTP / webhook server (architecture §2 — Frappe
  invokes us in-process)

## §11. Branch model

Two long-lived branches, one per Frappe major:

| Frappe / ERPNext | Branch | Python |
|---|---|---|
| v16 (current stable) | `version-16` | 3.14 |
| v15 (previous stable) | `version-15` | 3.10-3.14 |

Tags follow the pattern `version-NN-vX.Y.Z` (e.g.
`version-15-v0.1.0`, `version-16-v0.1.0`). Each branch is
released independently; CHANGELOG entries are duplicated
across branches when applicable.

## §12. Distribution

Installed via `bench get-app` directly from GitHub. The app is
NOT distributed via PyPI (Frappe convention — bench manages
its own dependency resolution and PyPI distribution would
fragment that). The `opensalestax` Python SDK is on PyPI; the
app declares it in `requirements.txt`.
