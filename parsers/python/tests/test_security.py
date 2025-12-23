"""
Security tests for CommerceTXT.
The code must protect the machine from the network.
"""

from commercetxt.security import is_safe_url
from commercetxt.parser import CommerceTXTParser
from commercetxt.resolver import resolve_path
from commercetxt.limits import MAX_LINE_LENGTH


# ============================================================================
# 1. LOCALHOST BLOCKING (IPv4 + IPv6)
# ============================================================================


def test_blocks_localhost_variants():
    """Localhost is for the owner. The parser must stay out."""
    assert is_safe_url("http://localhost/file.txt") is False
    assert is_safe_url("https://localhost:8080/api") is False
    assert is_safe_url("http://127.0.0.1/admin") is False
    assert is_safe_url("http://[::1]/file.txt") is False


def test_blocks_localhost_case_insensitive():
    """Capital letters do not make a lie true. It is still localhost."""
    assert is_safe_url("http://LOCALHOST/file") is False
    assert is_safe_url("http://LocalHost/file") is False


# ============================================================================
# 2. PRIVATE IP BLOCKING (RFC 1918)
# ============================================================================


def test_blocks_private_ranges():
    """Private networks are for families and firms. Not for the parser."""
    assert is_safe_url("http://10.0.0.1/data") is False
    assert is_safe_url("http://172.16.0.1/internal") is False
    assert is_safe_url("http://192.168.0.1/router") is False
    assert is_safe_url("http://169.254.169.254/metadata") is False


# ============================================================================
# 3. SCHEME VALIDATION
# ============================================================================


def test_blocks_unsafe_schemes():
    """File and FTP are old ways. They are dangerous here."""
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("ftp://example.com/file") is False
    assert is_safe_url("gopher://server.com") is False


def test_allows_web_only():
    """The web is HTTP and HTTPS. These are allowed."""
    assert is_safe_url("http://example.com/file") is True
    assert is_safe_url("https://secure.example.com/api") is True


# ============================================================================
# 4. BYPASS ATTEMPTS & EXOTIC NOTATIONS
# ============================================================================


def test_blocks_exotic_ip_notation():
    """Numbers can be written in many ways. The truth remains the same."""
    assert is_safe_url("http://0177.0.0.1/file") is False  # Octal
    assert is_safe_url("http://0x7f.0.0.1/file") is False  # Hex
    assert is_safe_url("http://2130706433/file") is False  # Integer


def test_blocks_url_with_at_symbol():
    """The @ symbol is a trick to hide the destination. We do not fall for it."""
    assert is_safe_url("http://example.com@localhost/file") is False


# ============================================================================
# 5. RESOURCE LIMITS (DoS PROTECTION)
# ============================================================================


def test_dos_sections_limit():
    """A man must know his limits. A parser must too."""
    parser = CommerceTXTParser()
    content = "\n".join([f"# @SECTION_{i}\nKey: Value" for i in range(1500)])
    result = parser.parse(content)

    assert len(result.directives) <= 1000
    assert any("limit" in w.lower() for w in result.warnings)


def test_redos_long_line():
    """A line that never ends is an attack. We cut it short."""
    parser = CommerceTXTParser()
    huge_line = "Key: " + "A" * (MAX_LINE_LENGTH + 5000)
    result = parser.parse(huge_line)

    assert any("length" in w.lower() for w in result.warnings)


def test_ssrf_resolve_protection():
    """
    The resolver must be brave. It must block the local paths.
    If a path is bad, the error must be clear.
    """

    def dummy_loader(path):
        return "Content"

    unsafe_urls = ["http://localhost/admin", "file:///etc/passwd"]
    for url in unsafe_urls:
        result = resolve_path(url, dummy_loader)
        # Check if any error contains the word "Security" or "Blocked"
        found_security_error = any(
            "security" in e.lower() or "blocked" in e.lower() for e in result.errors
        )
        assert found_security_error, f"Failed to block unsafe path: {url}"


# ============================================================================
# 6. EDGE CASES
# ============================================================================


def test_handles_invalid_input_gracefully():
    """Broken things should not break the program. They should just fail."""
    assert is_safe_url(None) is False
    assert is_safe_url("") is False
    assert is_safe_url("not-a-url") is False
