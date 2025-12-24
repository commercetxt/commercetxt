"""
Tests for CommerceTXT vectors.
The files are in the folders. We read them and we see if they are true.
"""

import pytest
from pathlib import Path
from commercetxt import CommerceTXTParser, CommerceTXTValidator


def get_vector_files(folder_name):
    """Find all text files in the vector subfolder."""
    base_path = Path(__file__).parent / "vectors" / folder_name
    if not base_path.exists():
        return []
    return [str(p) for p in base_path.glob("*.txt")]


class TestVectors:
    """
    A class to test different scenarios.
    Good files must be good. Bad files must be caught.
    """

    @pytest.mark.parametrize("file_path", get_vector_files("valid"))
    def test_valid_vectors(self, file_path):
        """These files are clean. They must have no errors."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        parser = CommerceTXTParser()
        result = parser.parse(content)

        validator = CommerceTXTValidator()
        validator.validate(result)

        assert not result.errors, f"File {Path(file_path).name} failed validation."

    @pytest.mark.parametrize("file_path", get_vector_files("errors"))
    def test_error_vectors(self, file_path):
        """These files are broken. The validator must find the fault."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        parser = CommerceTXTParser()
        result = parser.parse(content)

        validator = CommerceTXTValidator()
        validator.validate(result)

        assert (
            len(result.errors) > 0
        ), f"File {Path(file_path).name} should have errors."

    @pytest.mark.parametrize("file_path", get_vector_files("warnings"))
    def test_warning_vectors(self, file_path):
        """These files are not perfect. There must be warnings."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        parser = CommerceTXTParser()
        result = parser.parse(content)

        validator = CommerceTXTValidator()
        validator.validate(result)

        assert (
            len(result.warnings) > 0
        ), f"File {Path(file_path).name} should have warnings."

    @pytest.mark.parametrize("file_path", get_vector_files("syntax_warnings"))
    def test_syntax_vectors(self, file_path):
        """The syntax is wrong. The parser must see it early."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        parser = CommerceTXTParser()
        result = parser.parse(content)

        assert (
            len(result.warnings) > 0 or len(result.errors) > 0
        ), f"File {Path(file_path).name} syntax passed."
