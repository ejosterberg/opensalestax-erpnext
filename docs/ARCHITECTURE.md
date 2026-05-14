# Architecture

## Lifecycle integration

This app integrates with ERPNext's tax-computation lifecycle by registering Frappe `doc_events: validate` hooks for `Sales Invoice`, `Sales Order`, and `Quotation` doctypes. When a document is saved, our handler `opensalestax_erpnext.tax.apply_opensalestax` fires during the document's `validate()` phase — after items are populated, before save commits.

```
Save click → ERPNext controller.validate() →
  AccountsController.validate() →
    set_missing_values()                       (line 277)
    validate_enabled_taxes_and_charges()       (line 304)
    set_taxes_and_charges()                    (line 308) ← may have copied template lines
    calculate_taxes_and_totals()               (line 310) ← initial totals
  SellingController.validate() →
    validate_items()
    set_customer_address()
  → doc_events: validate handlers fire (apps in install order)
      ↓
    OUR HOOK: opensalestax_erpnext.tax.apply_opensalestax
      ↓
      gate checks (enabled, USD, US ship-to, ZIP valid)
      cache lookup
      engine call (on miss)
      doc.taxes = []  (clear template lines)
      append per-jurisdiction tax rows (charge_type=Actual)
      calculate_taxes_and_totals(doc)  ← refresh totals against our lines
      ↓
  Save proceeds → DB write
```

## Why `validate`?

Five candidate events:

| Event | Why we didn't pick it |
|---|---|
| `before_validate` | Fires before `set_taxes_and_charges`; we'd have to suppress the template copy explicitly. Works, but more fragile. |
| `validate` | **Picked.** Matches `frappe/taxjar_integration` convention; runs *after* the controller's own tax math; we can re-run `calculate_taxes_and_totals(doc)` cleanly. |
| `before_save` | Fires after `validate()` returns. `grand_total` is already computed from the user's template at that point — our lines would land but totals would be stale. |
| `on_update` / `on_submit` | Too late. Doc is already saved / submitted. |
| `override_doctype_class` | Bench-wide singleton (only one override per doctype). Breaks composition with country-specific localizations or other tax apps. |

The TaxJar integration uses `validate` too. We're following a well-trodden path.

Verified via the Frappe Forum thread documenting that monkey-patching `calculate_taxes_and_totals` fails silently in RQ background workers — `doc_events` is import-order-safe whereas module patches are not. ([discuss.frappe.io/t/calculate-taxes-and-totals-override-not-working-in-background-jobs-on-frappe-cloud/159897](https://discuss.frappe.io/t/calculate-taxes-and-totals-override-not-working-in-background-jobs-on-frappe-cloud/159897))

## Module map

```
opensalestax_erpnext/
├── hooks.py              Registers doc_events + after_install. Single source of truth
│                         for what the framework wires up.
├── tax.py                THE CORE — apply_opensalestax + helpers. Read this first.
├── client_factory.py     Builds an opensalestax.Client from Settings, with URL validation
│                         and 5s timeout. Single chokepoint for "make an engine call."
├── cache.py              Redis-backed cache, JSON-serialized per-ZIP. get/set/flush.
├── url_validator.py      SSRF defense. Rejects loopback / RFC-1918 / link-local / CGNAT
│                         unless allow_private=True.
├── exceptions.py         Domain exceptions: OstaxEngineError, OstaxConfigError.
├── install.py            after_install hook — creates default Settings row.
├── audit.py              on_submit / on_cancel slots (v0.2 — currently no-op stubs).
├── _compat.py            Frappe v15 ↔ v16 shims (FrappeTestCase vs IntegrationTestCase,
│                         in_test flag rename).
└── opensalestax_erpnext/
    ├── doctype/opensalestax_settings/
    │   ├── opensalestax_settings.json    Single doctype definition (the form)
    │   ├── opensalestax_settings.py      Controller — validate() + test_connection action
    │   └── opensalestax_settings.js      Desk-form JS — wires Test Connection button
    └── tests/                            Unit tests, one file per concern
```

## Settings flow

`OpenSalesTax Settings` is a Frappe Single doctype — exactly one row, edited as a form rather than a list. Default values are created by `install.py::after_install` when the app is first installed.

Reading settings in code:

```python
def _settings():
    return frappe.get_cached_doc("OpenSalesTax Settings")

def _api_key():
    s = _settings()
    if not s.api_key:
        return None
    return s.get_password("api_key")  # decrypts the Password field
```

`get_cached_doc` is request-scoped, so repeated calls in the same hook invocation are free.

## Item Tax Template precedence

ERPNext's tax-precedence chain (research §3.6):

```
Item Tax Template (on item line)
  → Item Tax Template (on item group)
  → Tax Category (resolved via Tax Rule matching)
  → Sales Taxes and Charges Template (on doc.taxes_and_charges)
```

We override the bottom of the chain (the document-level template) but leave Item Tax Template entries intact when `treat_item_tax_template_as_override = 1` (the default). An item with an explicit Item Tax Template represents the merchant saying "this item is taxed differently" — typically nontaxable. Respecting it is a feature.

To force OpenSalesTax to override Item Tax Templates too, uncheck **Respect Item Tax Templates as Overrides** in Settings.

## Cache strategy

24h default TTL per ZIP (configurable). Engine rate lookups are deterministic given (ZIP, date), so 24h is conservative — most US sales-tax rate changes are scheduled quarterly. The cache lives in Frappe's standard Redis layer (`frappe.cache()`), keyed `ostax:rate:<zip5>`.

On Settings save, the cache is **not** auto-flushed. Reasoning: settings changes don't change the rate, only how the rate is looked up. If a merchant wants to force a fresh lookup (e.g. switching engine base_url to a different region), they can flush manually via `bench --site X console` → `frappe.cache().delete_keys('ostax:rate:*')`.

## Cross-version compatibility

The single `_compat.py` module isolates v15 ↔ v16 differences:

| Concern | v15 | v16 | `_compat.py` exposes |
|---|---|---|---|
| Test base class | `frappe.tests.utils.FrappeTestCase` | `frappe.tests.IntegrationTestCase` | `FrappeTestCase` (resolved at import) |
| in-test flag | `frappe.flags.in_test` | `frappe.in_test` | `in_test()` (checks both) |
| Single doctype int read | Returns `str` from `db.get_value` | Returns `int` | use `frappe.utils.cint()` defensively in callers |

The rest of the code uses identical Frappe APIs across both versions. Verified by running the same test suite on both branches in CI (`test-v15.yml` + `test-v16.yml`).

## The dependency arrow

Per the OpenSalesTax constitution §5:

```
opensalestax_erpnext (Apache 2.0)
   ↓  pip install via requirements.txt
opensalestax 0.1.x (PyPI)
   ↓  HTTPS
OpenSalesTax engine v1 HTTP API (/v1/calculate, /v1/health)
```

The connector **never** imports OpenSalesTax engine internals. The SDK is the only entry point. The HTTP API is the contract.

## Failure modes

| Failure | Behavior |
|---|---|
| Engine returns 5xx | If `fail_soft=1`: log and no-op. If `fail_soft=0`: `frappe.throw()` on save. |
| Engine times out (5s) | Same as 5xx — soft/strict branch. |
| Engine returns 4xx (bad ZIP) | Same — typically `fail_soft=1` means user keeps their template. |
| Cache layer down | Bypass cache, hit engine directly. |
| ZIP not parseable | Hook no-ops; user's template applies. |
| Settings Single doctype missing | Hook no-ops (defensive — happens during the install→test gap). |
