"""
CommerceTXT Command Line Interface.
Provides a CLI for parsing, validating, and processing commerce.txt files.

Enhancement: Added colored output support (optional, graceful fallback).
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Optional color support (graceful fallback if not installed)
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

    # Create dummy color constants for compatibility when colorama not installed
    class _DummyColor:
        def __getattr__(self, name: str) -> str:
            return ""

    Fore = _DummyColor()  # type: ignore[assignment]
    Style = _DummyColor()  # type: ignore[assignment]

from . import __version__
from .bridge import CommerceAIBridge
from .constants import CLI_SCORE_EXCELLENT, CLI_SCORE_FAIR, CLI_SCORE_GOOD
from .parser import parse_file
from .rag.tools.comparator import ProductComparator
from .rag.tools.health_check import AIHealthChecker
from .rag.tools.normalizer import SemanticNormalizer
from .rag.tools.schema_bridge import SchemaBridge
from .resolver import CommerceTXTResolver
from .validator import CommerceTXTValidator


def main() -> None:
    """Main entry point. Uses action routing to avoid complexity."""
    parser = _create_parser()
    args = parser.parse_args()

    _setup_logging(args.log_level)

    try:
        file_path = _validate_file_path(args.file)
        resolver = CommerceTXTResolver()

        final_result = _load_and_merge(file_path, resolver)

        # Validate the parsed result (catch ValueError for strict mode errors)
        validator = CommerceTXTValidator()
        try:
            final_result = validator.validate(final_result)
        except ValueError as ve:
            # Strict mode validation error - add to result.errors
            final_result.errors.append(str(ve))
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # Action Routing
    if args.compare or args.compare_file:
        _handle_compare(args, final_result, resolver)
        return

    if args.health:
        _handle_health(final_result)
        return

    if args.normalize:
        _handle_normalize(final_result, args.json)
        return

    if args.schema:
        _handle_schema(final_result)
        return

    if args.prompt:
        _handle_prompt(final_result)
        return

    _handle_validation_output(final_result, args, file_path)


def _create_parser() -> argparse.ArgumentParser:
    """
    Creates and configures an argument parser for the CommerceTXT Reference Parser.

    The parser is used for parsing command-line arguments associated with managing
    and comparing commerce.txt files, output formatting, logging configurations,
    and executing specific actions such as validation, schema generation, and
    health assessments.

    Returns:
        argparse.ArgumentParser: An instance of ArgumentParser pre-configured
        with available options and functionality.
    """
    parser = argparse.ArgumentParser(
        prog="commercetxt",
        description=f"CommerceTXT Reference Parser v{__version__}",
        epilog="For more information: https://github.com/commercetxt/commercetxt",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"CommerceTXT Reference Parser v{__version__}\n"
        f"Protocol Specification: v1.0.1\n"
        f"Implementation: v{__version__}\n"
        f"Python Package: https://pypi.org/project/commercetxt/",
    )

    # Positional arguments
    parser.add_argument("file", help="Path to the commerce.txt or product file")
    parser.add_argument(
        "compare_file",
        nargs="?",
        help="Optional second file for comparison (use with --compare)",
    )

    # Output format
    parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors (exit code 1)"
    )

    # Logging
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging verbosity (default: WARNING)",
    )

    # Actions
    parser.add_argument(
        "--metrics", action="store_true", help="Show performance metrics after parsing"
    )
    parser.add_argument(
        "--prompt", action="store_true", help="Generate low-token AI prompt for LLMs"
    )
    parser.add_argument(
        "--health", action="store_true", help="Run AI Health Score assessment"
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize units in @SPECS (e.g., 1500g -> 1.5kg)",
    )
    parser.add_argument(
        "--schema", action="store_true", help="Generate Schema.org JSON-LD markup"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare two products (requires compare_file)",
    )
    parser.add_argument(
        "--validate", action="store_true", help="Only validate (skip other actions)"
    )

    return parser


def _setup_logging(level_name: str) -> None:
    logging.basicConfig(level=getattr(logging, level_name), format="%(message)s")


def _validate_file_path(path_str: str) -> Path:
    """
    Validates that the provided file path exists.
    """
    path = Path(path_str).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path


def _load_and_merge(path: Path, resolver: CommerceTXTResolver) -> Any:
    """
    Loads and merges commerce.txt data with root definitions if applicable.

    This function processes a given file using a resolver that merges the
    file's contents with a root definition file, provided it exists in the
    parent directory under the name 'commerce.txt'. The encoding is
    automatically detected during file parsing.

    Args:
        path (Path): Path to the commerce.txt file to be loaded and processed.
        resolver (CommerceTXTResolver): Resolver instance responsible for
            merging the target file's data with root definitions.
                                         target file's data with root definitions.

    Returns:
        Any: The merged file data, or the original file data if no root
            merge is performed.

    """
    # Use parse_file which auto-detects encoding
    target = parse_file(path)

    # Check for root commerce.txt for inheritance
    potential_root = path.parent / "commerce.txt"

    if path.name != "commerce.txt" and potential_root.exists():
        root = parse_file(potential_root)
        return resolver.merge(root, target)

    return target


def _handle_compare(args: Any, result_a: Any, resolver: CommerceTXTResolver) -> None:
    """
    Handles the comparison operation between two sets of directives.

    This function validates the existence and compatibility of the second
    input file for comparison, loads its content, and performs a comparison
    between the directives from two sources. The result of the comparison is
    output in either JSON format or as formatted text, depending on the
    provided arguments.

    Parameters:
    args: Any
        The arguments provided by the user, including options for the compare operation.
    result_a: Any
        The data or directives loaded from the initial file to be compared.
    resolver: CommerceTXTResolver
        The resolver instance used for parsing and merging the directives.

    Raises:
    FileNotFoundError
        If the provided compare file does not exist or cannot be accessed.
    """
    if not args.compare_file:
        print("Error: --compare requires a second file path", file=sys.stderr)
        sys.exit(1)

    try:
        path_b = _validate_file_path(args.compare_file)

        # FIX: Use _load_and_merge which supports UTF-16/32
        result_b = _load_and_merge(path_b, resolver)

    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    comparator = ProductComparator()
    comp = comparator.compare(result_a.directives, result_b.directives)

    if args.json:
        print(json.dumps(comp, indent=2))
    else:
        _print_comparison_text(comp, Path(args.file).name, path_b.name)
    sys.exit(0)


def _handle_health(result: Any) -> None:
    """
    Handles the health check result and generates a report.

    This function evaluates the health directives from the input result using an
    instance of AIHealthChecker and generates a health report. The generated report
    is printed to the console, and the program exits with a status code of 0.

    Parameters:
        result (Any): The result containing health directives to be assessed.

    Returns:
        None
    """

    checker = AIHealthChecker()
    report = checker.assess(result.directives)
    _print_health_text(report)
    sys.exit(0)


def _handle_normalize(result: Any, output_json: bool) -> None:
    """
    Handles the normalization of specifications present in the given result.

    This function utilizes a SemanticNormalizer to process and normalize the
    specifications retrieved from the directives of the result object. After
    normalizing, it outputs the normalized specifications based on the `output_json`
    flag provided.

    Arguments:
        result (Any): The result object containing directives that include the
            specifications. The normalization process updates the "SPECS" key
            within these directives.
        output_json (bool): A flag that determines the format of the output. If
            True, the normalized specifications are printed as a JSON object.
            Otherwise, they are printed as formatted text.
    """
    normalizer = SemanticNormalizer()
    specs = result.directives.get("SPECS", {})
    normalized = normalizer.normalize_specs(specs)
    result.directives["SPECS"] = normalized

    if output_json:
        print(json.dumps(normalized, indent=2))
    else:
        print("Normalized Specifications:")
        for k, v in normalized.items():
            print(f"  {k}: {v}")
    sys.exit(0)


def _handle_schema(result: Any) -> None:
    """
    Generate Schema.org JSON-LD markup.
    """
    bridge = SchemaBridge()
    flat = {}

    # Only flatten relevant sections for Schema.org
    relevant_sections = {"PRODUCT", "OFFER", "SPECS", "INVENTORY", "REVIEWS"}

    for k, v in result.directives.items():
        if k in relevant_sections and isinstance(v, dict):
            flat.update(v)
        elif k not in relevant_sections and not isinstance(v, dict):
            # Keep non-conflicting top-level keys
            flat[k] = v

    print(bridge.to_json_ld(flat))
    sys.exit(0)


def _handle_prompt(result: Any) -> None:
    """
    Generate AI prompt from parsed result.

    Note: result should already be validated in main() before calling this.
    """

    bridge = CommerceAIBridge(result)
    print(bridge.generate_low_token_prompt())
    sys.exit(0)


def _handle_validation_output(result: Any, args: Any, path: Path) -> None:
    """
    Output validation results.

    Note: result should already be validated in main() before calling this.
    """
    # Apply strict mode if requested (treat warnings as errors)
    if args.strict and result.warnings:
        for w in result.warnings:
            if f"Strict Mode Error: {w}" not in result.errors:
                result.errors.append(f"Strict Mode Error: {w}")

    if args.json:
        out = {
            "valid": len(result.errors) == 0,
            "errors": result.errors,
            "warnings": result.warnings,
            "directives": result.directives,
            "attributes": getattr(result, "attributes", {}),
        }
        print(json.dumps(out, indent=2))
    elif args.validate:
        _print_validate_text(result, path)
    else:
        _print_human_text(result, path)

    sys.exit(1 if result.errors else 0)


# --- Printing Helpers ---


def _print_comparison_text(comp: dict, name_a: str, name_b: str) -> None:
    print(f"--- Product Comparison: {name_a} vs {name_b} ---")
    adv = comp.get("price_advantage")
    print(f"Price Advantage: {adv.upper() if adv else 'None'}")

    if comp.get("savings"):
        print(f"Savings: {comp['savings']}")

    print("\nKey Differences:")
    for diff in comp.get("spec_differences", []):
        is_neutral = diff["advantage"] == "neutral"
        adv_text = "" if is_neutral else f"-> Advantage: {diff['advantage']}"
        print(f"  [{diff['attribute']}]")
        print(f"    {name_a}: {diff['product_a']}")
        print(f"    {name_b}: {diff['product_b']} {adv_text}")

    print(f"\nRecommendation: {comp.get('recommendation')}")


def _print_health_text(report: dict) -> None:
    score = report.get("score", 0)
    print(f"AI Health Score: {score}/100")

    if score >= CLI_SCORE_EXCELLENT:
        status = "EXCELLENT"
    elif score >= CLI_SCORE_GOOD:
        status = "GOOD"
    elif score >= CLI_SCORE_FAIR:
        status = "FAIR"
    else:
        status = "POOR"
    print(f"Status: {status}")

    if report.get("suggestions"):
        print("Suggestions:")
        for s in report["suggestions"]:
            print(f"  - {s}")
    else:
        print("No suggestions available.")


def _print_validate_text(result: Any, path: Path) -> None:
    heading = f"--- Validation Report: {path.name} ---"
    if HAS_COLOR:
        print(f"{Fore.CYAN}{heading}{Style.RESET_ALL}")
    else:
        print(heading)

    def _print_section(
        title: str, items: list[str], color: str | None = None, prefix: str = "-"
    ) -> None:
        if not items:
            return
        header = title if not color else f"{color}{title}{Style.RESET_ALL}"
        print(header)
        for text in items:
            if HAS_COLOR and color:
                print(f"  {color}{prefix}{Style.RESET_ALL} {text}")
            else:
                print(f"  {prefix} {text}")

    _print_section("ERRORS:", result.errors, Fore.RED, "✗")
    _print_section("WARNINGS:", result.warnings, Fore.YELLOW, "⚠")

    status_text = "Status: PASSED" if not result.errors else "Status: FAILED"
    status_color = Fore.GREEN if not result.errors else Fore.RED
    conclusion = (
        "File conforms to CommerceTXT specification"
        if not result.errors
        else f"Found {len(result.errors)} error(s)"
    )
    if HAS_COLOR:
        print(f"{status_color}{status_text}{Style.RESET_ALL}")
        print(f"{status_color}✓{Style.RESET_ALL} {conclusion}")
    else:
        print(status_text)
        print(conclusion)


def _print_human_text(result: Any, path: Path) -> None:
    def _print_section(
        title: str, items: list[str], color: str | None = None, prefix: str = "-"
    ) -> None:
        if not items:
            return
        header = title if not color else f"{color}{title}{Style.RESET_ALL}"
        print(header)
        for text in items:
            if HAS_COLOR and color:
                print(f"  {color}{prefix}{Style.RESET_ALL} {text}")
            else:
                print(f"  {prefix} {text}")

    _print_section("ERRORS:", result.errors, Fore.RED, "ERROR:")
    _print_section("WARNINGS:", result.warnings, Fore.YELLOW, "WARN:")

    if result.errors:
        state_text = "Status: INVALID"
        state_color = Fore.RED
    else:
        state_text = "Status: VALID"
        state_color = Fore.GREEN
    if HAS_COLOR:
        print(f"{state_color}{state_text}{Style.RESET_ALL}")
        if not result.errors and not result.warnings:
            msg = f"File {path.name} validates successfully"
            print(f"{state_color}✓{Style.RESET_ALL} {msg}")
    else:
        print(state_text)
        if not result.errors and not result.warnings:
            print(f"File {path.name} validates successfully")


if __name__ == "__main__":
    main()
