# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""Redis-backed cache for engine rate lookups.

Backed by Frappe's `frappe.cache()` which provides a configured Redis
client. Cache key is `ostax:rate:<zip5>`; values are JSON-serialized
engine responses.

Cache miss is graceful â€” a corrupt or unreadable cache entry is
treated as a miss and the engine call is made fresh.
"""

from __future__ import annotations

import json
from typing import Any

import frappe

_KEY_PREFIX = "ostax:rate:"


def _key(zip5: str) -> str:
	return f"{_KEY_PREFIX}{zip5}"


def get(zip5: str) -> dict[str, Any] | None:
	"""Return the cached engine response for `zip5`, or None on miss."""
	raw = frappe.cache().get_value(_key(zip5))
	if raw is None:
		return None
	if isinstance(raw, dict):
		# frappe.cache().get_value may already JSON-decode in some setups
		return raw
	try:
		return json.loads(raw)
	except (TypeError, ValueError):
		# JSONDecodeError is a ValueError subclass â€” caught above.
		return None


def put(zip5: str, payload: dict[str, Any], ttl_seconds: int) -> None:
	"""Store `payload` under `zip5` with TTL `ttl_seconds`.

	Silently no-ops if `ttl_seconds <= 0` (caller wants caching disabled).
	"""
	if ttl_seconds <= 0:
		return
	frappe.cache().set_value(
		_key(zip5),
		json.dumps(payload),
		expires_in_sec=ttl_seconds,
	)


def flush() -> int:
	"""Delete every cached rate entry. Returns the number deleted."""
	pattern = f"{_KEY_PREFIX}*"
	keys = frappe.cache().get_keys(pattern) or []
	if keys:
		frappe.cache().delete_keys(keys)
	return len(keys)
