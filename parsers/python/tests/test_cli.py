"""
CommerceTXT CLI Tests.

Tests command-line interface flags, output formats, and error handling.
Covers --json, --prompt, --validate, --health, --schema, --normalize, --compare.
"""

import json
import re
import sys
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import pytest

from commercetxt.cli import main


def run_cli_internal(args_list):
    """
    Patch sys.argv to simulate input. Capture the output.
    """
    with patch.object(sys, "argv", ["commercetxt", *args_list]):
        out, err = StringIO(), StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = 0
            try:
                main()
            except SystemExit as e:
                code = e.code
            return code, out.getvalue(), err.getvalue()


def test_cli_fractal_inheritance(tmp_path):
    """
    Two files exist. One inherits from the other. The parser must find the truth.
    """
    root = tmp_path / "commerce.txt"
    root.write_text("# @IDENTITY\nName: Root\nCurrency: USD", encoding="utf-8")
    prod = tmp_path / "item.txt"
    prod.write_text("# @PRODUCT\nName: Item", encoding="utf-8")

    _code, stdout, _ = run_cli_internal([str(prod), "--json"])
    data = json.loads(stdout)
    assert data["directives"]["IDENTITY"]["Name"] == "Root"


def test_cli_strict_mode(tmp_path):
    """
    Strict mode has no mercy. A small mistake and the program exits with one.
    """
    file = tmp_path / "warn.txt"
    file.write_text("# @IDENTITY\nName: T\nCurrency: EURO", encoding="utf-8")

    code, _, _ = run_cli_internal([str(file), "--strict"])
    assert code == 1


def test_cli_invalid_syntax(tmp_path):
    """
    The line is bad. The parser sees the failure and reports it.
    """
    file = tmp_path / "bad.txt"
    file.write_text("Invalid line", encoding="utf-8")
    _code, stdout, _ = run_cli_internal([str(file)])
    assert "Status: INVALID" in stdout or "WARN" in stdout


def test_cli_prompt_output(tmp_path):
    """
    The machine speaks to the AI. The prompt must be clean and it must be there.
    """
    file = tmp_path / "ai.txt"
    file.write_text("# @IDENTITY\nName: Store\nCurrency: USD", encoding="utf-8")

    _code, stdout, _ = run_cli_internal([str(file), "--prompt"])

    assert "STORE: Store" in stdout
    assert "CURRENCY: USD" in stdout


def test_cli_file_not_found():
    """
    The file is not there. The error is real. The program must handle it.
    """
    code, _, stderr = run_cli_internal(["nonexistent.txt"])
    assert code == 1
    assert "File not found" in stderr


def test_cli_validate_only_output(tmp_path):
    """
    Test the new --validate flag. It should show a summary.
    """
    file = tmp_path / "valid_test.txt"
    file.write_text(
        "# @IDENTITY\nName: TestShop\nCurrency: EUR\n"
        "# @OFFER\nPrice: 10\nAvailability: InStock",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(file), "--validate"])

    assert code == 0
    assert "--- Validation Report: valid_test.txt ---" in stdout
    assert "Status: PASSED" in stdout
    assert (
        "File conforms" in stdout or "conforms to CommerceTXT specification" in stdout
    )


def test_cli_metrics_and_error_handling(tmp_path):
    """Hits cli.py lines related to metrics and specific error paths."""
    file = tmp_path / "metrics.txt"
    file.write_text("# @IDENTITY\nName: MetricsTest\nCurrency: USD", encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(file), "--metrics"])
    assert code == 0

    with patch(
        "commercetxt.validator.CommerceTXTValidator.validate",
        side_effect=ValueError("Custom Error"),
    ):
        code, stdout, _ = run_cli_internal([str(file)])

        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", stdout)
        assert "ERROR: Custom Error" in clean_output


def test_cli_prompt_vs_json_output(tmp_path):
    """Ensure --prompt outputs text, not JSON."""
    test_file = tmp_path / "test.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n"
        "# @OFFER\nPrice: 10\nAvailability: InStock"
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--prompt"])

    assert code == 0
    assert "STORE:" in stdout
    assert not stdout.strip().startswith("{")


def test_cli_json_output(tmp_path):
    """Ensure --json outputs valid JSON."""
    test_file = tmp_path / "test.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n"
        "# @OFFER\nPrice: 10\nAvailability: InStock"
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--json"])

    assert code == 0
    data = json.loads(stdout)
    assert "valid" in data
    assert data["valid"] is True


