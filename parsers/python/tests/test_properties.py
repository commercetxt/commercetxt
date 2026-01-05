"""
Property-based tests for CommerceTXT parser, validator, and resolver.
Ensures robustness, correctness, and security across diverse inputs.
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from commercetxt.model import ParseResult
from commercetxt.parser import CommerceTXTParser
from commercetxt.resolver import CommerceTXTResolver
from commercetxt.validator import CommerceTXTValidator

# ---------------------------------------------------------
# Common setup
# ---------------------------------------------------------

parser = CommerceTXTParser(strict=False)
validator = CommerceTXTValidator(strict=False)
resolver = CommerceTXTResolver()


# ---------------------------------------------------------
# Property 1: Parser is a total function
# ---------------------------------------------------------


@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(st.text())
def test_parser_never_crashes(random_text):
    """
    For any text input, the parser must:
    - never crash
    - always return a ParseResult
    """
    result = parser.parse(random_text)

    assert isinstance(result, ParseResult)
    assert hasattr(result, "directives")
    assert hasattr(result, "errors")
    assert hasattr(result, "warnings")


# ---------------------------------------------------------
# Property 2: Validation is monotonic
# ---------------------------------------------------------


@settings(max_examples=200)
@given(st.text())
def test_validation_monotonic(random_text):
    """
    Validation must be monotonic:
    it may add errors/warnings, but never remove them.
    """
    result = parser.parse(random_text)

    validator.validate(result)

    errors_1 = list(result.errors)
    warnings_1 = list(result.warnings)
    trust_1 = list(result.trust_flags)

    validator.validate(result)

    assert len(result.errors) >= len(errors_1)
    assert len(result.warnings) >= len(warnings_1)
    assert len(result.trust_flags) >= len(trust_1)


# ---------------------------------------------------------
# Property 3: Resolver merge is idempotent
# ---------------------------------------------------------


@settings(max_examples=200)
@given(st.text())
def test_merge_semantically_idempotent(random_text):
    """
    Merging a context with itself must preserve semantics.
    Diagnostics may differ in ordering or line numbers.
    """
    result = parser.parse(random_text)

    merged = resolver.merge(result, result)

    assert merged.directives == result.directives
    assert merged.errors == result.errors
    assert set(merged.trust_flags) == set(result.trust_flags)


# ---------------------------------------------------------
# Property 4: Resolver merge is deterministic
# ---------------------------------------------------------


@settings(max_examples=200)
@given(st.text(), st.text())
def test_merge_deterministic(a, b):
    """
    Given the same inputs, merge must always produce the same output.
    """
    r1 = parser.parse(a)
    r2 = parser.parse(b)

    m1 = resolver.merge(r1, r2)
    m2 = resolver.merge(r1, r2)

    assert m1.directives == m2.directives
    assert m1.errors == m2.errors
    assert m1.warnings == m2.warnings
    assert m1.trust_flags == m2.trust_flags


# ---------------------------------------------------------
# Property 5: Security layer never crashes via resolver
# ---------------------------------------------------------


@settings(max_examples=200)
@given(st.text())
def test_security_layer_never_crashes(random_text):
    """
    Security logic must never crash on untrusted input.
    It is exercised indirectly via resolver.
    """
    parser = CommerceTXTParser(strict=False)
    resolver = CommerceTXTResolver()

    result = parser.parse(random_text)

    try:
        resolver.merge(result, result)
    except Exception as exc:
        msg = f"Security layer crashed: {exc}"
        raise AssertionError(msg) from exc
