# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] — 2026-05-17

### Changed

- **Dual-licensed Apache-2.0 OR GPL-2.0-or-later.** Adds GPL-2.0-or-later
  as an alternative license alongside the existing Apache-2.0 grant.
  ERPNext core (Frappe + ERPNext) is GPL-3.0+, so GPL-2.0-or-later gives
  this app a clean copyleft-compatible distribution path while keeping
  Apache-2.0 available for downstream non-GPL embeddings. License files
  reorganized: `LICENSE-APACHE.txt` (existing Apache text, moved from
  `LICENSE`), `LICENSE-GPL.txt` (new, GNU GPL v2 text), `LICENSE` (new
  dual-declaration). SPDX headers updated across `.py` source files and
  `pyproject.toml`. `setup.py` `license=` field switched to the dual SPDX
  expression and a `GPLv2+` classifier added. `license.txt` (Frappe's
  preferred name) rewritten to reflect the dual license. Brings this app
  in line with the rest of the OpenSalesTax connector portfolio's
  dual-licensing standard.

### Added

- **`.github/dependabot.yml`** — weekly checks for pip + GitHub Actions
  dependencies, with grouped dev-dep PRs. Brings this repo in line with
  the rest of the OpenSalesTax connector portfolio's supply-chain hygiene
  standard.

## [0.1.0] — 2026-05-13

### Added — v0.1 initial release

- **`doc_events: validate` hook** for Sales Invoice, Sales Order, and Quotation that replaces the user's tax template with OpenSalesTax-computed per-jurisdiction lines.
- **`OpenSalesTax Settings` Single doctype** with engine base URL, API key (encrypted), cache TTL, fail-soft behavior, tax-account head, item-tax-template override-respect toggle, allow-private-networks flag.
- **Cache layer** backed by Frappe's Redis client (24h default TTL per ZIP).
- **SSRF defense** — `UrlValidator` rejects loopback / RFC-1918 / link-local / CGNAT / multicast / broadcast addresses unless **Allow Private Networks** is explicitly enabled (for LAN deployments).
- **Country / currency / ZIP gates** — hook no-ops if currency ≠ USD or ship-to country ≠ United States or ZIP isn't a 5-digit number.
- **Item Tax Template precedence** — items with an explicit `item_tax_template` are excluded from OpenSalesTax compute by default (respects merchant override); behavior is configurable in Settings.
- **Fail-soft mode** — when the engine is unreachable, silently fall back to the user's tax template (default) or throw on save (strict).
- **Test Connection action** in Settings — calls the engine's `/v1/health` and reports version + RTT.
- **`after_install` hook** — auto-creates default Settings row.
- **Compatibility shim** for `FrappeTestCase` (v15) → `IntegrationTestCase` (v16).
- **GitHub Actions CI**:
  - `ci.yml` — lint (ruff), format check, type check (mypy)
  - `test-v15.yml` — Frappe v15 + ERPNext v15 + MariaDB 10.6 integration test
  - `test-v16.yml` — Frappe v16 + ERPNext v16 + MariaDB 10.6 integration test
  - DCO sign-off check
- **SECURITY-REVIEW.md** documenting threat model + mitigations.
- **SonarQube project** configured (key: `opensalestax-erpnext`).
- **README** with install / configure / verify / disclaimer.
- **Apache 2.0** license + SPDX headers on every source file + DCO sign-off on every commit.

### Known limitations (v0.1)

- USD-only / US-only — non-USD or non-US invoices fall through to the user's tax template.
- Sales side only — Purchase Invoice / use-tax accrual deferred to v0.2.
- No per-product category mapping — engine v1 has no category gate; deferred to v0.2 once the engine adds the surface.
- No POS Invoice support — deferred to v0.2.
- No transaction record-back on `on_submit` — engine has no `/v1/transactions` endpoint yet.

### Disclaimer

Tax calculations are provided as-is for convenience. The merchant is solely responsible for tax-collection accuracy and remittance to the appropriate jurisdictions. Verify against your state Department of Revenue before remitting.

[Unreleased]: https://github.com/ejosterberg/opensalestax-erpnext/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ejosterberg/opensalestax-erpnext/releases/tag/version-15-v0.1.0
