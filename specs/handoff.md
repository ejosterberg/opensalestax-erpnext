# Handoff — opensalestax-erpnext

> **Read first if you're a fresh agent.** Constitution + current
> state + this file are the canonical bring-up sequence.

## You are here — 2026-05-15 (v0.1.0 shipped, spec writeup completed by captain)

v0.1.0 is live on GitHub on both `version-15` and `version-16`
branches (tags `version-15-v0.1.0`, `version-16-v0.1.0`). All
shipped quality gates green. Specs were back-filled by the
captain session on 2026-05-15 (the code shipped 2026-05-13
before specs landed).

For the "where we are" snapshot read
[`specs/current-state.md`](current-state.md).

## What's next — v0.2 candidates

The order below is a recommendation; pick whatever interests
you (or what Eric directs). Each item is roughly half a day to
a day of focused work.

### Tier 1 — likely shipped first

1. **Live-instance integration test on a Proxmox demo VM.** GH
   Actions matrices simulate this in CI but a real bench hasn't
   been exercised end-to-end. Provision an `erpnext-v16-demo`
   VM (pmvm1, next free in 900-999 range), `bench init` + ERPNext
   v16, install this app, configure Settings, create a US Sales
   Invoice with a MN ship-to address, observe per-jurisdiction
   tax lines. Document the recipe in `docs/INTEGRATION-CHECK.md`
   and link from CHANGELOG.
2. **POS Invoice support.** Add to the `doc_events` map. The
   POS controller has a different `validate` path — verify the
   gate logic still works (currency, country, ZIP) and that
   `calculate_taxes_and_totals` is the right downstream call.
3. **Purchase Invoice / use-tax accrual.** Hook
   `doc_events.validate` for `Purchase Invoice`. The tax math is
   different (the merchant is the buyer; use-tax accrual posts
   to a different GL account). Per-state nexus filter probably
   useful here too — most merchants don't owe use tax in every
   state they buy from.

### Tier 2 — when there's user demand

4. **Per-product OST category mapping** — gated on the engine
   adding a category surface in v1. Wait for that. When ready:
   add a "Tax Class → OST Category" mapping section in Settings
   (sibling pattern: WooCommerce v0.3.3 + Odoo v0.1.13 + Magento
   v1.3 — all use TaxClass.name → OST category string).
5. **Transaction record-back on `on_submit`** — gated on the
   engine adding `POST /v1/transactions`. Wait for that. The
   `audit.py` stubs are reserved for this.
6. **Per-state nexus filter** — sibling pattern shipped in
   Vendure v1.2 + Magento (proposed v1.3). Two mutually-exclusive
   options: `enabled_states` / `disabled_states` on Settings.
   Strategy: return early (template fallthrough) when ship-to
   province isn't in nexus list. ~half day.
7. **Bench-installable demo dataset** — a small fixture (one
   item, one tax account head, one MN customer) that a merchant
   can `bench install-app opensalestax_erpnext_demo` to see the
   full happy-path render.

### Tier 3 — engine-side prerequisites

8. **Operator telemetry** — last successful calc timestamp,
   failure streak count, average RTT. Surface via Frappe's
   built-in dashboard primitives.
9. **Multi-company support** — verify behavior when the same
   ERPNext install has multiple Company records with different
   tax setups. Confirm or fix.

## Standing rules

- Apache-2.0; DCO sign-off mandatory; no AI co-author trailers
- Constitution §5: USD-only / US-only; non-matching documents
  fall through to ERPNext's normal template-based tax math
- Constitution §8: fail-soft default; strict mode opt-in via
  Settings
- Two branches: `version-15` and `version-16`. Most changes
  land on both. CHANGELOG entries on each branch.

## Pre-flight for a fresh session

1. Read `specs/constitution.md`
2. Read `specs/current-state.md`
3. Read `specs/handoff.md` (this file)
4. Read `docs/SECURITY-REVIEW.md` and `docs/ARCHITECTURE.md`
5. Skim recent commits on both `version-15` and `version-16`
   (`git log version-15..version-16` and reverse)
6. Pick a v0.2 candidate and ship it

## Portfolio context

The canonical state of this and the other ~17 OST connector
projects lives at:

`../opensalestax-Odoo/portfolio/{state,roadmap,policy,needs-eric,log}.md`

Eric's captain Claude session works through that portfolio
sequentially. If you're picking up this repo specifically (vs.
running the captain), update `portfolio/state.md` when you
ship.
