# SPDX-License-Identifier: Apache-2.0
"""SSRF defense — validate engine base_url before dispatching requests.

When a merchant types a URL into OpenSalesTax Settings, this module
decides whether it's safe to send HTTP traffic to. By default it
rejects:

- loopback (127.0.0.0/8, ::1)
- link-local (169.254.0.0/16, fe80::/10)
- multicast / reserved / broadcast
- RFC-1918 private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- CGNAT (100.64.0.0/10)

The RFC-1918 + CGNAT block can be overridden with `allow_private=True`
for legitimate LAN-hosted OpenSalesTax deployments — the merchant must
opt in via the **Allow Private Networks** toggle in Settings.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")


def is_safe_url(url: str, allow_private: bool = False) -> bool:
	"""Return True if `url` is safe to dispatch HTTP requests to.

	Args:
		url: The URL string from OpenSalesTax Settings.
		allow_private: If True, RFC-1918 + CGNAT addresses pass. Default False.

	Returns:
		True if every resolved address for the URL's host is safe; False otherwise.
		Malformed URLs and DNS-resolution failures return False.
	"""
	if not url or not isinstance(url, str):
		return False

	try:
		parsed = urlparse(url.strip())
	except ValueError:
		return False

	if parsed.scheme not in ("http", "https"):
		return False

	host = parsed.hostname
	if not host:
		return False

	# Strip brackets from IPv6 literals — urlparse leaves them off but be defensive
	host = host.strip("[]")

	# Resolve all addresses (IPv4 + IPv6). If any is unsafe, reject.
	try:
		addr_info = socket.getaddrinfo(host, None)
	except (OSError, UnicodeError):
		return False

	if not addr_info:
		return False

	for entry in addr_info:
		sockaddr = entry[4]
		ip_str = sockaddr[0]
		try:
			ip = ipaddress.ip_address(ip_str)
		except ValueError:
			continue

		if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
			return False
		if ip.is_unspecified:
			return False
		if not allow_private:
			if ip.is_private:
				return False
			if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT_NET:
				return False

	return True


def reason_unsafe(url: str, allow_private: bool = False) -> str:
	"""Return a short human-readable reason a URL fails validation.

	Returns an empty string if the URL is safe. Useful for surfacing
	a clear error to admins editing Settings.
	"""
	if not url or not isinstance(url, str):
		return "URL is empty"

	try:
		parsed = urlparse(url.strip())
	except ValueError:
		return "URL is malformed"

	if parsed.scheme not in ("http", "https"):
		return f"unsupported scheme {parsed.scheme!r} — only http/https allowed"

	host = parsed.hostname
	if not host:
		return "URL has no host component"
	host = host.strip("[]")

	try:
		addr_info = socket.getaddrinfo(host, None)
	except (OSError, UnicodeError):
		return f"host {host!r} did not resolve"

	if not addr_info:
		return f"host {host!r} returned no addresses"

	for entry in addr_info:
		sockaddr = entry[4]
		ip_str = sockaddr[0]
		try:
			ip = ipaddress.ip_address(ip_str)
		except ValueError:
			continue
		if ip.is_loopback:
			return f"resolved to loopback address {ip}"
		if ip.is_link_local:
			return f"resolved to link-local address {ip}"
		if ip.is_multicast:
			return f"resolved to multicast address {ip}"
		if ip.is_reserved:
			return f"resolved to reserved address {ip}"
		if ip.is_unspecified:
			return f"resolved to unspecified address {ip}"
		if not allow_private:
			if ip.is_private:
				return (
					f"resolved to private/RFC-1918 address {ip} — tick "
					"'Allow Private Networks' in Settings if this is intentional"
				)
			if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT_NET:
				return f"resolved to CGNAT address {ip}"

	return ""
