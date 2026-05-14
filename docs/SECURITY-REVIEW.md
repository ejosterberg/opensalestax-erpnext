# Security Review — opensalestax-erpnext v0.1

> Snapshot dated 2026-05-13. Re-do at every major version.

## Scope of review

The OpenSalesTax for ERPNext app:

- Reads ERPNext Sales Invoice / Sales Order / Quotation documents on `validate`.
- Reads the customer's shipping `Address` to extract a ZIP code.
- Makes outbound HTTPS calls to a merchant-configured OpenSalesTax engine.
- Writes per-jurisdiction tax lines into the document's `taxes` child table.
- Persists configuration via the `OpenSalesTax Settings` Single doctype (incl. an optional encrypted API key).

What this review does NOT cover:

- Security of the OpenSalesTax engine itself (separate audit).
- Security of upstream Frappe / ERPNext (out of scope; report upstream).
- Security of the `opensalestax` Python SDK (separate audit).

## Threat model

| # | Threat | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| T1 | **SSRF** — admin sets `base_url` to `http://10.0.0.1/admin/dangerous` or similar internal target | M | High | `UrlValidator` rejects loopback / RFC-1918 / link-local / multicast / CGNAT addresses unless `allow_private_networks=1`. Validation runs both at Settings save time (in `OpenSalesTaxSettings.validate()`) and again at `build_client()` time, so a manual DB write can't bypass it. | ✅ Mitigated |
| T2 | **Credential leakage** — API key shows up in logs / error messages | M | High | `api_key` field is `Password` fieldtype (encrypted at rest via Frappe). Accessed only through `settings.get_password("api_key")`. Never written to logs — `_log_engine_error()` formats `doctype/name` only. `frappe.log_error()` is itself sanitized by Frappe. | ✅ Mitigated |
| T3 | **GL-account injection** — admin (or a compromised admin session) picks an attacker-controlled GL account | L | Medium | `tax_account_head` is a `Link → Account` field. Frappe enforces referential integrity — the value must be an existing `Account` doc the user has read access to. | ✅ Mitigated |
| T4 | **TLS bypass** — `verify_ssl=0` exposes the integration to a MITM | L | High | Default ON. `verify_ssl=0` is documented as dev-only in the field description AND the README. No automatic re-enable, by design — merchants who genuinely run self-signed-dev want the toggle. | ⚠️ Documented |
| T5 | **DoS via engine hang** — engine becomes unresponsive, every Sales Invoice save blocks indefinitely | M | High | `client_factory.build_client()` passes a 5-second timeout to the SDK. On timeout the `fail_soft=1` path is the default; the save proceeds with the user's template applied. `fail_soft=0` (strict) is explicit opt-in for merchants who'd rather block than guess. | ✅ Mitigated |
| T6 | **Stale cache** — rate changes (e.g. quarterly state update) but cache TTL hasn't expired | M | Low | TTL configurable; 24h default lines up with Avalara/TaxJar conventions for periodicity. Manual flush available via `bench --site X console` → `frappe.cache().delete_keys('ostax:rate:*')`. v0.2 candidate: scheduled flush at known rate-change dates. | ✅ Accepted |
| T7 | **CSRF on Test Connection** — attacker tricks an admin into calling `test_connection` against an arbitrary URL | L | Low | `test_connection` is decorated `@frappe.whitelist()` which enforces Frappe's CSRF token check on all non-GET callable methods. The URL it probes is read from saved Settings (server-side), not from the request payload — so even if CSRF were bypassed, the URL is already trusted by the admin. | ✅ Mitigated |
| T8 | **Privilege escalation** — non-admin reads API key via desk search or list view | L | High | Settings doctype permissions: `System Manager` (full) and `Accounts Manager` (read/write). No other role gets access. Frappe enforces these server-side; the `Password` field type encrypts at rest so a DB compromise still requires the decrypt key. | ✅ Mitigated |
| T9 | **PII exfiltration** — customer addresses sent to a third party | N/A | Medium | The connector sends **only the ZIP code** to the engine (engine v1 API is ZIP-only by design). No customer name, no street, no email, no phone. The engine constitution explicitly limits inputs to address fragments. | ✅ By design |
| T10 | **Composition collision** — multiple tax apps both register `validate` hooks; order is undefined → last-write-wins, behavior depends on install order | L | Medium | Documented in README: "install only one tax provider." Future v0.2 candidate: detect competing tax apps at install time and warn loudly. | ⚠️ Documented |
| T11 | **Injection via tax-line description** — attacker controls part of a jurisdiction name returned by the engine | L | Low | Tax-line descriptions are rendered by ERPNext as text in HTML form views; Frappe escapes them. No `safe_eval` or template-string interpretation of the field. | ✅ Mitigated |
| T12 | **Background-job context** — RQ worker imports tax module before settings are configured; hook fires on an unconfigured stack and crashes | M | Medium | Settings read is guarded in `tax.py::apply_opensalestax` with a broad `try/except: return` that no-ops if the doctype isn't ready. Idempotent: when settings exist, the gate `enabled=0` further no-ops. | ✅ Mitigated |
| T13 | **Cache poisoning** — attacker writes a malicious JSON blob under `ostax:rate:<zip5>` in Redis | L | High | Requires direct Redis access, which already implies compromise. Within the app, JSON-decode is wrapped in a `try/except: return None` — a corrupt entry is treated as a miss and a fresh engine call is made. This recovers automatically. | ✅ Mitigated |
| T14 | **Currency confusion** — non-USD invoice silently gets USD-priced sales tax applied | L | High | Hook bails on `doc.currency != "USD"` BEFORE any computation. Ship-to country must be "United States". Both gates are explicit. | ✅ Mitigated |
| T15 | **Float rounding error** — tax amounts drift over many invoices | M | Low | All math goes through `Decimal` with `quantize(Decimal("0.01"))` per jurisdiction line. Sum-of-rounded ≈ rounded-sum within 1 cent. Documented in CHANGELOG. | ✅ Mitigated |

