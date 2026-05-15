# CLAUDE.md — opensalestax-erpnext

> Project memory for Claude sessions on the ERPNext Frappe app
> connector. Read this AND `specs/constitution.md` + `specs/handoff.md`
> before writing code.

## Mission

A Frappe app that wires destination-based US sales tax into
ERPNext's tax-computation lifecycle, driven by a self-hosted
OpenSalesTax engine. Same merchant value proposition as the
other OST connectors (Vendure, Medusa, Saleor, Square, Magento,
WooCommerce, Bagisto, etc.): no per-transaction fees, no SaaS
lock-in, no third-party API keys.

## Stack

- **Language:** Python 3.10–3.14
- **Framework:** Frappe (the ERPNext platform) — installed via
  `bench get-app` + `bench install-app`
- **Distribution:** GitHub install (branch-per-Frappe-major)
  — `v15` branch targets ERPNext v15 (Python 3.10+, MariaDB
  10.6); `v16` branch targets ERPNext v16 (Python 3.14)
- **License:** Apache-2.0
- **Tests:** pytest + Frappe's `FrappeTestCase` (v15) /
  `IntegrationTestCase` (v16) — compat shim in
  `opensalestax_erpnext/tests/compat.py`

## Architectural anchors

- **In-process Frappe doc_event hook.** The app registers
  `doc_events.validate` for `Sales Invoice`, `Sales Order`, and
  `Quotation`. On validate, it replaces the user's tax template
  with OpenSalesTax-computed per-jurisdiction lines, then calls
  `erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals(doc)`
  to refresh `grand_total`.
- **Single `OpenSalesTax Settings` doctype.** Engine URL + API
  key (encrypted) + cache TTL + fail-soft toggle + tax-account
  head + override-respect + allow-private-networks. A "Test
  Connection" action calls the engine's `/v1/health`.
- **Cache layer** backed by Frappe's Redis client (24h default
  TTL keyed on ZIP).
- **SSRF defense** — `UrlValidator` rejects loopback /
  RFC-1918 / link-local / CGNAT / multicast / broadcast unless
  the `Allow Private Networks` flag is explicitly enabled (for
  LAN-hosted engines).
- **USD-only / US-only.** Non-USD or non-US documents
  fall through to ERPNext's normal template-based tax math
  (matches the engine constitution's US-only scope).
- **Fail-soft default.** When the engine is unreachable, the
  hook silently falls back to the user's tax template. Strict
  mode is opt-in via Settings.
- **Sales-side only in v0.1.** Purchase Invoice / use-tax
  accrual is deferred to v0.2.

## File layout

```
opensalestax-erpnext/
├── CLAUDE.md                       # this file
├── README.md                       # user-facing install + verify
├── LICENSE                         # Apache-2.0
├── CHANGELOG.md
├── CONTRIBUTING.md                 # DCO mandatory
├── SECURITY.md
├── setup.py / pyproject.toml       # packaging
├── requirements.txt                # opensalestax>=0.1.0,<0.2.0 + frappe deps
├── docs/
│   ├── SECURITY-REVIEW.md
│   └── ARCHITECTURE.md
├── opensalestax_erpnext/
│   ├── __init__.py                 # __version__
│   ├── hooks.py                    # Frappe app declaration + doc_events
│   ├── tax.py                      # apply_opensalestax() — the validate handler
│   ├── url_validator.py            # SSRF guard
│   ├── audit.py                    # on_submit / on_cancel stubs (v0.2)
│   ├── install.py                  # after_install hook
│   ├── tests/
│   │   ├── compat.py               # FrappeTestCase ↔ IntegrationTestCase shim
│   │   └── test_*.py               # 6 unit suites: apply, cache, fail_soft,
│   │                               # gates, item_tax_template, url_validator
│   └── opensalestax_erpnext/doctype/opensalestax_settings/  # Single doctype
└── specs/                          # spec-driven dev (Eric's playbook)
    ├── constitution.md
    ├── current-state.md
    └── handoff.md
```

## What NOT to do

- Don't add Purchase Invoice / use-tax accrual in v0.1 — defer
  to v0.2 with its own ADR.
- Don't add POS Invoice support in v0.1 — same reason.
- Don't call `engine /v1/transactions` (endpoint doesn't exist
  yet). No transaction record-back until the engine adds the
  surface — also v0.2.
- Don't introduce per-product category mapping until OST's v1
  HTTP API exposes a category gate.
- Don't ship a separate standalone server. The app is
  in-process Frappe; the trust boundary is the merchant's
  ERPNext install.
- Don't accept commits without DCO sign-off.
- Don't introduce non-Apache-2.0-compatible dependencies.

## Releasing

- **Two branches**: `version-15` (ERPNext v15) and `version-16`
  (ERPNext v16). Each tagged independently as
  `version-NN-vX.Y.Z` (e.g. `version-15-v0.1.0`,
  `version-16-v0.1.0`).
- GitHub release on each tag for each branch.
- The app is not distributed via PyPI; merchants install it
  via `bench get-app https://github.com/...` from the
  appropriate branch.

## Sibling-project map

See `opensalestax-Odoo/portfolio/state.md` for the canonical
list of all connector projects in this portfolio.
