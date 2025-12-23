"""
Security utilities for CommerceTXT.
Prevents SSRF and network attacks.
Protect the internal perimeter.
"""

import ipaddress
import socket
import re
from urllib.parse import urlparse

# Private and reserved IP ranges.
# Keep the local network dark.
BLOCKED_IPS = [
    "127.0.0.0/8",  # Localhost
    "10.0.0.0/8",  # Private Class A
    "172.16.0.0/12",  # Private Class B
    "192.168.0.0/16",  # Private Class C
    "169.254.0.0/16",  # Link-local
    "0.0.0.0/32",  # Default route
    "::1/128",  # IPv6 localhost
    "fc00::/7",  # IPv6 private
    "fe80::/10",  # IPv6 link-local
]


def is_safe_url(url: str) -> bool:
    """
    Check if URL is safe to fetch.
    Blocks octal, hex, integer, localhost, and private IPs.
    """
    try:
        if not url or not isinstance(url, str):
            return False

        if "\\" in url:
            return False

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Clean the host. Strip brackets for IPv6. Lowercase only.
        clean_host = hostname.strip("[]").lower()
        if clean_host == "localhost":
            return False

        # 1. Block Octal and Hex notations before normalization.
        # This stops bypass attempts using exotic IP formats.
        octets = clean_host.split(".")
        for octet in octets:
            # Block octal (e.g., 0177.0.0.1)
            if re.match(r"^0[0-7]+$", octet):
                return False
            # Block hex (e.g., 0x7f.0.0.1)
            if re.match(r"^0x[0-9a-f]+$", octet):
                return False

        # 2. Block Integer IP notation (e.g., http://2130706433/).
        # Prevents bypassing filters via long-form integer addresses.
        if "." not in clean_host and clean_host.isdigit():
            try:
                ip_int = int(clean_host)
                # Check if it falls within 127.0.0.0/8 (2130706432 - 2147483647)
                if 2130706432 <= ip_int <= 2147483647:
                    return False
            except (ValueError, OverflowError):
                pass

        # 3. Collect IPs to check against the blacklist.
        hosts_to_check = {clean_host}
        try:
            # Resolve through system. Final line of defense.
            hosts_to_check.add(socket.gethostbyname(clean_host))
        except (socket.gaierror, ValueError):
            pass

        # 4. Validate every IP against the reserved ranges.
        for h in hosts_to_check:
            try:
                ip = ipaddress.ip_address(h)
                for blocked in BLOCKED_IPS:
                    if ip in ipaddress.ip_network(blocked):
                        return False
            except ValueError:
                continue

        return True
    except Exception:
        return False
