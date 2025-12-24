# CommerceTXT Python Reference Parser (v1.0.2)

A robust, secure, and production-ready Python parser for the CommerceTXT protocol. This library handles parsing, validation, fractal inheritance, and advanced security checks for commerce.txt files.

## Key Features
- **Fractal Inheritance**: Support for resolving and merging nested directives across multiple files.
- **Comprehensive Validation**: Sequential Tier-based validation with a new `--validate` report flag.
- **AI-Ready Bridge**: Enhanced support for directives like `BRAND_VOICE`, `SEMANTIC_LOGIC`, and `PROMOS`.
- **Robust Test Suite**: Includes Property-based testing (Hypothesis), Fuzz testing, and 95%+ code coverage.
- High-Performance Caching: Built-in LRU caching to skip redundant parsing for unchanged files.
- Async Support: Concurrent parsing for bulk file processing using AsyncCommerceTXTParser.
- AI Readiness Bridge: Native support for generating clean, low-token prompts for Large Language Models (LLMs).
- Enterprise-Grade Security: Blocks localhost, private IP ranges, and exotic IP notations (Octal, Hex, Integer).

---

## Installation & Setup

Ensure you have Python 3.8+ installed.

Install the package directly from PyPI:

```bash
pip install commercetxt
```

## CLI Usage

Validate files or generate AI-ready prompts instantly.

**Comprehensive Validation Report:**
```bash
python -m commercetxt.cli path/to/commerce.txt --validate
```

Basic Validation:
```bash
python -m commercetxt.cli path/to/commerce.txt
```

Generate AI Prompt:
```bash
python -m commercetxt.cli product.txt --prompt
```

Advanced Usage:

```bash
python -m commercetxt.cli commerce.txt --json --metrics --log-level DEBUG
```
---

## Library Usage

1. Basic Parsing & Validation:
```python
from commercetxt import CommerceTXTParser, CommerceTXTValidator
parser = CommerceTXTParser()
result = parser.parse(content)
validator = CommerceTXTValidator(strict=False)
validator.validate(result)
```

2. High-Speed Caching:
```python
from commercetxt.cache import parse_cached
result = parse_cached(content)
```

3. Bulk Async Parsing:
```python
import asyncio
from commercetxt.async_parser import AsyncCommerceTXTParser
async def main():
    async_parser = AsyncCommerceTXTParser()
    results = await async_parser.parse_many([file1, file2])
asyncio.run(main())
```
---

## Testing & Quality

CommerceTXT 1.0.2 maintains a **95% code coverage** and utilizes a multi-layered testing strategy:
* **Data-Driven**: 150+ test vectors covering valid and malformed scenarios.
* **Property-Based**: Using `Hypothesis` to ensure logical consistency.
* **Fuzzing**: Stress-testing the parser against arbitrary random input.
* **Security Audit**: Automated checks for SSRF prevention and DoS mitigation.

---
## Security Limits

- MAX_FILE_SIZE: 10 MB
- MAX_SECTIONS: 1000
- MAX_LINE_LENGTH: 100 KB
- MAX_NESTING: 100
- Blocked IPs: Any Reserved (Prevents SSRF)

---

## Project Structure

- parser.py: Core parsing logic with optimized Regex compilation.
- validator.py: Business logic divided into compliance Tiers.
- security.py: Network security utilities (IP and URL validation).
- bridge.py: Token-efficient prompt generator for LLM integration.
- async_parser.py: Async engine for concurrent processing.
- cache.py: LRU caching implementation for performance.
- resolver.py: Locale resolution and fractal inheritance logic.
- metrics.py: Singleton for real-time performance tracking.

---

## Running Tests

Requires pytest and pytest-asyncio.

````bash
pytest parsers/python/tests/
python -m pytest --cov=commercetxt --cov-report=html
````