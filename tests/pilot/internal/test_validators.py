"""Tests for pilot.internal.validators."""

from __future__ import annotations

from pilot.internal.validators import validate_public_url


def test_public_url_accepts_a_dns_name() -> None:
    assert validate_public_url("http://vllm:8000/v1") is None
    assert validate_public_url("https://frappe-llm.example/v1") is None


def test_public_url_accepts_a_routable_ip() -> None:
    assert validate_public_url("http://8.8.8.8/v1") is None


def test_public_url_accepts_a_private_lan_ip() -> None:
    """Self-hosted integrations legitimately live on a private network."""
    assert validate_public_url("http://192.168.1.50:8000/v1") is None


def test_public_url_rejects_non_http_scheme() -> None:
    assert validate_public_url("file:///etc/passwd") is not None
    assert validate_public_url("ftp://example.com") is not None


def test_public_url_rejects_a_url_without_a_host() -> None:
    assert validate_public_url("http:///path") is not None


def test_public_url_rejects_loopback() -> None:
    assert validate_public_url("http://127.0.0.1:8000") is not None
    assert validate_public_url("http://[::1]:8000") is not None


def test_public_url_rejects_link_local_and_cloud_metadata() -> None:
    assert validate_public_url("http://169.254.169.254/latest/meta-data/") is not None


def test_public_url_rejects_unspecified_and_multicast() -> None:
    assert validate_public_url("http://0.0.0.0:8000") is not None
    assert validate_public_url("http://224.0.0.1:8000") is not None


def test_public_url_allows_a_blank_value() -> None:
    assert validate_public_url("") is None
