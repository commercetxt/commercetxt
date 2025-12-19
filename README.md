# CommerceTXT Protocol

> **Transaction-ready context for AI agents**  
> Like llms.txt, but for e-commerce

[![License: CC0](https://img.shields.io/badge/License-CC0_1.0-lightgrey.svg)](https://creativecommons.org/publicdomain/zero/1.0/)
[![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)](https://commercetxt.org)
[![Standard](https://img.shields.io/badge/standard-stable-green.svg)](./spec/README.md)

---

## What is CommerceTXT?

CommerceTXT is an open, read-only protocol that enables AI agents to access accurate commerce data without HTML scraping. It provides deterministic information about:

- Product prices and availability
- Store policies (shipping, returns, warranties)
- Inventory levels (real-time stock)
- Subscription pricing
- Product specifications and compatibility
- Customer reviews (aggregated)

**Result:** 95-99% token reduction, zero hallucinations, better user experience.

---

## The Problem

AI agents today must:
- Scrape 2-5 MB HTML pages to find a single price
- Execute JavaScript (or fail)
- Infer prices and availability probabilistically
- Re-crawl constantly for updates

**Consequences:**
- Hallucinated prices and inventory
- High inference costs (8,500+ tokens per product)
- Merchant frustration (server overload)
- User distrust (incorrect information)

---

## The Solution

```
# commerce.txt (380 tokens instead of 8,500)

# @IDENTITY
Name: Demo Store
Currency: USD

# @PRODUCT
Name: Sony WH-1000XM5
SKU: WH1000XM5

# @OFFER
Price: 348.00
Availability: InStock

# @INVENTORY
Stock: 42
LastUpdated: 2025-12-15T10:00:00Z

# @REVIEWS
Rating: 4.7
Count: 1243
TopTags: "Great battery", "Comfortable", "Worth it"
```

AI agents read this structured data directly—no scraping, no guessing, no hallucinations.

---

## Quick Start

### For Merchants

1. **Create `/commerce.txt` file**
   ```bash
   # Download template
   curl -O https://raw.githubusercontent.com/commercetxt/commercetxt/main/templates/commerce.txt
   ```

2. **Add to your website root**
   ```
   https://yourstore.com/commerce.txt
   ```

3. **Update robots.txt**
   ```
   Commerce-TXT: https://yourstore.com/commerce.txt
   ```

4. **Use generator** (optional)
   - Online: Coming soon
   - Shopify plugin: Coming soon

### For AI Platform Developers

```python
# Python example
import requests

# Discover commerce.txt
response = requests.get('https://example.com/commerce.txt')
commerce_data = parse_commercetxt(response.text)

# Access structured data
print(f"Price: ${commerce_data['@OFFER']['Price']}")
print(f"Stock: {commerce_data['@INVENTORY']['Stock']}")
```

See [Parser Documentation](./parsers/) (coming soon) for implementation details.

---

## Features

### Deterministic Data
No more "prices may vary" or "appears to be in stock"—data is either correct or absent.

### Token-Efficient
- HTML scraping: 8,500+ tokens
- CommerceTXT: 380 tokens
- **Reduction: 95%+**

### Schema.org Compatible
Maps directly to existing structured data standards. Works *with* your current setup, not against it.

### Multi-Regional Support
Built-in locale resolution for different currencies, languages, and policies.

### Trust & Verification
Optional cross-verification system ensures merchant data accuracy.

### Open Standard
CC0 license—no permission needed to implement. Vendor-neutral infrastructure.

---

## Documentation

- **[Full Specification](./spec/README.md)** - Technical RFC (v1.0.0)
- **[Manifesto](./MANIFESTO.md)** - Why AI platforms should support this
- **[Examples](./examples/)** - Real commerce.txt files
- **[Parsers](./parsers/)** - Reference implementations  (coming soon)
- **[Website](https://commercetxt.org)** - Interactive guides

---

## Why This Matters

### For AI Platforms

**Anthropic / OpenAI / Google:**
- 95% cost reduction on commerce queries
- Eliminates price/inventory hallucinations
- Better agent experience (no "let me check" loops)
- Legal/reputational risk mitigation

### For Merchants

- Control how AI represents your products
- Reduce server load from AI crawlers
- Deterministic channel for updates
- First-mover advantage in AI commerce

### For Users

- Accurate pricing and availability
- Faster AI responses
- Better shopping recommendations
- Trustworthy information

---

## Real-World Impact

### Before CommerceTXT
```
User: "What's the price of Sony XM5?"
AI: [Scrapes 2.5 MB page, 8,500 tokens]
    "They appear to be around $350, but prices may vary..."
```

### With CommerceTXT
```
User: "What's the price of Sony XM5?"
AI: [Reads 5 KB file, 380 tokens]
    "Sony XM5 headphones are $348.00 (42 in stock, ships 3-5 days)"
```

**Result:** 95% faster, 100% accurate, zero hallucinations.

---

## Roadmap

### v1.0.0 (Stable Release - Dec 2025)
- Core directives (@PRODUCT, @OFFER, @INVENTORY, @REVIEWS)
- Trust Score framework
- Multi-regional support
- Complete specification
- **Parser implementations (in development)**

### v1.0.1 (Released - Dec 2025) 
- @IMAGES directive (direct image URLs)
- @AGE_RESTRICTION directive (regulated products)
- @PRODUCT URL field clarification
- Enhanced documentation

### v1.1 (Q1 2026)
- @SUSTAINABILITY directive (verified environmental claims)
- Enhanced validation tools
- More parser implementations
- Merchant onboarding tooling

### v2.0+ (Future)
- @ACTIONS (transactional capabilities - requires industry consensus)
- Real-time API integration
- Advanced trust mechanisms

---

## Community

### Get Involved

- **GitHub Discussions:** Share ideas, ask questions
- **Discord:** Real-time chat (coming soon)
- **Email:** hello@commercetxt.org


---

## Who's Behind This?

**Initiated by:** Tsanko Zanov  
**Maintained by:** Open Merchant Context Workgroup  
**Governance:** Community-driven, decisions by consensus  
**License:** CC0 1.0 Universal (Public Domain)

No single company owns CommerceTXT. It's open infrastructure for the Agentic Web.

---

## FAQ

### Is this a replacement for HTML?
No. CommerceTXT is *complementary* to HTML. Your website continues to work normally—this is an additional interface for AI agents.

### Won't competitors scrape my prices?
Your prices are already public in HTML. CommerceTXT doesn't expose new data—it just reduces server load from bots that are already scraping you.

### Do I need to use all directives?
No. Tier 1 (Minimal) requires only 4 directives. Add more as needed. See [Compliance Tiers](./spec/README.md#6-compliance-tiers).

### Which AI platforms support this?
CommerceTXT is newly launched (v1.0.0). We're in active discussions with Anthropic, OpenAI, and Google. See [Manifesto](./MANIFESTO.md) for pitch.

### How do I keep data fresh?
Set appropriate `Cache-Control` headers (5-60 minutes). For dynamic inventory, generate commerce.txt on-demand from your database.

### What about security?
- Files MUST NOT contain PII or secrets
- Use WAF to allow only verified AI bots
- Rate limiting recommended
- See [Security Section](./spec/README.md#9-error-handling-security--trust)

---

## Status

**Current Version:** 1.0.0 (Stable Release)  
**Release Date:** December 16, 2025  
**Stability:** Production-ready  
**Breaking Changes:** None expected in v1.x

---

## License

This specification is dedicated to the **public domain** (CC0 1.0 Universal).

You may:
- Implement without permission
- Modify freely
- Use commercially
- Distribute anywhere

No attribution required (but appreciated).

---

## Links

- **Website:** https://commercetxt.org
- **Specification:** https://github.com/commercetxt/commercetxt/blob/main/spec/README.md
- **GitHub:** https://github.com/commercetxt/commercetxt/
- **Discussions:** https://github.com/commercetxt/commercetxt/discussions
- **Twitter:** Coming soon

---

**Built for the Agentic Web. Open. Neutral. Essential.**