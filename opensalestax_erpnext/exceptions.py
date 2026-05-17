# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""Domain exceptions for the OpenSalesTax integration."""


class OstaxError(Exception):
	"""Base class for OpenSalesTax integration errors."""


class OstaxConfigError(OstaxError):
	"""Raised when Settings are missing or invalid."""


class OstaxEngineError(OstaxError):
	"""Raised when the engine returns an unrecoverable error."""
