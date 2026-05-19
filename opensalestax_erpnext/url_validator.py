# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""SSRF defense -- validate engine base_url before dispatching requests.

When a merchant types a URL into OpenSalesTax Settings, this module
decides whether it's safe to send HTTP traffic to. By default it
rejects:

- loopback (127.0.0.0/8, ::1)
- link-local (169.254.0.0/16, fe80::/10)
- multicast / reserved / broadcast
- RFC-1918 private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- CGNAT (100.64.0.0/10)

The RFC-1918 + CGNAT block can be overridden with `allow_private=True`
for legitimate LAN-hosted OpenSalesTax deployments -- the merchant must
opt in via the **Allow Private Networks** toggle in Settings.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")


def _parse_host(url: str) -> str | None:
	"""Return the hostname component of `url`, or None if unparseable."""
	if not url or not isinstance(url, str):
		return None
	try:
		parsed = urlparse(url.strip())
	except ValueError:
		return None
	if parsed.scheme not in ("http", "https"):
		return None
	host = parsed.hostname
	if not host:
		return None
	# Strip brackets from IPv6 literals -- urlparse leaves them off but be defensive
	return host.strip("[]")


def _resolve_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
	"""Resolve `host` to a list of IP addresses. Empty list on failure."""
	try:
		addr_info = socket.getaddrinfo(host, None)
	except (OSError, UnicodeError):
		return []
	resolved: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
	for entry in addr_info:
		sockaddr = entry[4]
		try:
			resolved.append(ipaddress.ip_address(sockaddr[0]))
		except ValueError:
			continue
	return resolved


def _is_always_unsafe(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
	"""Return True if the IP is unsafe regardless of allow_private flag."""
	return bool(ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)


def _is_private_or_cgnat(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
	"""Return True if the IP is RFC-1918 private or in the CGNAT range."""
	if ip.is_private:
		return True
	return isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT_NET


def is_safe_url(url: str, allow_private: bool = False) -> bool:
	"""Return True if `url` is safe to dispatch HTTP requests to.

	Args:
		url: The URL string from OpenSalesTax Settings.
		allow_private: If True, RFC-1918 + CGNAT addresses pass. Default False.

	Returns:
		True if every resolved address for the URL's host is safe; False otherwise.
		Malformed URLs and DNS-resolution failures return False.
	"""
	host = _parse_host(url)
	if host is None:
		return False
	resolved = _resolve_addresses(host)
	if not resolved:
		return False
	for ip in resolved:
		if _is_always_unsafe(ip):
			return False
		if not allow_private and _is_private_or_cgnat(ip):
			return False
	return True


def _classify_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, allow_private: bool) -> str:
	"""Return a non-empty reason string if `ip` is unsafe, else ''."""
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
	if allow_private:
		return ""
	if ip.is_private:
		return (
			f"resolved to private/RFC-1918 address {ip} -- tick "
			"'Allow Private Networks' in Settings if this is intentional"
		)
	if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT_NET:
		return f"resolved to CGNAT address {ip}"
	return ""


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
		return f"unsupported scheme {parsed.scheme!r} -- only http/https allowed"
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
		try:
			ip = ipaddress.ip_address(entry[4][0])
		except ValueError:
			continue
		reason = _classify_ip(ip, allow_private)
		if reason:
			return reason
	return ""
