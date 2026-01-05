"""
Logging for CommerceTXT.
Track the parser. See the errors.
"""

from __future__ import annotations

import logging


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """
    Get a configured logger.
    It tells you what happens and when.
    """
    logger = logging.getLogger(name)

    # Set up handler if missing. Use standard stream.
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Apply level. Defaults to WARNING.
    if level:
        logger.setLevel(getattr(logging, level.upper()))
    else:
        logger.setLevel(logging.WARNING)

    return logger
