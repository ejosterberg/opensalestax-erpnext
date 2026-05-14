# SPDX-License-Identifier: Apache-2.0
"""Audit-trail slots for on_submit / on_cancel.

v0.1: stubs only. Reserved for v0.2 when the engine adds a
`/v1/transactions` endpoint for transaction record-back.
"""

from __future__ import annotations

from typing import Any


def record_submission(_doc: Any, _method: str | None = None) -> None:
	"""Hook for Sales Invoice on_submit. v0.2 will post to engine.

	Args are positional-required by Frappe's hook dispatcher but unused
	in v0.1 — the engine has no `/v1/transactions` endpoint yet.
	"""
	return None


def record_cancellation(_doc: Any, _method: str | None = None) -> None:
	"""Hook for Sales Invoice on_cancel. v0.2 will post to engine."""
	return None
