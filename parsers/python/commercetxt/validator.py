# validator.py (NEW - FACADE PATTERN)
"""
Main validator facade. Delegates to focused sub-validators.
"""

from .logging_config import get_logger
from .metrics import get_metrics
from .model import ParseResult
from .validators import AttributeValidator, CoreValidator, PolicyValidator


class CommerceTXTValidator:
    """
    Main validator orchestrator.
    Delegates to specialized validators for better organization.
    """

    def __init__(self, strict: bool = False, logger=None):
        self.strict = strict
        self.logger = logger or get_logger(__name__)

        # Initialize sub-validators
        self.core = CoreValidator(strict=strict, logger=self.logger)
        self.attributes = AttributeValidator(strict=strict, logger=self.logger)
        self.policies = PolicyValidator(strict=strict, logger=self.logger)

    def validate(self, result: ParseResult) -> ParseResult:
        """
        Run all validations through sub-validators.
        """
        metrics = get_metrics()
        metrics.start_timer("validation")
        self.logger.debug("Starting validation")

        # Delegate to specialized validators
        self.core.validate(result)
        self.attributes.validate(result)
        self.policies.validate(result)

        if result.errors:
            self.logger.error(f"Validation failed with {len(result.errors)} errors")
        else:
            self.logger.info(f"Validation passed with {len(result.warnings)} warnings")

        metrics.stop_timer("validation")
        metrics.gauge("validation_errors", len(result.errors))
        metrics.gauge("validation_warnings", len(result.warnings))

        return result
