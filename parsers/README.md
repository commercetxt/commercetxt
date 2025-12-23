# CommerceTXT Parsers

This repository contains the official reference implementations for the CommerceTXT protocol. These tools are designed to be secure, fast, and compliant with the latest specification.

## Available Implementations

### 🐍 [Python (Reference Implementation)](./parsers/python)
The official reference parser and validator, fully production-ready and type-safe.

**Status:** v1.0.1 (Stable)
**Key Features:**
* **Fractal Inheritance:** Native support for resolving nested directives across multiple files.
* **Tiered Validation:** Strict compliance checks for Tier 1 (Core), Tier 2 (Commercial), and Tier 3 (Metadata).
* **Enterprise Security:** Built-in protection against SSRF and private network exposure.
* **AI Readiness:** Specialized bridge for generating token-efficient prompts for LLMs.
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

## Contribute

We welcome contributions! If you would like to build a parser in your favorite language (Go, JavaScript, TypeScript, Rust, etc.), please open an Issue or a Pull Request.

---

**© 2025 [CommerceTXT](https://commercetxt.org) Project | MIT License** 