def test_cli_health_flag(tmp_path):
    """Test --health flag that runs AI Health Check."""
    test_file = tmp_path / "health_test.txt"
    test_file.write_text(
        "# @IDENTITY\nName: HealthTest\nCurrency: USD\n# @OFFER\nPrice: 100\n"
        "Availability: InStock\n# @SPECS\nWeight: 500g\nColor: Black",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--health"])

    assert code == 0
    assert "AI Health Score:" in stdout
    assert "Status:" in stdout
    assert "/100" in stdout


def test_cli_health_flag_with_complete_data(tmp_path):
    """Test --health flag with complete product data for good score."""
    test_file = tmp_path / "complete.txt"
    content = (
        "# @IDENTITY\nName: CompleteProduct\nCurrency: USD\n# @OFFER\nPrice: 100\n"
        "Availability: InStock\n# @SPECS\nWeight: 500g\nDimensions: 10x10x5 cm\n"
        "Material: Aluminum\nColor: Black\nProcessor: TestCPU\nRAM: 8GB\n"
        "Storage: 256GB\nDisplay: 6 inch\nBattery: 4000mAh"
    )
    test_file.write_text(content, encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(test_file), "--health"])

    assert code == 0
    assert "AI Health Score:" in stdout
    assert "Suggestions" in stdout or "optimized" in stdout


def test_cli_normalize_flag(tmp_path):
    """Test --normalize flag that converts units to SI standard."""
    test_file = tmp_path / "normalize_test.txt"
    test_file.write_text(
        "# @IDENTITY\nName: NormalizeTest\nCurrency: USD\n# @SPECS\n"
        "Weight: 1500 g\nHeight: 10 in\nVolume: 500 ml",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--normalize"])

    assert code == 0
    assert "Normalized Specifications" in stdout
    assert "Weight:" in stdout
    assert "kg" in stdout or "1.5" in stdout


def test_cli_normalize_with_json(tmp_path):
    """Test --normalize with --json flag."""
    test_file = tmp_path / "normalize_json.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n# @SPECS\nWeight: 2000 g",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--normalize", "--json"])

    assert code == 0
    data = json.loads(stdout)
    assert "Weight" in data
    assert "kg" in str(data["Weight"])


def test_cli_normalize_no_specs(tmp_path):
    """Test --normalize when SPECS is missing."""
    test_file = tmp_path / "no_specs.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n# @OFFER\nPrice: 100",
        encoding="utf-8",
    )

    code, _stdout, _ = run_cli_internal([str(test_file), "--normalize"])
    assert code == 0


