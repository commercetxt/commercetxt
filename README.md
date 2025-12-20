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

**Result:** ~95% token reduction and elimination of price and inventory hallucinations.

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
   Non-standard hint. Primary discovery is via direct fetch.

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
CommerceTXT uses Schema.org as a semantic vocabulary, not as a web serialization format. Maps directly to existing structured data standards. Works *with* your current setup, not against it. 

### Multi-Regional Support
Built-in locale resolution for different currencies, languages, and policies.

### Trust & Verification
Optional cross-verification system ensures merchant data accuracy.

### Open Standard
CC0 license—no permission needed to implement. Vendor-neutral infrastructure.

---

## Documentation

- **[Full Specification](./spec/README.md)** - Technical RFC (v1.0.1)
- **[Manifesto](./MANIFESTO.md)** - Why AI platforms should support this
- **[Contributors](./CONTRIBUTORS.md)** - Project contributors
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

# Roadmap (Community-Driven)

---
## **v1.1 (Q1 2026 - Focus: Trust & Discovery)** 
**Upgraded in response to feedback from [Hacker News](https://news.ycombinator.com/item?id=46289481) and [Schema.org](https://github.com/schemaorg/schemaorg/discussions/4651) communities.**

### Discovery Improvements (The "Frictionless" Update)
* **HTML Link Discovery:** Support for `<link rel="commercetxt" href="...">` in `<head>` 
  - Enables merchants on restricted platforms (Shopify, Wix) to point to externally hosted files
  - Fallback for environments where root file access is blocked
  
* **Well-Known First:** Mandate `/.well-known/commerce.txt` as primary path (RFC 8615 compliant)
  - Root `/commerce.txt` becomes legacy fallback
  - Aligns with IETF best practices (credit: HN community feedback)

* **Technical Rigor (Schema.org Integration):**
    * **Formal Grammar:** Strict rules for escaping special characters (`|`, `:`, `\n`) to ensure parser stability.
    * **Semantic Mapping:** Publishing formal Turtle definitions to ensure 1:1 mapping with Schema.org vocabulary.
    * **Graph Flattening:** Standardized way to represent multi-currency offers and complex product models in a flat-file format.

### Data Integrity & Freshness
* **@TIMESTAMP (Global):** Document-level timestamp for freshness validation
  - Prevents "stale inventory" hallucinations
  - Enables agent-side caching strategies
  - Format: ISO-8601 timestamp

* **@SUSTAINABILITY (Optional):** Verified environmental claims
  - Carbon footprint, recycled materials, repair programs
  - Requires third-party verification URL (anti-greenwashing)
  - Example: `CarbonNeutral: Yes | Verified: https://climatepartner.com/cert/12345`

### Reference Implementations
* **Openfront Integration:** First production implementation
  - Open source Shopify alternative by @theturtletalks
  - Provides real-world validation of spec
  - Case study: [link to be added]

### Ethical Sales Guidance
* **@PURCHASE_ADVICE:** Merchant-defined key selling points
  - Factual highlights to prevent AI from "hallucinating" features the product does not have.
  - Example: `Highlights: 5-year warranty, Free repairs, Carbon-neutral shipping`

* **@COMPARISON_CONTEXT:** How to position vs competitors
  - Transparent competitive advantages
  - Example: `vs. CompetitorX: Better battery (30h vs 20h), Lower price ($200 less)`

### Advanced Features (Experimental)
* **Multi-Variant @BRAND_VOICE:** A/B testing for brand personality
  - Requires analytics infrastructure (out of scope for v1.x)
  - Community feedback needed before standardization

---

## v2.0 (2027+) - "Transactional Layer" (Requires Community Consensus)
**Theme:** From read-only context to actionable commerce (if community decides this is valuable).

### Proposed (Not Finalized)
* **@ACTIONS:** Transactional directives (add to cart, apply coupon)
  - Requires extensive security review
  - User-in-the-loop mandatory for all transactions
  - Open question: Should CommerceTXT remain read-only forever?

* **@ANALYTICS:** Anonymous conversion tracking
  - Privacy-first approach (no PII)
  - Helps merchants measure AI shopping channel ROI

---

## Community Involvement
* **Working Group:** Open to all contributors
  - Decisions by consensus, not dictation
  
* **Reference Implementations:**
  - Openfront (in progress - Q1 2026)
  - Seeking: WooCommerce plugin, Magento extension
  
* **AI Platform Adoption:**
  - Target: OpenAI, Anthropic, Google to support in ChatGPT/Claude/Gemini
  - Community help needed: We are specifically looking for contacts within **Search Quality**, **LLM Training**, and **GPTs/Plugins Infrastructure** teams. Who has contacts at these companies?

---

## How to Contribute
1. **Propose features:** Open GitHub Issues with `[RFC]` prefix
2. **Review spec:** Technical feedback on mapping, syntax, edge cases
3. **Build implementations:** Plugins for e-commerce platforms
4. **Spread awareness:** Write blog posts, conference talks, podcasts

**Join the discussion:** https://github.com/commercetxt/commercetxt/discussions

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
CommerceTXT is newly launched (v1.0.1). We're in active discussions with Anthropic, OpenAI, and Google. See [Manifesto](./MANIFESTO.md) for pitch.

### How do I keep data fresh?
Set appropriate `Cache-Control` headers (5-60 minutes). For dynamic inventory, generate commerce.txt on-demand from your database.

### What about security?
- Files MUST NOT contain PII or secrets
- Use WAF to allow only verified AI bots
- Rate limiting recommended
- See [Security Section](./spec/README.md#9-error-handling-security--trust)

---

## Status

**Current Version:** 1.0.1 (Stable Release)  
**Release Date:** December 17, 2025  
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
- **X:** https://x.com/CommerceTXT

---

**Built for the Agentic Web. Open. Neutral. Essential.**