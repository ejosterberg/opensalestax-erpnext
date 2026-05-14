# Contributing to opensalestax-erpnext

Thanks for your interest! Contributions are welcome via pull request.

## Ground rules

1. **Every commit must be DCO-signed off** — `git commit -s`. The signature certifies that you wrote the code (or have the right to contribute it) per the [Developer Certificate of Origin](https://developercertificate.org/). CI rejects unsigned commits.
2. **No AI-generated commit trailers.** Don't include `Co-authored-by: Claude` or similar attributions. The DCO sign-off is enough.
3. **Apache 2.0** — all contributions are licensed Apache 2.0. SPDX header on every new source file: `# SPDX-License-Identifier: Apache-2.0`.
4. **One concern per PR.** Don't bundle "fix tax-rounding bug + new feature + lint cleanup" — keep them separate.

## Development setup

You need a Frappe bench to develop against. Easiest path:

```bash
# Spin up a bench (one-time)
pip install frappe-bench
bench init --frappe-branch version-15 my-bench
cd my-bench
bench get-app erpnext --branch version-15
bench new-site dev.localhost --admin-password admin --mariadb-root-password root
bench --site dev.localhost install-app erpnext

# Install our app from your local clone
bench get-app file:///path/to/your/clone/opensalestax-erpnext --branch version-15
bench --site dev.localhost install-app opensalestax_erpnext
bench start
```

Now visit `http://dev.localhost:8000` and search for "OpenSalesTax Settings".

## Running tests

Inside the bench:

```bash
bench --site dev.localhost run-tests --app opensalestax_erpnext
```

For unit-only tests outside a bench (faster iteration):

```bash
pip install -r requirements-dev.txt
pytest
```

## Linting / formatting

```bash
ruff check .
ruff format --check .
mypy opensalestax_erpnext/
```

CI runs all three. Fix locally before pushing.

## Pull-request checklist

Before requesting review:

- [ ] All commits signed off (`git log --format='%h %s%b' | grep Signed-off-by | wc -l` matches your commit count)
- [ ] SPDX header on every new `.py` file
- [ ] `ruff check .` green
- [ ] `ruff format --check .` green
- [ ] `mypy opensalestax_erpnext/` green
- [ ] Unit tests added or updated for the change
- [ ] `bench run-tests --app opensalestax_erpnext` green
- [ ] CHANGELOG `[Unreleased]` section updated
- [ ] Tested on both v15 and v16 (or noted which branches you tested)

## Security issues

Don't open a public issue for security vulnerabilities. See [`SECURITY.md`](SECURITY.md).
