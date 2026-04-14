from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
import requests

from data.proxy_transport import ProxyTransport, ProxySession


class MockResponse:
    def __init__(self, status_code: int = 200, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}


def test_proxy_transport_disabled_returns_none() -> None:
    transport = ProxyTransport(proxy_url="")
    assert transport.get_proxies() is None


def test_proxy_transport_enabled_returns_proxy_dict() -> None:
    transport = ProxyTransport(proxy_url="proxy.example.com:8080", proxy_type="http")
    proxies = transport.get_proxies()
    
    assert proxies is not None
    assert proxies["http"] == "http://proxy.example.com:8080"
    assert proxies["https"] == "http://proxy.example.com:8080"


def test_proxy_transport_socks5_format() -> None:
    transport = ProxyTransport(proxy_url="socks5.example.com:1080", proxy_type="socks5")
    proxies = transport.get_proxies()
    
    assert proxies is not None
    assert proxies["http"] == "socks5://socks5.example.com:1080"
    assert proxies["https"] == "socks5://socks5.example.com:1080"


def test_proxy_transport_sticky_session_persistence() -> None:
    transport = ProxyTransport(
        proxy_url="proxy.example.com:8080",
        sticky_minutes=30,
    )
    
    first_proxies = transport.get_proxies()
    second_proxies = transport.get_proxies()
    
    # Same proxy URL within sticky session
    assert first_proxies == second_proxies


def test_proxy_transport_session_expiration() -> None:
    transport = ProxyTransport(
        proxy_url="proxy.example.com:8080",
        sticky_minutes=0,  # Expired immediately
    )
    
    # First call creates session
    transport.get_proxies()
    
    # Manually expire session
    if transport._current_session:
        transport._current_session.session_start = datetime.now(timezone.utc) - timedelta(minutes=1)
    
    # Next call should reinitialize (same proxy but new session)
    transport.get_proxies()
    
    assert transport._current_session is not None


def test_proxy_transport_cloudfront_ban_detection_404() -> None:
    transport = ProxyTransport(proxy_url="proxy.example.com:8080")
    response = MockResponse(status_code=404)
    
    assert transport._detect_cloudfront_ban(response) is True


def test_proxy_transport_cloudfront_ban_detection_cache_header() -> None:
    transport = ProxyTransport(proxy_url="proxy.example.com:8080")
    response = MockResponse(
        status_code=200,
        headers={"x-cache": "Error from cloudfront"},
    )
    
    assert transport._detect_cloudfront_ban(response) is True


def test_proxy_transport_cloudfront_ban_detection_normal_response() -> None:
    transport = ProxyTransport(proxy_url="proxy.example.com:8080")
    response = MockResponse(status_code=200, headers={"x-cache": "Hit from cloudfront"})
    
    assert transport._detect_cloudfront_ban(response) is False


def test_proxy_transport_failover_rotation() -> None:
    transport = ProxyTransport(
        proxy_url="proxy1.example.com:8080",
        failover_list=["proxy2.example.com:8080", "proxy3.example.com:8080"],
    )
    
    session = ProxySession(
        proxy_url="proxy1.example.com:8080",
        proxy_type="http",
        session_start=datetime.now(timezone.utc),
    )
    
    # Rotate to next proxy
    new_session = transport._rotate_proxy(session)
    
    assert new_session.proxy_url == "proxy2.example.com:8080"
    
    # Rotate again
    newer_session = transport._rotate_proxy(new_session)
    
    assert newer_session.proxy_url == "proxy3.example.com:8080"
    
    # Rotate back to first (wrap around)
    final_session = transport._rotate_proxy(newer_session)
    
    assert final_session.proxy_url == "proxy1.example.com:8080"


def test_proxy_transport_handle_response_triggers_failover() -> None:
    transport = ProxyTransport(
        proxy_url="proxy1.example.com:8080",
        failover_list=["proxy2.example.com:8080"],
    )
    
    # Initialize session
    transport.get_proxies()
    
    # Simulate CloudFront ban
    response = MockResponse(status_code=404)
    transport.handle_response(response)
    
    # Should have rotated to failover proxy
    assert transport._current_session is not None
    assert transport._current_session.proxy_url == "proxy2.example.com:8080"
    # fail_count should be 1 (one ban detected on the first proxy)
    assert transport._current_session.fail_count >= 1


def test_proxy_transport_get_status() -> None:
    transport = ProxyTransport(
        proxy_url="proxy.example.com:8080",
        sticky_minutes=30,
        failover_list=["proxy2.example.com:8080"],
    )
    
    transport.get_proxies()
    status = transport.get_status()
    
    assert status["enabled"] is True
    assert status["current_proxy"] == "proxy.example.com:8080"
    assert status["session_age_minutes"] is not None
    assert status["fail_count"] == 0
    assert status["sticky_minutes"] == 30
    assert status["failover_available"] is True


def test_proxy_transport_get_status_disabled() -> None:
    transport = ProxyTransport(proxy_url="")
    status = transport.get_status()
    
    assert status["enabled"] is False
    assert status["current_proxy"] is None
    assert status["session_age_minutes"] is None
    assert status["fail_count"] == 0
