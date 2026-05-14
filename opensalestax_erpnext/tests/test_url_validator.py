# SPDX-License-Identifier: Apache-2.0
"""SSRF defense unit tests.

These tests do not require a Frappe bench — they're pure-Python and
can run via plain `pytest`. Run via `bench run-tests` too via the
FrappeTestCase shim, but the actual logic doesn't touch Frappe.
"""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from opensalestax_erpnext.url_validator import is_safe_url, reason_unsafe


def _resolve(host: str):
	"""Return a getaddrinfo-shaped result for a single IPv4 host."""

	def _fake(_host, _port, *_args, **_kw):
		return [(2, 1, 6, "", (host, 0))]

	return _fake


class TestUrlValidator(TestCase):
	"""Mock socket.getaddrinfo and verify each rejection branch."""

	def test_loopback_rejected(self):
		with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve("127.0.0.1")):
			self.assertFalse(is_safe_url("http://example.com"))
			self.assertIn("loopback", reason_unsafe("http://example.com"))

	def test_loopback_rejected_even_with_allow_private(self):
		with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve("127.0.0.1")):
			self.assertFalse(is_safe_url("http://example.com", allow_private=True))

	def test_rfc1918_rejected_by_default(self):
		for host in ("10.0.0.1", "172.16.0.1", "192.168.1.1"):
			with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve(host)):
				self.assertFalse(is_safe_url("http://example.com"), f"{host} should be rejected")

	def test_rfc1918_allowed_with_opt_in(self):
		for host in ("10.0.0.1", "172.16.0.1", "192.168.1.1"):
			with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve(host)):
				self.assertTrue(
					is_safe_url("http://example.com", allow_private=True),
					f"{host} should be allowed when opted in",
				)

	def test_link_local_rejected(self):
		with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve("169.254.1.1")):
			self.assertFalse(is_safe_url("http://example.com"))
			self.assertFalse(is_safe_url("http://example.com", allow_private=True))

	def test_multicast_rejected(self):
		with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve("224.0.0.1")):
			self.assertFalse(is_safe_url("http://example.com"))

	def test_cgnat_rejected_by_default(self):
		with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve("100.64.0.1")):
			self.assertFalse(is_safe_url("http://example.com"))
			self.assertIn("CGNAT", reason_unsafe("http://example.com"))

	def test_cgnat_allowed_with_opt_in(self):
		with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve("100.64.0.1")):
			self.assertTrue(is_safe_url("http://example.com", allow_private=True))

	def test_public_ipv4_accepted(self):
		with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _resolve("8.8.8.8")):
			self.assertTrue(is_safe_url("https://tax.example.com"))
			self.assertEqual(reason_unsafe("https://tax.example.com"), "")

	def test_https_required_unless_http(self):
		# ftp:// should be rejected outright (no DNS lookup needed)
		self.assertFalse(is_safe_url("ftp://example.com"))
		self.assertIn("scheme", reason_unsafe("ftp://example.com"))

	def test_empty_url_rejected(self):
		self.assertFalse(is_safe_url(""))
		self.assertFalse(is_safe_url(None))  # type: ignore[arg-type]
		self.assertEqual(reason_unsafe(""), "URL is empty")

	def test_no_host_rejected(self):
		# A scheme-only URL has no hostname
		self.assertFalse(is_safe_url("http://"))
		self.assertIn("host", reason_unsafe("http://"))

	def test_dns_resolution_failure_rejected(self):
		def _raise(*_a, **_kw):
			raise OSError("dns failure")

		with patch("opensalestax_erpnext.url_validator.socket.getaddrinfo", _raise):
			self.assertFalse(is_safe_url("http://does-not-exist.invalid"))
			self.assertIn("did not resolve", reason_unsafe("http://does-not-exist.invalid"))
