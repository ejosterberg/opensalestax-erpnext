# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.4] — 2026-05-19

### Changed

- **CP-9: bumped `opensalestax` requirement from `>=0.2.0,<0.3.0` to
  `>=0.3.0,<0.4.0`.** Picks up the SDK's new `shipping` kwarg on
  `client.calculate()` plus the `CalculationResult.shipping` and
  `coverage_warning` response fields, and the `Shipping` /
  `CalculatedShipping` pydantic models.

### Notes

- ERPNext's current flow sends a single `taxable_total` to the engine
  (no per-line breakdown) and computes per-jurisdiction tax at
  apply-time. The first-class shipping field is not yet wired in —
  surfacing it cleanly requires (1) separating shipping from item
  taxables (ERPNext stores shipping in the `taxes` table mixed with
  actual tax lines, distinguished by `account_head`), then (2)
  passing the shipping amount through `_call_engine()` as the new
  `shipping` kwarg, and (3) splitting the engine's return into
  item-tax vs. shipping-tax adjustments. This refactor is deferred
  to v0.3.x. Today, merchants who include shipping inside the
  `taxable_total` get it taxed at the same rate as items — which
  matches ERPNext's standard "shipping is taxed like items" default
  for most US states. The per-state shipping-taxability nuances
  (MN tax-iff-taxable-items, MO/VA separately-stated, MD
  shipping-vs-handling) aren't yet reflected.
- Engine v0.59.0+ recommended.

## [0.2.3] — 2026-05-19

### Fixed

- **`ruff format --check` red on `tax.py` + `tests/test_gates.py`.**
  Pre-existing formatter drift that v0.2.2 didn't catch because
  `ruff check` (linter) and `ruff format --check` (formatter) are
  separate jobs in CI. Once v0.2.2 made `ruff check` pass, the
  formatter check ran and flagged the drift. `ruff format` auto-fix
  applied: 58 lines reflowed across 2 files. Behavior unchanged;
  51/51 pytest tests still pass.

## [0.2.2] — 2026-05-19

### Fixed

- **CI red since v0.2.0: ruff RUF002 + RUF003 ambiguous-Unicode errors.**
  Several Python files contained mojibake byte sequences inside
  comments and docstrings -- visual `->` and `--` characters that had
  been encoded as 3-byte sequences (U+00E2 U+2020 U+2019 and
  U+00E2 U+20AC U+201D respectively) by a Latin-1 -> UTF-8 conversion
  somewhere in the file's history. ruff correctly flagged these as
  ambiguous Unicode (RUF002 in docstrings, RUF003 in comments).
  v0.2.2 replaces both 3-char mojibake sequences with their ASCII
  equivalents (`->` and `--`) across all `.py` files. 48 characters
  swapped across 15 files. No behavior change; CI green again.
- 51/51 pytest tests still pass.

## [0.2.1] — 2026-05-19

### Changed

- **CP-8 Phase 5D: bumped `opensalestax` constraint to `>=0.2.0,<0.3.0`.**
  Picks up the new `OpenSalesTaxClient.capabilities()` /
  `OpenSalesTaxClient.get_capabilities()` helpers for engine v0.59.0's
  `/v1/capabilities` endpoint. No merchant-visible behavior change in
  this release — the helper is available to connector code but not yet
  wired into any feature path. Constraint bump only; Test Connection
  surface enrichment deferred to v-next.

## [0.2.0] — 2026-05-19

### Added

- **Per-state nexus filter (CP-3).** New `Nexus States (comma-separated)`
  field in the OpenSalesTax Settings DocType accepts a comma-separated
  list of US 2-letter state codes (e.g. `MN,WI,IA`). When set and
  non-empty, the validate hook short-circuits the engine call for any
  Sales Invoice / Sales Order / Quotation whose ship-to state is not
  in the list — ERPNext's default tax behavior (typically: no tax)
  takes over. Unset / empty preserves v0.1 behavior (engine called
  for every US/USD doc). Missing / unresolvable destination state
  with the filter active is fail-closed (also short-circuit) — the
  safer default for a merchant who explicitly opted in.

  Address parsing: ERPNext's `Address.state` is free text. We accept
  the 2-letter form directly and normalize the 50 full state names
  ("Minnesota" → "MN") at the read site. Anything that doesn't
  resolve to a 2-letter US code yields null (fail-closed).

  The new field is shipped in the DocType JSON, so existing installs
  pick it up automatically on `bench migrate` (Frappe syncs DocType
  field additions from the JSON — no separate patch needed).

  Brings this connector in line with WooCommerce v0.5, Vendure v1.2,
  and Odoo v0.3, which already shipped this filter. Major win for
  merchants with limited nexus footprints — typical merchant only
  has 1–3 nexus states and was previously paying engine RTT on
  every invoice.

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
