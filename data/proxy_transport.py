from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class ProxySession:
    proxy_url: str
    proxy_type: str
    session_start: datetime
    fail_count: int = 0


class ProxyTransport:
    """
    Proxy transport layer with sticky sessions and automatic failover.
    
    Features:
    - HTTP and SOCKS5 proxy support
    - Sticky sessions (configurable duration)
    - Automatic failover on CloudFront ban detection
    - Thread-safe proxy rotation
    """

    def __init__(
        self,
        proxy_url: str,
        proxy_type: str = "http",
        sticky_minutes: int = 30,
        failover_list: list[str] | None = None,
    ) -> None:
        self.primary_proxy_url = proxy_url
        self.proxy_type = proxy_type
        self.sticky_minutes = sticky_minutes
        self.failover_list = failover_list or []
        
        self._current_session: ProxySession | None = None
        self._all_proxies = [proxy_url] + self.failover_list
        self._lock = threading.Lock()
        
        if proxy_url:
            self._init_session(proxy_url)

    def _init_session(self, proxy_url: str) -> ProxySession:
        return ProxySession(
            proxy_url=proxy_url,
            proxy_type=self.proxy_type,
            session_start=datetime.now(timezone.utc),
        )

    def _is_session_expired(self, session: ProxySession) -> bool:
        expiry = session.session_start + timedelta(minutes=self.sticky_minutes)
        return datetime.now(timezone.utc) >= expiry

    def _detect_cloudfront_ban(self, response: requests.Response) -> bool:
        """Detect CloudFront IP ban via response headers or status code."""
        # Check for CloudFront error header (case-insensitive)
        cache_header = response.headers.get("x-cache", "")
        if "error from cloudfront" in cache_header.lower():
            return True
        
        # Check for 404 (CloudFront often returns 404 for banned IPs)
        if response.status_code == 404:
            return True
        
        return False

    def _format_proxy_dict(self, proxy_url: str) -> dict[str, str]:
        """Format proxy URL for requests library based on proxy type."""
        if self.proxy_type == "socks5":
            return {
                "http": f"socks5://{proxy_url}",
                "https": f"socks5://{proxy_url}",
            }
        return {
            "http": f"http://{proxy_url}",
            "https": f"http://{proxy_url}",
        }

    def _rotate_proxy(self, current_session: ProxySession) -> ProxySession:
        """Rotate to next proxy in failover list."""
        current_url = current_session.proxy_url
        current_index = self._all_proxies.index(current_url)
        next_index = (current_index + 1) % len(self._all_proxies)
        next_url = self._all_proxies[next_index]
        
        LOG.warning(
            "Proxy rotation: %s -> %s (failover #%d)",
            current_url,
            next_url,
            next_index,
        )
        
        new_session = self._init_session(next_url)
        new_session.fail_count = current_session.fail_count + 1
        return new_session

    def get_proxies(self) -> dict[str, str] | None:
        """Get current proxy dict for requests library, or None if disabled."""
        if not self.primary_proxy_url:
            return None
        
        with self._lock:
            if self._current_session is None:
                self._current_session = self._init_session(self.primary_proxy_url)
            
            # Check if session expired
            if self._is_session_expired(self._current_session):
                LOG.info("Proxy session expired, reinitializing")
                self._current_session = self._init_session(self._current_session.proxy_url)
            
            return self._format_proxy_dict(self._current_session.proxy_url)

    def handle_response(self, response: requests.Response) -> None:
        """
        Handle response and trigger failover if CloudFront ban detected.
        Call this after every request to check for ban.
        """
        if not self.primary_proxy_url:
            return
        
        if self._detect_cloudfront_ban(response):
            LOG.error(
                "CloudFront ban detected via %s. x-cache=%s, status=%s",
                self._current_session.proxy_url if self._current_session else "unknown",
                response.headers.get("x-cache", ""),
                response.status_code,
            )
            
            with self._lock:
                if self._current_session:
                    self._current_session.fail_count += 1
                    
                    # Rotate to next proxy
                    if len(self._all_proxies) > 1:
                        self._current_session = self._rotate_proxy(self._current_session)
                    else:
                        LOG.error("No failover proxies available, stuck on banned proxy")

    def get_status(self) -> dict[str, Any]:
        """Get current proxy status for monitoring."""
        if not self._current_session:
            return {
                "enabled": bool(self.primary_proxy_url),
                "current_proxy": None,
                "session_age_minutes": None,
                "fail_count": 0,
            }
        
        session_age = (datetime.now(timezone.utc) - self._current_session.session_start).total_seconds() / 60
        
        return {
            "enabled": bool(self.primary_proxy_url),
            "current_proxy": self._current_session.proxy_url,
            "session_age_minutes": round(session_age, 1),
            "fail_count": self._current_session.fail_count,
            "sticky_minutes": self.sticky_minutes,
            "failover_available": len(self._all_proxies) > 1,
        }
