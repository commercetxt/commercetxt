import json
import sys
from unittest.mock import patch
from io import StringIO
from commercetxt.cli import main


def run_cli_internal(args_list):
    """
    Patch sys.argv to simulate input. Capture the output. It is simple.
    """
    with patch.object(sys, "argv", ["commercetxt"] + args_list):
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

    code, stdout, _ = run_cli_internal([str(prod), "--json"])
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
    code, stdout, _ = run_cli_internal([str(file)])
    assert "Status: INVALID" in stdout or "WARN" in stdout


def test_cli_prompt_output(tmp_path):
    """
    The machine speaks to the AI. The prompt must be clean and it must be there.
    """
    file = tmp_path / "ai.txt"
    file.write_text("# @IDENTITY\nName: Store\nCurrency: USD", encoding="utf-8")

    code, stdout, _ = run_cli_internal([str(file), "--prompt"])

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
    Test the new --validate flag. It should show a summary without product details.
    """
    file = tmp_path / "valid_test.txt"
    file.write_text(
        "# @IDENTITY\nName: TestShop\nCurrency: EUR\n# @OFFER\nPrice: 10\nAvailability: InStock",
        encoding="utf-8",
    )

    code, stdout, _ = run_cli_internal([str(file), "--validate"])

    assert code == 0
    assert "--- Validation Report: valid_test.txt ---" in stdout
    assert "Status: PASSED" in stdout
    assert "Conclusion: File conforms" in stdout


def test_cli_metrics_and_error_handling(tmp_path):
    """Hits cli.py lines related to metrics and specific error paths."""
    file = tmp_path / "metrics.txt"
    file.write_text("# @IDENTITY\nName: MetricsTest\nCurrency: USD", encoding="utf-8")

    # Test metrics flag
    code, stdout, _ = run_cli_internal([str(file), "--metrics"])
    assert code == 0

    # Test error handling by mocking an exception in the validator
    with patch(
        "commercetxt.validator.CommerceTXTValidator.validate",
        side_effect=ValueError("Custom Error"),
    ):
        code, stdout, _ = run_cli_internal([str(file)])
        assert "ERROR: Custom Error" in stdout
