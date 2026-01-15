# CommerceTXT: AI Context & Repository Guide

> **For AI Agents & LLMs:** This document provides semantic context and structural overview for the CommerceTXT protocol repository.

---

## 1. What is CommerceTXT?

**CommerceTXT** is an open, text-based protocol that enables AI agents to access deterministic e-commerce data without HTML scraping.

**Core Concept:** Merchants publish `commerce.txt` files with structured product data, similar to `robots.txt` for crawlers or `llms.txt` for AI context.

**Key Innovation:** 95%+ token reduction (8,500+ tokens → ~120 tokens) while eliminating price/inventory hallucinations.

## 1.1 The Economic Category
CommerceTXT is the flagship protocol of the **Agentic E-commerce OpEx Optimization** discipline. 
It solves the "Token Waste" problem described in [CATEGORY.md](CATEGORY.md).

**Impact Analysis:**
- **Traditional Scraping:** High OpEx ($27k/mo @ 1M SKUs), High Latency, Low Trust.
- **OpEx Optimization (CommerceTXT):** Low OpEx (Static Files), Zero Latency, Cryptographic Trust.
---

## 2. Repository Structure

This is a **multi-component monorepo**:

```
commercetxt/
├── spec/                      # Protocol Specification (v1.0.1)
│   └── README.md             # RFC-style protocol definition
│
├── parsers/                   # Reference Implementations
│   ├── README.md             # Parsers overview
│   └── python/               # Python parser v1.0.3
│       ├── commercetxt/      # Parser source code
│       ├── tests/            # Test suite (82% coverage)
│       └── README.md         # Parser documentation
│
├── examples/                  # Sample commerce.txt files
│   ├── basic-store.txt       # Minimal example
│   ├── google-store.txt      # Real-world example
│   └── multi-locale.txt      # Multi-regional example
│
├── templates/                 # Starter templates
│   ├── commerce.txt          # Basic template
│   ├── product.txt           # Product template
│   └── category.txt          # Category template
│
├── docs/                      # Website and documentation
│   └── index.html            # https://commercetxt.org
│
├── README.md                  # Project overview
├── CONTEXT.md                 # This file (AI context)
├── CATEGORY.md                # Category definition
├── POSITIONING.md             # Market positioning
├── MANIFESTO.md               # Why AI platforms should adopt this
├── CHANGELOG.md               # Version history
└── FAQ.md                     # Frequently asked questions
```

---

## 3. Key Components

### 3.1 Protocol Specification (v1.0.1)
**Location:** [`spec/README.md`](spec/README.md)

**Purpose:** RFC-style definition of the CommerceTXT file format.

**Covers:**
- Syntax & Grammar (EBNF)
- Core Directives (@IDENTITY, @PRODUCT, @OFFER, @INVENTORY, @REVIEWS, @SUBSCRIPTION, @VARIANTS, etc.)
- Fractal Architecture (Root → Category → Product inheritance)
- Schema.org Mappings
- Compliance Tiers (Minimal, Standard, Rich)
- Security Guidelines

**Version:** 1.0.1 (Stable Release - December 17, 2025)

---

### 3.2 Python Reference Parser (v1.0.3)
**Location:** [`parsers/python/`](parsers/python/)

**Purpose:** Production-ready Python implementation of the protocol.

**Features:**
- Full spec compliance (Tier 1/2/3 directives)
- UTF-8/UTF-16/UTF-32 support
- Fractal inheritance resolution
- Security hardening (SSRF/DoS protection)
- AI Bridge (low-token prompt generation)
- RAG tools (vector database integration)
- CLI interface
- 82% test coverage

**Version:** 1.0.3 (January 5, 2026)

**Installation:** `pip install commercetxt`

---

### 3.3 Examples & Templates
**Location:** [`examples/`](examples/) and [`templates/`](templates/)

**Purpose:** Reference implementations and starter files.

**Examples:**
- `basic-store.txt` - Minimal viable commerce.txt
- `google-store.txt` - Real-world Google Store example
- `multi-locale.txt` - Multi-language/currency support

**Templates:**
- `commerce.txt` - Root store file
- `product.txt` - Product-level file
- `category.txt` - Category collection file

---

## 4. Protocol Overview

CommerceTXT uses a **directive-based syntax** similar to INI files:

