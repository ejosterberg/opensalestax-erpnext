# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Email **ejosterberg@gmail.com** with:

- A description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Suggested mitigation, if you have one

You should receive an acknowledgement within 72 hours. Critical issues are typically patched and released within 7 days.

## What we consider security-sensitive

This app is a tax-calculation integration. Issues that materially affect:

- **Confidentiality** — leaking the engine API key, leaking customer addresses to unauthorized parties, exposing the engine to unintended callers (SSRF, reflected requests).
- **Integrity** — incorrect tax math that benefits an attacker, ability to substitute attacker-controlled responses, ability to escalate from `Accounts Manager` permissions.
- **Availability** — ability to crash the bench, deadlock the cache, or trigger unbounded engine calls.

…are in scope. Issues that affect the merchant's own tax accuracy when configured correctly (and where the merchant is the "attacker") generally are not.

## Out of scope

- Issues in upstream Frappe / ERPNext — report to <https://github.com/frappe/frappe/security> and <https://github.com/frappe/erpnext/security>.
- Issues in the OpenSalesTax engine itself — report to <https://github.com/ejosterberg/open-sales-tax/security>.
- Issues in the `opensalestax` Python SDK — report to <https://github.com/ejosterberg/opensalestax-python/security>.

## Disclosure

We follow a 90-day disclosure timeline (or earlier if fully patched and shipped). Reporters are credited in the CHANGELOG unless they request anonymity.
