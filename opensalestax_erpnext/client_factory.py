# SPDX-License-Identifier: Apache-2.0
"""Build an opensalestax.Client from OpenSalesTax Settings.

Single chokepoint for engine HTTP calls. Pulls config from the Settings
doctype, validates the URL via the SSRF allow-list, decrypts the API
key, and constructs a typed SDK client with a conservative 5-second
timeout.
"""

from __future__ import annotations

from typing import Any

from .exceptions import OstaxConfigError
from .url_validator import is_safe_url, reason_unsafe

_DEFAULT_TIMEOUT_SECONDS = 5.0


def build_client(settings: Any) -> Any:
	"""Build and return an `opensalestax.Client` from a Settings doc.

	Raises:
		OstaxConfigError: If `base_url` is missing, malformed, or fails the
			SSRF allow-list.
		ImportError: If the `opensalestax` SDK is not installed (this would
			indicate a broken `requirements.txt` install).
	"""
	from opensalestax import Client  # imported lazily so unit tests can patch

	base_url = (settings.base_url or "").strip()
	if not base_url:
		raise OstaxConfigError("OpenSalesTax base URL is not configured")

	allow_private = bool(getattr(settings, "allow_private_networks", 0))
	if not is_safe_url(base_url, allow_private=allow_private):
		raise OstaxConfigError(
			f"OpenSalesTax base URL rejected: {reason_unsafe(base_url, allow_private=allow_private)}"
		)

	api_key = None
	if getattr(settings, "api_key", None):
		try:
			api_key = settings.get_password("api_key")
		except Exception:
			# get_password may raise if the field isn't truly encrypted yet
			# (e.g. immediately after first save). Treat as anonymous.
			api_key = None

	verify_ssl = bool(getattr(settings, "verify_ssl", 1))

	# The SDK exposes a Client constructor with these keyword args.
	# See opensalestax-python's README for the canonical surface.
	return Client(
		base_url=base_url,
		api_key=api_key,
		verify=verify_ssl,
		timeout=_DEFAULT_TIMEOUT_SECONDS,
	)
