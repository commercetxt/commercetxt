# CommerceTXT Parsers

This repository contains the official reference implementations for the CommerceTXT protocol. These tools are designed to be secure, fast, and compliant with the latest specification.

## Available Implementations

### 🐍 [Python (Reference Implementation)](./python)
The official reference parser and validator, fully production-ready and type-safe.

**Status:** v1.0.2 (Stable)
**Key Features:**
* **Fractal Inheritance:** Native support for resolving nested directives across multiple files.
* **Tiered Validation:** Strict compliance checks for Tier 1, 2, and 3.
* **Enterprise Security:** Built-in protection against SSRF, DoS, and private network exposure.
* **AI & LLM Bridge:** Enhanced prompt generation supporting `BRAND_VOICE`, `SEMANTIC_LOGIC`, and `PROMOS`.
* **Extreme Reliability:** 95%+ code coverage with Fuzz and Property-based testing.
* **CLI Tool:** Validate and process `commerce.txt` files directly from the terminal.
---

## Roadmap

* **JavaScript / TypeScript:** (In Progress) Browser-compatible parser for frontend integration.
* **Go:** (Planned) High-performance parser for microservices.
* **Rust:** (Planned) Memory-safe implementation for system-level integration.

---

## Installation (Python)
To install the reference parser, navigate to the python directory or use:
```bash
pip install commercetxt
```
Validate any file instantly:
```bash
commercetxt path/to/commerce.txt --validate
```

## Contribute

We welcome contributions! If you would like to build a parser in your favorite language (Go, JavaScript, TypeScript, Rust, etc.), please open an Issue or a Pull Request.

---

**© 2025 [CommerceTXT](https://commercetxt.org) Project | MIT License** 