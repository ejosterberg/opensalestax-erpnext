# Current state — opensalestax-erpnext

**Last refresh:** 2026-05-15 (captain spec writeup; code state unchanged from v0.1.0 ship)
**Status:** **v0.1.0 shipped 2026-05-13 on both `version-15` and `version-16` branches.**

## What's shipped

| Version | Tag | Branch | Date | Notes |
|---|---|---|---|---|
| 0.1.0 | `version-15-v0.1.0` | `version-15` | 2026-05-13 | Initial release for ERPNext v15 (Python 3.10-3.14, MariaDB 10.6). 6 unit test suites, integration tests via GitHub Actions matrix. SonarQube clean. |
| 0.1.0 | `version-16-v0.1.0` | `version-16` | 2026-05-13 | Same code, same release notes, recompiled against Frappe v16 (Python 3.14). |

GitHub: <https://github.com/ejosterberg/opensalestax-erpnext>

## Where the upstream engine is

OpenSalesTax engine — same instance the other connectors point at.
Pin: **v0.22+** (pre-v0.22 had the SD-state-bleed bug, closed in
v0.22.0). v1 HTTP API: `POST /v1/calculate`, `GET /v1/health`,
`GET /v1/states`, `GET /v1/rates`.

Engine is accessed via the `opensalestax` Python SDK (PyPI:
`opensalestax>=0.1.0,<0.2.0`).

## Where the platform is

- **ERPNext v16** (current stable, GA 2026-01-12; Python 3.14)
- **ERPNext v15** (previous stable; Python 3.10-3.14, MariaDB 10.6)
- ERPNext v14: not supported

## Architecture surface (v0.1)

- `doc_events.validate` hook for `Sales Invoice`, `Sales Order`,
  `Quotation` — replaces the user's tax template with
  per-jurisdiction lines.
- `doc_events.on_submit` / `on_cancel` for Sales Invoice — audit
  stubs (no-op in v0.1; reserved for v0.2).
- `after_install` hook — auto-creates default Settings row.
- `OpenSalesTax Settings` Single doctype — engine URL + encrypted
  API key + cache TTL + fail-soft toggle + tax-account head +
  item-tax-template override-respect + allow-private-networks +
  Test Connection action.
- Redis-backed cache (24h default, keyed on ZIP).
- `UrlValidator` SSRF defense.
- Country / currency / ZIP gates.
- Item Tax Template precedence (configurable).

## Known limitations (v0.1)

- USD-only / US-only — non-USD or non-US invoices fall through
  to the user's tax template (per constitution §5).
- Sales side only — Purchase Invoice / use-tax accrual deferred
  to v0.2.
- No per-product category mapping — gated on engine v1
  surfacing a category gate; deferred to v0.2.
- No POS Invoice support — deferred to v0.2.
- No transaction record-back on `on_submit` — engine has no
  `/v1/transactions` endpoint yet; deferred indefinitely.

## Quality bar (v0.1)

- 6 unit test suites pass on both Frappe v15 and v16
- GitHub Actions matrices green: ci.yml (lint / format / mypy),
  test-v15.yml (live Frappe + MariaDB), test-v16.yml (same on v16)
- SonarQube clean
- DCO sign-off on every commit; no AI co-author trailers
- SECURITY-REVIEW.md committed at `docs/SECURITY-REVIEW.md`

## What's NOT done

- Live-instance integration test on a fresh ERPNext bench
  (i.e., a real demo VM) — recommended next captain action.
  GitHub Actions matrices simulate this in CI, but a live
  Proxmox-hosted bench has not been exercised.
- v0.2 feature backlog (see [`handoff.md`](handoff.md))

## Spec-folder map

| File | Purpose |
|---|---|
| `specs/constitution.md` | Non-negotiable principles (license, architecture, USD-only, branch model) |
| `specs/current-state.md` | This file |
| `specs/handoff.md` | What the next session should pick up — v0.2 candidate list |

## Sibling-project map

The canonical portfolio state is in
`../opensalestax-Odoo/portfolio/state.md`. ERPNext is one of
~18 OST connector projects in the portfolio.