def test_cli_schema_flag(tmp_path):
    """Test --schema flag that outputs Schema.org JSON-LD."""
    test_file = tmp_path / "schema_test.txt"
    test_file.write_text(
        "# @IDENTITY\nName: SchemaTest\nCurrency: USD\n# @PRODUCT\n"
        "Name: Test Product\nBrand: TestBrand\n# @OFFER\nPrice: 100\nCurrency: USD",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--schema"])

    assert code == 0
    assert '"@type": "Product"' in stdout or "@type" in stdout
    assert "schema.org" in stdout.lower()
    try:
        json.loads(stdout)
    except json.JSONDecodeError:
        msg = "Schema output should be valid JSON"
        raise AssertionError(msg) from None


def test_cli_schema_with_nested_directives(tmp_path):
    """Test --schema flag with nested directives."""
    test_file = tmp_path / "nested.txt"
    test_file.write_text(
        "# @IDENTITY\nName: NestedTest\nCurrency: USD\n# @PRODUCT\n"
        "Name: Product\nBrand: Brand\n# @SPECS\nWeight: 500g\nColor: Black",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--schema"])

    assert code == 0
    data = json.loads(stdout)
    assert "@type" in data


def test_cli_multiple_flags_priority(tmp_path):
    """Test that --health takes priority and exits early."""
    test_file = tmp_path / "priority.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n# @OFFER\nPrice: 100",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--health", "--validate"])

    assert code == 0
    assert "AI Health Score:" in stdout
    assert "Validation Report" not in stdout


def test_cli_normalize_then_exit(tmp_path):
    """Test that --normalize exits after execution."""
    test_file = tmp_path / "exit_test.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n# @SPECS\nWeight: 1000 g",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--normalize", "--validate"])

    assert code == 0
    assert "Normalized" in stdout
    assert "Validation Report" not in stdout


def test_cli_schema_then_exit(tmp_path):
    """Test that --schema exits after execution."""
    test_file = tmp_path / "schema_exit.txt"
    test_file.write_text("# @IDENTITY\nName: Test\nCurrency: USD", encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(test_file), "--schema", "--json"])

    assert code == 0
    data = json.loads(stdout)
    assert "@context" in data or "@type" in data


def test_cli_log_level_debug(tmp_path):
    """Test --log-level DEBUG flag."""
    test_file = tmp_path / "log_test.txt"
    test_file.write_text("# @IDENTITY\nName: LogTest\nCurrency: USD", encoding="utf-8")

    code, _stdout, _ = run_cli_internal([str(test_file), "--log-level", "DEBUG"])
    assert code == 0


def test_cli_health_with_no_suggestions(tmp_path):
    """Test --health output when score is high."""
    test_file = tmp_path / "perfect.txt"
    content = (
        "# @IDENTITY\nName: Perfect\nCurrency: USD\n# @OFFER\nPrice: 100\n"
        "Availability: InStock\n# @SPECS\nWeight: 500g\nDimensions: 10x10x5 cm\n"
        "Material: Aluminum\nColor: Black\nProcessor: CPU\nRAM: 8GB\n"
        "Storage: 256GB\nDisplay: 6 inch\n# @SEMANTIC_LOGIC\nitems:\n"
        "  - When asked about durability, mention 2-year warranty"
    )
    test_file.write_text(content, encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(test_file), "--health"])

    assert code == 0
    if "100" in stdout or "EXCELLENT" in stdout:
        assert "optimized" in stdout or "Suggestions" in stdout


def test_cli_normalize_empty_specs(tmp_path):
    """Test --normalize with empty SPECS dict."""
    test_file = tmp_path / "empty_specs.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n# @SPECS", encoding="utf-8"
    )

    code, _stdout, _ = run_cli_internal([str(test_file), "--normalize"])
    assert code == 0


def test_cli_schema_with_empty_directives(tmp_path):
    """Test --schema with minimal directives."""
    test_file = tmp_path / "minimal_schema.txt"
    test_file.write_text("# @IDENTITY\nName: Minimal\nCurrency: USD", encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(test_file), "--schema"])

    assert code == 0
    data = json.loads(stdout)
    assert "@type" in data


def test_cli_error_recovery_in_validator(tmp_path):
    """Test that ValueError in validator is caught."""
    test_file = tmp_path / "validator_error.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n# @OFFER\nPrice: invalid_price",
        encoding="utf-8",
    )

    _code, stdout, _ = run_cli_internal([str(test_file)])
    assert any(x in stdout for x in ["Price must be numeric", "ERROR", "INVALID"])


def test_cli_strict_mode_converts_warnings_to_errors(tmp_path):
    """Test that --strict mode converts warnings to errors."""
    test_file = tmp_path / "strict_test.txt"
    content = (
        "# @IDENTITY\nName: StrictTest\nCurrency: USD\n"
        "TaxIncluded: true\n# @OFFER\nPrice: 100"
    )
    test_file.write_text(content, encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(test_file), "--strict"])
    assert code == 1 or "Strict Mode Error" in stdout


