# conftest.py
import pytest
import sys
from io import StringIO
from unittest.mock import patch
from commercetxt.cli import main


@pytest.fixture
def run_cli():
    """Fixture that provides the CLI execution logic to all tests."""

    def _run(args_list):
        with patch.object(sys, "argv", ["commercetxt"] + args_list):
            out, err = StringIO(), StringIO()
            with patch("sys.stdout", out), patch("sys.stderr", err):
                code = 0
                try:
                    main()
                except SystemExit as e:
                    code = e.code
                return code, out.getvalue(), err.getvalue()

    return _run