## Code-review notes

### `tax.py` (the hook)

- Broad `except Exception` in the engine-call branch is intentional and `# noqa`'d — engine errors must NOT crash the save flow when `fail_soft=1`, regardless of SDK exception class.
- The first `try/except` around `_settings()` is also broad — guards against the install→test-run gap where the Settings doctype may not yet exist. Documented in the comment.
- `_log_engine_error` uses a `try/except: pass` around `frappe.log_error` — last-resort guard against logging failures masking the original exception path. Standard pattern in defensive Python.

### `url_validator.py`

- Resolves the URL's hostname via `socket.getaddrinfo` and checks **every** returned address, not just the first. Prevents DNS-rebinding attacks where a hostname resolves to a public IP once (for the validation check) and an internal IP later (when the actual request fires) — at least not via the obvious A-record swap; for full DNS-rebinding defense we'd need to pin the resolved address into the request and bypass the resolver, which is out of scope for v0.1. Documented as accepted risk: T1 partial mitigation.
- IPv6 link-local (`fe80::/10`) is caught by `ip.is_link_local`.
- Unspecified addresses (`0.0.0.0`, `::`) are rejected separately to defend against "bind to all interfaces" edge cases.

### `client_factory.py`

- Re-validates the URL even though Settings already validates on save. This is intentional — the in-DB value might have been changed without going through the form (e.g. via `frappe console` or a `set_value` API call), and the cost of re-checking is negligible.
- `get_password("api_key")` is wrapped in a broad `try/except` that falls back to anonymous. The fallback is documented; the alternative (fail hard) would force every test/dev install to set a key.

### `opensalestax_settings.py`

- `validate()` only enforces URL validation when `enabled=1`. This lets admins save a draft URL that's still wrong without being blocked — common during initial setup.
- The `test_connection` method is decorated with `@frappe.whitelist()` (CSRF + auth). It does NOT take a URL argument — it reads from saved Settings — so an attacker can't probe arbitrary URLs even if they bypass auth.

## Operational guidance

For merchants deploying this app:

1. **Always run with TLS** — keep `verify_ssl=1`. The toggle exists for self-signed-dev only.
2. **Restrict Settings permissions** — only `System Manager` should have full write. The `Accounts Manager` role can update mid-cycle tweaks (cache TTL, fail-soft) without seeing the API key encryption surface.
3. **Audit the Tax Account Head** — make sure it's a liability account that maps to your sales-tax-payable register.
4. **Snapshot before enabling on production** — set `enabled=0` on the first install, verify Test Connection works, then flip in a controlled window.
5. **Rotate API keys quarterly** — paste a fresh key into Settings; the old key is overwritten in the `Password` field.

## Known limitations

- **DNS-rebinding** is not fully mitigated for cross-protocol attacks. Mitigation would require pinning the resolved IP across both validation and request. Out of scope for v0.1; tracked as a v0.2 candidate.
- **Network egress audit** — there's no built-in egress logging beyond Frappe's standard request log. A v0.2 candidate is a per-engine-call audit doctype.
- **Token rotation** — manual via Settings form. A v0.2 candidate is a `bench` command for unattended rotation in CI/CD.

## Sign-off

| Reviewer | Date | Status |
|---|---|---|
| Eric Osterberg (project lead) | 2026-05-13 | Approved for v0.1 release |
| SonarQube static analysis | 2026-05-13 | See `docs/SONARQUBE-RESULTS.md` (link added after first scan) |