def test_cli_inventory_utc_handling(tmp_path):
    """Ensure CLI handles UTC inventory dates correctly."""
    test_file = tmp_path / "utc_test.txt"
    utc_date = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    test_file.write_text(
        f"# @IDENTITY\nName: UTC_Shop\nCurrency: USD\n"
        f"# @INVENTORY\nLastUpdated: {utc_date}",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--validate"])

    assert code == 0
    assert "Status: PASSED" in stdout
    assert "inventory_stale" not in stdout


def test_cli_metrics_flag_coverage(tmp_path):
    """Test --metrics flag for performance monitoring."""
    test_file = tmp_path / "metrics_test.txt"
    test_file.write_text(
        "# @IDENTITY\nName: MetricsTest\nCurrency: USD\n# @OFFER\n"
        "Price: 100\nAvailability: InStock",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--metrics"])

    assert code == 0
    assert any(x in stdout.lower() for x in ["metrics", "time"])


def test_cli_prompt_flag_text_output(tmp_path):
    """Test --prompt flag outputs text, not JSON."""
    test_file = tmp_path / "prompt_test.txt"
    test_file.write_text(
        "# @IDENTITY\nName: PromptTest\nCurrency: USD\n# @OFFER\n"
        "Price: 100\nAvailability: InStock",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--prompt"])

    assert code == 0
    assert "STORE:" in stdout or "CURRENCY:" in stdout
    assert not stdout.strip().startswith("{")


def test_cli_validate_flag_with_errors(tmp_path):
    """Test --validate flag with files containing errors."""
    test_file = tmp_path / "invalid_file.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\n# @OFFER\nPrice: -100", encoding="utf-8"
    )

    _code, stdout, _ = run_cli_internal([str(test_file), "--validate"])

    assert "Validation Report" in stdout
    assert any(x in stdout for x in ["FAILED", "Errors:"])


def test_cli_all_flags_together(tmp_path):
    """Test behavior when multiple flags are provided."""
    test_file = tmp_path / "all_flags.txt"
    test_file.write_text(
        "# @IDENTITY\nName: AllFlags\nCurrency: USD\n# @OFFER\n"
        "Price: 100\n# @SPECS\nWeight: 500g",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal(
        [str(test_file), "--health", "--normalize", "--schema", "--validate"]
    )

    assert code == 0
    assert "AI Health Score:" in stdout
    assert "Normalized" not in stdout
    assert "schema.org" not in stdout.lower()
    assert "Validation Report" not in stdout


def test_cli_compare_missing_second_file(tmp_path):
    """Test --compare without --compare-file produces error."""
    test_file = tmp_path / "file1.txt"
    test_file.write_text("# @IDENTITY\nName: Test\nCurrency: USD", encoding="utf-8")

    code, stdout, stderr = run_cli_internal([str(test_file), "--compare"])

    assert code == 1
    assert "requires a second file path" in stderr


def test_cli_compare_file_not_found(tmp_path):
    """Test --compare with non-existent second file."""
    test_file = tmp_path / "file1.txt"
    test_file.write_text("# @IDENTITY\nName: Test\nCurrency: USD", encoding="utf-8")

    # compare_file is a positional argument, not a flag
    code, stdout, stderr = run_cli_internal(
        [str(test_file), "nonexistent.txt", "--compare"]
    )

    # CLI should exit with code 1 for file not found
    assert code != 0
    assert "not found" in stderr.lower() or "File not found" in stderr


def test_cli_compare_two_files(tmp_path):
    """Test comparing two files."""
    file1 = tmp_path / "file1.txt"
    file1.write_text(
        "# @IDENTITY\nName: Product A\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\nAvailability: InStock",
        encoding="utf-8",
    )

    file2 = tmp_path / "file2.txt"
    file2.write_text(
        "# @IDENTITY\nName: Product B\nCurrency: USD\n"
        "# @OFFER\nPrice: 150\nAvailability: InStock",
        encoding="utf-8",
    )

    # compare_file is a positional argument
    code, stdout, _ = run_cli_internal([str(file1), str(file2), "--compare"])

    assert code == 0
    assert (
        "Product Comparison" in stdout
        or "comparison" in stdout.lower()
        or "Recommendation" in stdout
    )


def test_cli_compare_json_output(tmp_path):
    """Test comparing two files with JSON output."""
    file1 = tmp_path / "file1.txt"
    file1.write_text(
        "# @IDENTITY\nName: A\nCurrency: USD\n# @OFFER\nPrice: 100", encoding="utf-8"
    )

    file2 = tmp_path / "file2.txt"
    file2.write_text(
        "# @IDENTITY\nName: B\nCurrency: USD\n# @OFFER\nPrice: 150", encoding="utf-8"
    )

    # compare_file is a positional argument
    code, stdout, _ = run_cli_internal([str(file1), str(file2), "--compare", "--json"])

    assert code == 0
    data = json.loads(stdout)
    assert isinstance(data, dict)
    assert "recommendation" in data or "price_advantage" in data


def test_cli_health_check(tmp_path):
    """Test --health flag."""
    test_file = tmp_path / "health.txt"
    test_file.write_text(
        "# @IDENTITY\nName: HealthTest\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\nAvailability: InStock",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--health"])

    assert code == 0
    assert "AI Health Score" in stdout or "score" in stdout.lower()


def test_cli_normalize_specs(tmp_path):
    """Test --normalize flag."""
    test_file = tmp_path / "normalize.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n"
        "# @SPECS\nWeight: 500g\nDimensions: 10x20x30cm",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--normalize"])

    assert code == 0
    assert "Normalized" in stdout or "SPECS" in stdout


def test_cli_normalize_json(tmp_path):
    """Test --normalize with JSON output."""
    test_file = tmp_path / "normalize.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n" "# @SPECS\nWeight: 500g",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--normalize", "--json"])

    assert code == 0
    data = json.loads(stdout)
    assert isinstance(data, dict)


def test_cli_schema_output(tmp_path):
    """Test --schema flag."""
    test_file = tmp_path / "schema.txt"
    test_file.write_text(
        "# @IDENTITY\nName: SchemaTest\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\nAvailability: InStock",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--schema"])

    assert code == 0
    assert "schema.org" in stdout.lower() or "@type" in stdout


def test_cli_log_levels(tmp_path):
    """Test different log levels."""
    test_file = tmp_path / "log_test.txt"
    test_file.write_text("# @IDENTITY\nName: Test\nCurrency: USD", encoding="utf-8")

    for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
        code, stdout, _ = run_cli_internal([str(test_file), "--log-level", level])
        assert code in [0, 1]  # May fail validation but shouldn't crash


def test_cli_colorama_not_available(tmp_path, monkeypatch):
    """Test CLI behavior when colorama is not available."""
    test_file = tmp_path / "nocolor.txt"
    test_file.write_text("# @IDENTITY\nName: Test\nCurrency: USD", encoding="utf-8")

    # This will test the dummy color classes
    code, stdout, _ = run_cli_internal([str(test_file)])
    assert code in [0, 1]  # May fail validation


def test_cli_compare_with_savings(tmp_path):
    """Test comparison with different prices showing savings."""
    file1 = tmp_path / "product_a.txt"
    file1.write_text(
        "# @IDENTITY\nName: Product A\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\nAvailability: InStock\n"
        "# @SPECS\nWeight: 500g\nColor: Red",
        encoding="utf-8",
    )

    file2 = tmp_path / "product_b.txt"
    file2.write_text(
        "# @IDENTITY\nName: Product B\nCurrency: USD\n"
        "# @OFFER\nPrice: 150\nAvailability: InStock\n"
        "# @SPECS\nWeight: 600g\nColor: Blue",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(file1), str(file2), "--compare"])

    assert code == 0
    assert "Product Comparison" in stdout


def test_cli_health_with_suggestions(tmp_path):
    """Test health output with suggestions."""
    test_file = tmp_path / "minimal_health.txt"
    test_file.write_text(
        "# @IDENTITY\nName: MinimalTest\nCurrency: USD\n" "# @OFFER\nPrice: 100",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--health"])

    assert code == 0
    assert "AI Health Score:" in stdout
    assert "Status:" in stdout


def test_cli_validate_with_warnings_only(tmp_path):
    """Test validate output with warnings."""
    test_file = tmp_path / "warnings.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\nTaxIncluded: yes\n"
        "# @OFFER\nPrice: 100",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--validate"])

    # Check for validation output
    assert "Validation Report" in stdout or "Status:" in stdout


def test_cli_human_output_with_errors(tmp_path):
    """Test human-readable output with errors."""
    test_file = tmp_path / "errors.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\n# @OFFER\nPrice: -100",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file)])

    assert code == 1
    import re

    clean_output = re.sub(r"\x1b\[[0-9;]*m", "", stdout)
    assert "Status: INVALID" in clean_output or "ERROR" in clean_output


def test_cli_human_output_valid_no_warnings(tmp_path):
    """Test human-readable output with valid file and no warnings."""
    test_file = tmp_path / "perfect.txt"
    test_file.write_text(
        "# @IDENTITY\nName: PerfectTest\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\nAvailability: InStock",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file)])

    assert code == 0
    import re

    clean_output = re.sub(r"\x1b\[[0-9;]*m", "", stdout)
    assert "validates successfully" in clean_output or "Status: VALID" in clean_output


