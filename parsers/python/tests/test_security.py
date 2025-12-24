"""
Security tests for CommerceTXT.
Ensures protection against SSRF, DoS, and malicious obfuscation attempts.
"""

import socket
from unittest.mock import patch

from commercetxt.security import is_safe_url
from commercetxt.parser import CommerceTXTParser
from commercetxt.resolver import resolve_path
from commercetxt.limits import MAX_LINE_LENGTH


# ============================================================================
# 1. NETWORK PERIMETER PROTECTION (SSRF PREVENTION)
# ============================================================================


def test_blocks_localhost_variants():
    """Localhost is strictly for the internal owner. The parser must not access it."""
    assert is_safe_url("http://localhost/file.txt") is False
    assert is_safe_url("https://localhost:8080/api") is False
    assert is_safe_url("http://127.0.0.1/admin") is False
    assert is_safe_url("http://[::1]/file.txt") is False


def test_blocks_localhost_case_insensitive():
    """Case sensitivity should not bypass localhost blocking."""
    assert is_safe_url("http://LOCALHOST/file") is False
    assert is_safe_url("http://LocalHost/file") is False


def test_blocks_private_ranges():
    """Private IPv4 ranges (RFC 1918) must be blocked to prevent internal scanning."""
    assert is_safe_url("http://10.0.0.1/data") is False
    assert is_safe_url("http://172.16.0.1/internal") is False
    assert is_safe_url("http://192.168.0.1/router") is False
    assert is_safe_url("http://169.254.169.254/metadata") is False


# ============================================================================
# 2. URI SCHEME & INPUT VALIDATION
# ============================================================================


def test_blocks_unsafe_schemes():
    """Only web-based schemes (HTTP/HTTPS) are permitted. File/FTP are dangerous."""
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("ftp://example.com/file") is False
    assert is_safe_url("gopher://server.com") is False


def test_allows_web_only():
    """Standard web protocols must be allowed for remote resolution."""
    assert is_safe_url("http://example.com/file") is True
    assert is_safe_url("https://secure.example.com/api") is True


def test_handles_invalid_input_gracefully():
    """Malformed or null inputs should fail safely without crashing."""
    assert is_safe_url(None) is False
    assert is_safe_url("") is False
    assert is_safe_url("not-a-url") is False


def test_missing_hostname_coverage():
    """Covers line 45: Block URLs that result in empty hostnames."""
    assert is_safe_url("http:///path/to/resource") is False


# ============================================================================
# 3. OBFUSCATION & BYPASS DEFENSE
# ============================================================================


def test_blocks_exotic_ip_notation():
    """Block exotic IP formats (Octal, Hex, Integer) used to bypass filters."""
    assert is_safe_url("http://0177.0.0.1/file") is False  # Octal
    assert is_safe_url("http://0x7f.0.0.1/file") is False  # Hex
    assert is_safe_url("http://2130706433/file") is False  # Integer


def test_blocks_url_with_at_symbol():
    """The @ symbol used for user-auth spoofing must be blocked if pointing to local hosts."""
    assert is_safe_url("http://example.com@localhost/file") is False


def test_blocks_backslash_confusion():
    """Backslashes used in obfuscation (line 37) must be rejected."""
    assert is_safe_url("https://example.com\\@google.com") is False
    assert is_safe_url("https://example.com\\admin") is False


# ============================================================================
# 4. RESOURCE LIMITS (DoS PROTECTION)
# ============================================================================


def test_dos_sections_limit():
    """Prevent Denial of Service by limiting the total number of allowed sections."""
    parser = CommerceTXTParser()
    content = "\n".join([f"# @SECTION_{i}\nKey: Value" for i in range(1500)])
    result = parser.parse(content)

    assert len(result.directives) <= 1000
    assert any("limit" in w.lower() for w in result.warnings)


def test_redos_long_line():
    """Protect against ReDoS and memory exhaustion from excessively long lines."""
    parser = CommerceTXTParser()
    huge_line = "Key: " + "A" * (MAX_LINE_LENGTH + 5000)
    result = parser.parse(huge_line)

    assert any("length" in w.lower() for w in result.warnings)


# ============================================================================
# 5. EXCEPTION HANDLING & COVERAGE (MOCKING)
# ============================================================================


def test_socket_resolution_failure_coverage():
    """
    Manually triggers gaierror handling (lines 93-94).
    Ensures the parser continues safely if DNS resolution fails.
    """
    with patch("socket.gethostbyname") as mock_socket:
        mock_socket.side_effect = socket.gaierror("DNS lookup failed")
        # Function catches error and proceeds; remains True for safe domains
        assert is_safe_url("http://safe-domain.com") is True


def test_integer_ip_overflow_coverage():
    """
    Manually triggers OverflowError handling (lines 71-72).
    Blocks integer IPs that exceed system bounds.
    """
    with patch("builtins.int") as mock_int:
        mock_int.side_effect = OverflowError("Integer too large")
        assert is_safe_url("http://2130706433/") is False


def test_ssrf_resolve_protection():
    """Ensure the high-level resolver utilizes security checks to block unsafe paths."""

    def dummy_loader(path):
        return "Content"

    unsafe_urls = ["http://localhost/admin", "file:///etc/passwd"]
    for url in unsafe_urls:
        result = resolve_path(url, dummy_loader)
        # Verify that security warnings or errors are raised
        found_security_error = any(
            "security" in e.lower() or "blocked" in e.lower() for e in result.errors
        )
        assert found_security_error, f"Failed to block unsafe path: {url}"