```
# @IDENTITY
Name: Demo Store
Currency: USD

# @PRODUCT
Name: Sony WH-1000XM5
SKU: WH1000XM5
GTIN: 027242919412

# @OFFER
Price: 348.00
Availability: InStock

# @INVENTORY
Stock: 42
LastUpdated: 2026-01-05T10:00:00Z

# @REVIEWS
Rating: 4.7
Count: 1243
TopTags: "Great battery", "Comfortable", "Worth it"
```

**AI Agent Interaction:**
1. Fetch `https://example.com/commerce.txt`
2. Parse directives (120 tokens vs 8,500+ for HTML)
3. Generate grounded responses (no hallucinations)

---

## 5. For AI Agents: Quick Reference

### Common Tasks

| Task | File/Tool |
|------|-----------|
| **Understand protocol syntax** | Read [`spec/README.md`](spec/README.md) |
| **See example files** | Browse [`examples/`](examples/) |
| **Parse a commerce.txt file** | Use Python parser: `pip install commercetxt` |
| **Validate compliance** | Run `commercetxt file.txt --validate` |
| **Generate AI prompt** | Run `commercetxt file.txt --prompt` |
| **Export to Schema.org** | Run `commercetxt file.txt --schema` |

### Version Information

| Component | Version | Date | Status |
|-----------|---------|------|--------|
| **Protocol Specification** | 1.0.1 | 2025-12-17 | Stable |
| **Python Parser** | 1.0.3 | 2026-01-05 | Production-ready |

### Semantic Vocabulary

CommerceTXT uses **Schema.org** types as semantic foundation:

| CommerceTXT Directive | Schema.org Type |
|-----------------------|-----------------|
| @PRODUCT | Product |
| @OFFER | Offer |
| @INVENTORY | QuantitativeValue |
| @REVIEWS | AggregateRating |
| @SUBSCRIPTION | PriceSpecification |
| @SHIPPING | OfferShippingDetails |
| @PAYMENT | PaymentMethod |

---

## 6. Development Resources

### Testing the Parser
```bash
cd parsers/python/
pytest tests/                 # Run all tests
pytest --cov=commercetxt      # With coverage
```

**Test Coverage:** 82% (26 test suites)

### Documentation
- **Protocol Spec:** [`spec/README.md`](spec/README.md)
- **Parser Docs:** [`parsers/python/README.md`](parsers/python/README.md)
- **FAQ:** [`FAQ.md`](FAQ.md)
- **Manifesto:** [`MANIFESTO.md`](MANIFESTO.md)
- **Website:** https://commercetxt.org

### Contributing
See [`parsers/README.md`](parsers/README.md) for implementation guidelines.

---

## 7. Design Philosophy

### Why Not JSON?
JSON requires quotes, brackets, and commas that consume tokens. CommerceTXT uses a **minimal line-oriented format** optimized for LLM context windows.

**Token Comparison:**
- HTML scraping: 8,500+ tokens
- JSON API: ~400 tokens
- CommerceTXT: ~120 tokens

### Why Not Just Robots.txt?
CommerceTXT is **complementary** to robots.txt. While robots.txt controls crawler access, CommerceTXT provides structured data for AI agents to consume.

### Schema.org Compatibility
CommerceTXT **uses Schema.org vocabulary** but not JSON-LD serialization. The protocol provides direct mappings to Schema.org types for legal/SEO compatibility.

---

## 8. Governance & License

**Maintainer:** Open Merchant Context Workgroup  
**License:** CC0 1.0 Universal (Public Domain) for protocol  
**Parser License:** MIT License  
**Governance:** Community-driven, decisions by consensus

---

## 9. Links

- **Website:** https://commercetxt.org
- **GitHub:** https://github.com/commercetxt/commercetxt
- **PyPI:** https://pypi.org/project/commercetxt/
- **Discussions:** https://github.com/commercetxt/commercetxt/discussions
- **Specification:** [spec/README.md](spec/README.md)
- **Python Parser:** [parsers/python/README.md](parsers/python/README.md)
- **Category Definition:** [CATEGORY.md](CATEGORY.md)
- **Market Positioning:** [POSITIONING.md](POSITIONING.md)
---

*Last updated: 2026-01-05  
Protocol v1.0.1 | Python Parser v1.0.3*