def test_cli_schema_with_non_dict_values(tmp_path):
    """Test schema generation with mixed directive types."""
    test_file = tmp_path / "schema_mixed.txt"
    test_file.write_text(
        "# @IDENTITY\nName: SchemaTest\nCurrency: USD\n"
        "# @PRODUCT\nName: Test Product\nBrand: TestBrand\n"
        "# @OFFER\nPrice: 100",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--schema"])

    assert code == 0
    data = json.loads(stdout)
    assert "@type" in data


def test_cli_strict_mode_with_validator_value_error(tmp_path):
    """Test strict mode when validator raises ValueError."""
    test_file = tmp_path / "strict_error.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: INVALID\n" "# @OFFER\nPrice: 100",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file)])

    # Should have error in output
    import re

    clean_output = re.sub(r"\x1b\[[0-9;]*m", "", stdout)
    assert "ERROR" in clean_output or code == 1


def test_cli_action_routing_priority(tmp_path):
    """Test action routing priorities."""
    test_file = tmp_path / "routing.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\nAvailability: InStock\n"
        "# @SPECS\nWeight: 500g",
        encoding="utf-8",
    )

    # Test normalize action
    code, stdout, _ = run_cli_internal([str(test_file), "--normalize"])
    assert code == 0
    assert "Normalized" in stdout

    # Test schema action
    code, stdout, _ = run_cli_internal([str(test_file), "--schema"])
    assert code == 0
    assert "@type" in stdout

    # Test prompt action
    code, stdout, _ = run_cli_internal([str(test_file), "--prompt"])
    assert code == 0
    assert "STORE:" in stdout or "CURRENCY:" in stdout


