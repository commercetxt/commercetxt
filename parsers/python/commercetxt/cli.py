"""
CommerceTXT Command Line Interface.
Validates files. Generates AI prompts.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from .validator import CommerceTXTValidator
from .bridge import CommerceAIBridge
from .resolver import CommerceTXTResolver, resolve_path


def main():
    """Execute the CLI logic."""
    parser = argparse.ArgumentParser(
        description="CommerceTXT Reference Validator v1.0.1"
    )
    parser.add_argument("file", help="Path to the commerce.txt or product file")
    parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="WARNING"
    )
    parser.add_argument("--metrics", action="store_true", help="Show performance data")
    parser.add_argument("--prompt", action="store_true", help="Generate AI prompt")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Only validate the file without outputting content",
    )

    args = parser.parse_args()

    # Set up logging. Use the provided level.
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(message)s")
    logger = logging.getLogger("commercetxt.cli")

    # Locate the file. Stop if missing.
    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    resolver = CommerceTXTResolver()
    validator = CommerceTXTValidator(strict=args.strict, logger=logger)

    def simple_loader(p):
        """Read file content as UTF-8."""
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    # Parse and merge. Look for root context in parent directory.
    root_result = None
    potential_root = file_path.parent / "commerce.txt"
    if file_path.name != "commerce.txt" and potential_root.exists():
        root_result = resolve_path(str(potential_root), simple_loader)

    target_result = resolve_path(str(file_path), simple_loader)

    # Apply fractal inheritance. Merge results if root exists.
    final_result = (
        resolver.merge(root_result, target_result) if root_result else target_result
    )

    # Run validation. Catch data errors.
    try:
        validator.validate(final_result)
    except ValueError as e:
        final_result.errors.append(str(e))

    # Enforce strict mode. Warnings become errors.
    if args.strict and final_result.warnings:
        for w in final_result.warnings:
            msg = f"Strict Mode Error: {w}"
            if msg not in final_result.errors:
                final_result.errors.append(msg)

    bridge = CommerceAIBridge(final_result)

    # Handle output. Decide between prompt, JSON, validate or text report.
    if args.validate:
        print_validation_report(final_result, file_path)
    elif args.prompt:
        print(bridge.generate_low_token_prompt())
    elif args.json:
        out = {
            "valid": len(final_result.errors) == 0,
            "errors": final_result.errors,
            "warnings": final_result.warnings,
            "directives": final_result.directives,
        }
        print(json.dumps(out, indent=2))
    else:
        print_human_readable(final_result, file_path)

    # Exit with code 1 if errors found. Else 0.
    sys.exit(1 if final_result.errors else 0)


def print_validation_report(result, path):
    """Specific output for the --validate flag."""
    print(f"--- Validation Report: {path.name} ---")
    print(f"Status: {'PASSED' if not result.errors else 'FAILED'}")
    print(f"Errors: {len(result.errors)}")
    for e in result.errors:
        print(f"  [!] {e}")
    print(f"Warnings: {len(result.warnings)}")
    for w in result.warnings:
        print(f"  [*] {w}")

    if not result.errors:
        print("\nConclusion: File conforms to CommerceTXT protocol.")


def print_human_readable(result, path):
    """Print a simple status report."""
    status = "VALID" if not result.errors else "INVALID"
    print(f"Status: {status}")
    if result.errors:
        for e in result.errors:
            print(f" ERROR: {e}")
    if result.warnings:
        for w in result.warnings:
            print(f" WARN: {w}")


if __name__ == "__main__":
    main()
