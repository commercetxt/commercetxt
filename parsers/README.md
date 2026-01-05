# CommerceTXT Parsers

Official reference implementations for the CommerceTXT protocol. Secure, fast, and compliant with Protocol v1.0.1.

- [Protocol specification v1.0.1](../spec/README.md)
- [Examples](../examples/)
- [Tests](./python/tests/)

---

## Available Implementations

### 🐍 [Python (Reference Implementation)](./python)
Official reference parser - production-ready and type-safe.

**Status:** v1.0.3 (Stable - January 2026)  
**Protocol:** v1.0.1  
**Coverage:** 82%

**Features**
- Full Protocol Support (Tier 1/2/3)
- Fractal Inheritance (multi-file resolution)
- UTF-16/32 Support (Excel exports)
- Security Hardened (SSRF/DoS protection)
- AI Bridge (~120 tokens vs 8,500+)
- Async Support (bulk processing)
- LRU Caching
- CLI Tools

**RAG & AI Tools**
- AI Health Checker (0-100 scoring)
- Schema.org Bridge (JSON-LD)
- Semantic Normalizer
- RAG Pipeline (vector databases)
- Async RAG Pipeline

**Vector DB Support:**  
Pinecone, Qdrant, Redis, FAISS, In-Memory

**Resources**
- [README](./python/README.md)
- [Source Code](./python/commercetxt)
- [PyPI](https://pypi.org/project/commercetxt/)

---

## Quick Start

### Installation
```bash
pip install commercetxt
```

### Basic Usage
```python
from commercetxt import parse_file

result = parse_file('commerce.txt')
product = result.directives.get('PRODUCT', {})
print(f"Product: {product.get('Name')}")
```

### CLI
```bash
commercetxt commerce.txt --validate
commercetxt product.txt --prompt
commercetxt product.txt --health
```

---

## Roadmap

* **JavaScript/TypeScript:** (Planned Q1 2026) Browser-compatible parser
* **Go:** (Planned Q2 2026) High-performance microservices
* **Rust:** (Planned Q3 2026) Memory-safe system integration
* **PHP:** (Community Request) WordPress/WooCommerce

---

## Contribute

Build a parser in your language! Open an Issue or Pull Request.

**Guidelines:**
- Follow [Specification v1.0.1](../spec/README.md)
- Include comprehensive tests
- Add security protections (SSRF, DoS)
- Provide examples and documentation

---

**© 2026 [CommerceTXT](https://commercetxt.org) Project | MIT License**