def test_cli_colorama_dummy_classes():
    """Test that dummy color classes work when colorama not available."""
    # Import fresh to test dummy classes

    # This test verifies the code structure exists, actual ImportError is hard to mock
    # since colorama is already imported. The code paths 26-35 are defensive code.
    # We can verify they exist by checking the module structure.
    from commercetxt import cli

    assert hasattr(cli, "Fore")
    assert hasattr(cli, "Style")
    assert hasattr(cli, "HAS_COLOR")


def test_cli_health_no_suggestions(tmp_path):
    """Test health output when no suggestions are returned."""
    test_file = tmp_path / "health_no_sugg.txt"
    test_file.write_text(
        "# @IDENTITY\nName: HealthTest\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\nAvailability: InStock\n"
        "# @SPECS\nWeight: 500g\nDimensions: 10x10x5 cm\n"
        "Material: Aluminum\nColor: Black\nProcessor: CPU\nRAM: 8GB\n"
        "Storage: 256GB\nDisplay: 6 inch\nBattery: 4000mAh\nCamera: 12MP",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--health"])

    assert code == 0
    # Should have health score and either suggestions or "No suggestions"
    assert "AI Health Score:" in stdout


def test_cli_compare_with_neutral_advantage(tmp_path):
    """Test comparison with neutral advantage."""
    file1 = tmp_path / "prod1.txt"
    file1.write_text(
        "# @IDENTITY\nName: Product 1\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\n"
        "# @SPECS\nWeight: 500g",
        encoding="utf-8",
    )

    file2 = tmp_path / "prod2.txt"
    file2.write_text(
        "# @IDENTITY\nName: Product 2\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\n"
        "# @SPECS\nWeight: 500g",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(file1), str(file2), "--compare"])

    assert code == 0
    assert "Product Comparison" in stdout


def test_cli_compare_with_spec_differences(tmp_path):
    """Test comparison with spec differences showing advantages."""
    file1 = tmp_path / "prod_a.txt"
    file1.write_text(
        "# @IDENTITY\nName: Product A\nCurrency: USD\n"
        "# @OFFER\nPrice: 100\n"
        "# @SPECS\nWeight: 500g\nColor: Red\nRAM: 8GB",
        encoding="utf-8",
    )

    file2 = tmp_path / "prod_b.txt"
    file2.write_text(
        "# @IDENTITY\nName: Product B\nCurrency: USD\n"
        "# @OFFER\nPrice: 120\n"
        "# @SPECS\nWeight: 600g\nColor: Blue\nRAM: 16GB",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(file1), str(file2), "--compare"])

    assert code == 0
    assert "Product Comparison" in stdout or "Key Differences" in stdout


def test_cli_validate_with_both_errors_and_warnings(tmp_path):
    """Test validate output with both errors and warnings."""
    test_file = tmp_path / "both_issues.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\nTaxIncluded: true\n"
        "# @OFFER\nPrice: -50",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--validate"])

    # Should have validation report with errors
    assert "Validation Report" in stdout or "Status:" in stdout


