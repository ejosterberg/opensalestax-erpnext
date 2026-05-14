# SPDX-License-Identifier: Apache-2.0
"""Audit-trail slots for on_submit / on_cancel.

v0.1: stubs only. Reserved for v0.2 when the engine adds a
`/v1/transactions` endpoint for transaction record-back.
"""

from __future__ import annotations

from typing import Any


def record_submission(doc: Any, method: str | None = None) -> None:
	"""Hook for Sales Invoice on_submit. v0.2 will post to engine."""
	# Intentionally a no-op in v0.1 — engine has no transactions endpoint yet.
	return None


def record_cancellation(doc: Any, method: str | None = None) -> None:
	"""Hook for Sales Invoice on_cancel. v0.2 will post to engine."""
	return None
