"""
Security utilities for CommerceTXT.
Prevents SSRF and network attacks.
Protect the internal perimeter.
"""

import ipaddress
import re
import socket
from functools import lru_cache
from urllib.parse import urlparse

from .constants import LOOPBACK_IP_END, LOOPBACK_IP_START, MAX_URL_LENGTH

BLOCKED_IPS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "0.0.0.0/32",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]


def is_safe_url(url: str) -> bool:
    """Check if URL is safe to fetch."""
    # Combine basic validation checks
    if not url or not isinstance(url, str) or len(url) > MAX_URL_LENGTH or "\\" in url:
        return False

    try:
        parsed = urlparse(url)
        # Combine scheme and hostname checks
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False

        clean_host = parsed.hostname.strip("[]").lower()

        if clean_host == "localhost":
            return False

        if _is_blocked_pattern(clean_host):
            return False

        return _is_safe_host(clean_host)

    except Exception:
        return False


def _is_blocked_pattern(host: str) -> bool:
    """Check for octal, hex, or integer IP bypass attempts."""
    octets = host.split(".")
    for octet in octets:
        if re.match(r"^0[0-7]+$", octet):
            return True
        if re.match(r"^0x[0-9a-f]+$", octet):
            return True

    if "." not in host and host.isdigit():
        try:
            ip_int = int(host)
            if LOOPBACK_IP_START <= ip_int <= LOOPBACK_IP_END:
                return True
        except (ValueError, OverflowError):
            pass
    return False


@lru_cache(maxsize=1000)
def _resolve_host(host: str) -> str | None:
    """
    Cached DNS resolution.

    Returns the resolved IP address or None if resolution fails.
    Cache size of 1000 covers typical application needs while preventing
    memory exhaustion.

    Performance: ~1000x faster for repeated checks of the same host.
    """
    try:
        return socket.gethostbyname(host)
    except (socket.gaierror, ValueError):
        return None


def _is_safe_host(host: str) -> bool:
    """
    Resolve and check against blocked IP ranges.

    Uses cached DNS resolution to avoid repeated lookups for the same host.
    """
    hosts_to_check = {host}

    # Use cached DNS resolution
    resolved = _resolve_host(host)
    if resolved:
        hosts_to_check.add(resolved)

    for h in hosts_to_check:
        try:
            ip = ipaddress.ip_address(h)
            for blocked in BLOCKED_IPS:
                if ip in ipaddress.ip_network(blocked):
                    return False
        except ValueError:
            continue
    return True


def clear_dns_cache():
    """
    Clear the DNS resolution cache.

    Useful for:
    - Testing (ensure clean state)
    - Development (refresh DNS after changes)
    - Production (periodic cleanup if needed)

    Example:
        from commercetxt.security import clear_dns_cache
        clear_dns_cache()  # Fresh DNS lookups
    """
    _resolve_host.cache_clear()


def get_dns_cache_info() -> dict:
    """
    Get DNS cache statistics.

    Returns:
        dict with keys:
            - hits: Number of cache hits
            - misses: Number of cache misses
            - maxsize: Maximum cache size
            - currsize: Current cache size

    Example:
        from commercetxt.security import get_dns_cache_info
        info = get_dns_cache_info()
        print(f"Cache hit rate: {info['hits']/(info['hits']+info['misses']):.1%}")
    """
    cache_info = _resolve_host.cache_info()
    return {
        "hits": cache_info.hits,
        "misses": cache_info.misses,
        "maxsize": cache_info.maxsize,
        "currsize": cache_info.currsize,
    }