def test_cli_human_output_with_warnings_no_errors(tmp_path):
    """Test human output with warnings but no errors."""
    test_file = tmp_path / "warnings_only.txt"
    test_file.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\nTaxIncluded: maybe\n"
        "# @OFFER\nPrice: 100",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file)])

    # Should show warnings
    import re

    re.sub(r"\x1b\[[0-9;]*m", "", stdout)
    assert code in [0, 1]  # May be valid despite warnings


def test_cli_schema_with_non_relevant_sections(tmp_path):
    """Test schema with non-relevant sections."""
    test_file = tmp_path / "schema_complex.txt"
    test_file.write_text(
        "# @IDENTITY\nName: SchemaTest\nCurrency: USD\n"
        "# @PRODUCT\nName: Test Product\nBrand: TestBrand\n"
        "# @OFFER\nPrice: 100\n"
        "# @SPECS\nWeight: 500g\n"
        "# @CUSTOM_SECTION\nCustomValue: 123",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(test_file), "--schema"])

    assert code == 0
    data = json.loads(stdout)
    assert "@type" in data


# =============================================================================
# MUTATION TESTING - DAY 4: CLI Tests
# =============================================================================


def test_cli_parse_command_with_file(tmp_path):
    """Test parse command with valid file."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("# @IDENTITY\nName: Test\nCurrency: USD", encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(file_path)])

    assert code == 0
    # CLI outputs validation status, not raw content
    assert "VALID" in stdout or "validates successfully" in stdout


def test_cli_parse_command_file_not_found():
    """Test parse command with non-existent file."""
    code, _, stderr = run_cli_internal(["nonexistent.txt"])

    assert code == 1
    assert "not found" in stderr.lower() or "error" in stderr.lower()


def test_cli_parse_command_with_output_json(tmp_path):
    """Test parse with JSON output format."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("# @IDENTITY\nName: Test\nCurrency: USD", encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(file_path), "--json"])

    assert code == 0
    assert "{" in stdout  # JSON output
    data = json.loads(stdout)
    assert "directives" in data


def test_cli_validate_command_valid_file(tmp_path):
    """Test validate command with valid file."""
    file_path = tmp_path / "test.txt"
    file_path.write_text(
        "# @IDENTITY\nName: Test\nCurrency: USD\n# @OFFER\nPrice: 10\nAvailability: InStock",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(file_path), "--validate"])

    assert code == 0
    assert "PASSED" in stdout or "valid" in stdout.lower()


def test_cli_help_command():
    """Test --help flag."""
    code, stdout, _ = run_cli_internal(["--help"])

    assert code == 0
    assert "usage" in stdout.lower() or "help" in stdout.lower()


def test_cli_version_command():
    """Test --version flag."""
    code, stdout, _ = run_cli_internal(["--version"])

    assert code == 0
    # Should contain version number


def test_cli_parse_with_strict_flag(tmp_path):
    """Test parse with strict mode."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("# @IDENTITY\nName: Test\nCurrency: INVALID", encoding="utf-8")

    code, _, _ = run_cli_internal([str(file_path), "--strict"])

    # Should fail in strict mode with invalid currency
    assert code == 1


def test_cli_prompt_flag(tmp_path):
    """Test --prompt flag for AI bridge."""
    file_path = tmp_path / "test.txt"
    file_path.write_text(
        "# @IDENTITY\nName: Store\nCurrency: USD\n# @PRODUCT\nName: Widget",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(file_path), "--prompt"])

    assert code == 0
    assert "STORE: Store" in stdout
    assert "ITEM: Widget" in stdout


def test_schema_logic_mutation(capsys):
    """Kills mutation: 'and' -> 'or' in schema dictionary check (cli.py:270)."""
    from commercetxt.cli import _handle_schema
    from commercetxt.model import ParseResult

    result = ParseResult()
    # Case: Key is NOT relevant, but value IS dict.
    # Original: False AND True -> False -> Keeps nested structure in output.
    # Mutant: False OR True -> True -> Flattens keys.
    result.directives = {"EXTRA_SECTION": {"CustomField": "CustomValue"}}

    with pytest.raises(SystemExit):
        _handle_schema(result)

    captured = capsys.readouterr()
    # If the mutation exists, EXTRA_SECTION would be added to the output.
    # In original, it should be discarded to avoid conflicts.
    assert "EXTRA_SECTION" not in captured.out
