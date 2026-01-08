# CommerceTXT Protocol Specification
[![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)](https://github.com/commercetxt/commercetxt/releases)
[![License](https://img.shields.io/badge/license-CC0%201.0-green.svg)](https://creativecommons.org/publicdomain/zero/1.0/)
[![Status](https://img.shields.io/badge/status-stable-success.svg)]()

**Version:** 1.0.1  
**Date:** 2026-01-08  
**Status:** Stable Release  
**Maintainer:** Open Merchant Context Workgroup  
**License:** CC0 1.0 Universal (Public Domain)

---

## 1. Abstract

**CommerceTXT** is a lightweight, text-based protocol designed to provide deterministic, machine-readable context for AI Agents (LLMs) interacting with e-commerce environments. It solves the inefficiency of HTML scraping by serving structured data, logic, and policies in a token-optimized format.

**Key Features:**
- **95-99% token reduction** compared to HTML scraping
- **Real-time inventory** tracking (@INVENTORY)
- **Subscription pricing** support (@SUBSCRIPTION)
- **Verified reviews** integration (@REVIEWS)
- **Trust Score system** for merchant accountability
- **Multi-regional** support with locale resolution
- **Schema.org compliant** for legal and SEO interoperability

**File Convention:** The root file is named `commerce.txt` and placed at the domain root (e.g., `https://example.com/commerce.txt`).

### 1.1 Terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

---

## 2. Syntax & Grammar (EBNF)

The protocol follows a line-oriented directive syntax. Parsers MUST support UTF-8 encoding.

```ebnf
file           = { line }
line           = ( directive | comment | empty_line ), newline
directive      = section_header | list_item | entry
section_header = "#", space, "@", section_name
section_name   = uppercase_letters, { "_" | uppercase_letters }
entry          = key_value, { space, "|", space, key_value }
key_value      = key, ":", space, value
list_item      = "-", space, entry
comment        = "#", space, string
key            = alphanumeric
value          = string | number | path | iso8601_date
```

### Parsing Rules:

- **Whitespace:** Leading/trailing whitespace MUST be ignored.
- **Case Sensitivity:** Directives (@OFFER) and Keys (Price) are case-insensitive. Values are case-sensitive.
- **Comments:** Any line starting with # (not followed by @) is a comment and MUST be ignored by the parser.

### Complex Structures:

**Multi-value entries (pipe-separated):**
```
- Monthly: 29.99 | BilledAs: "$29.99/month" | Savings: "Save 17%"
```
This is parsed as a single list item with multiple key-value pairs separated by `|`.

**Nested lists (indentation):**
```
# @VARIANTS
Type: Storage
Options:
  - 128GB: 999.00 | SKU: GA05843-128
  - 256GB: 1099.00 | SKU: GA05843-256
```
The `Options:` line starts a nested list. Indented lines with `-` are list items under `Options`.

**Note:** The EBNF provides the base grammar. Complex directives like @SUBSCRIPTION and @VARIANTS use this grammar to build hierarchical structures. Parsers SHOULD maintain context (current section, nesting level) during parsing.

---

## 3. Context Inheritance & Architecture

The protocol utilizes a **Fractal Architecture** with a "Specific Overrides General" inheritance model.

### Resolution Logic:

- **L1 Root** (commerce.txt): Defines global Identity, Locales, and Shipping policies.
- **L2 Node** (Category): Defines Filters and Collections. Overrides Root.
- **L3 Leaf** (Product): Defines Transactional Data. Overrides Node and Root.

**Rule:** If a key is defined in both Root and Leaf, the Leaf value MUST take precedence.

---

## 4. Core Directives

### 4.1 @IDENTITY (Tier 1: Minimal)

**Purpose:** Store identification and basic contact information.

**Location:** Root file only

**Fields:**
- Name: String (store name)
- URL: String (primary domain)
- Currency: ISO 4217 code (e.g., USD, EUR)

**Example:**
```
# @IDENTITY
Name: Demo Store
URL: https://demostore.com
Currency: USD
```

---

### 4.2 @CATALOG (Tier 1: Minimal)

**Purpose:** Maps category names to their respective context files.

**Location:** Root file

**Syntax:** List items with format: `- CategoryName: /path/to/file.txt`

**Example:**
```
# @CATALOG
- Electronics: /categories/electronics.txt
- Clothing: /categories/clothing.txt
```

---

### 4.3 @FILTERS (Tier 2: Standard)

**Purpose:** Defines available attributes for filtering products within a category context. Helps AI understand the scope of the collection.

**Location:** Category files

**Syntax:** Key-value pairs where values are list or range descriptions.

**Example:**
```
# @FILTERS
Brands: Sony, Bose, Sennheiser
Type: Over-Ear, On-Ear, Earbuds
PriceRange: $50 - $500
Features: ANC, Wireless, Bluetooth
```

---

### 4.4 @ITEMS (Tier 1: Minimal)

**Purpose:** Lists the products contained in a specific category or collection file.

**Location:** Category files

**Syntax:** List items with format: `- ProductName: /path/to/product.txt`

**Example:**
```
# @ITEMS
- Sony WH-1000XM5: /products/sony-xm5.txt
- Bose QC45: /products/bose-qc45.txt
```

---

### 4.5 @PRODUCT (Tier 1: Minimal)

**Purpose:** Product identification using industry-standard identifiers.

**Location:** Leaf (Product) files

**Mandatory Fields:**
- Name: String
- SKU: String (merchant identifier)

**Recommended Fields:**
- URL: String (canonical product page URL)

**Optional Fields:**
- GTIN: String (Global Trade Item Number - barcode)
- Brand: String
- Model: String

**Example:**
```
# @PRODUCT
Name: Sony WH-1000XM5
GTIN: 027242919412
SKU: WH1000XM5
URL: https://techstore.example.com/products/sony-wh-1000xm5
Brand: Sony
Model: WH-1000XM5
```

**Why URL is Recommended:**
While agents can attempt to construct product URLs from file paths 
or @IDENTITY.URL + path resolution, explicit URLs eliminate ambiguity 
and are essential for:
- Providing direct purchase links to users
- Multi-language sites with different URL structures
- SEO canonical URL references
- Future transactional features (@ACTIONS)

---

### 4.6 @OFFER (Tier 1: Minimal)

**Purpose:** Transactional data (price and availability).

**Location:** Leaf (Product) files

**Mandatory Fields:**
- Price: Decimal number (e.g., 348.00)
- Availability: Enum (InStock|OutOfStock|PreOrder|Discontinued)

**Optional Fields:**
- Currency: ISO 4217 (inherits from @IDENTITY if not specified)
- Condition: Enum (New|Refurbished|Used)
- PriceValidUntil: ISO-8601 date
- TaxIncluded: Boolean (whether price includes VAT/sales tax)
- TaxRate: Decimal (e.g., 0.19 for 19% VAT)
- PriceExcludingTax: Decimal (base price before tax)
- DiscontinuedDate: ISO-8601 date (when product was discontinued)
- DiscontinuedNote: String (explanation for discontinued status)

**Tax Handling (Multi-Regional):**

For regions with Value Added Tax (VAT) or Goods and Services Tax (GST), merchants MUST specify whether the displayed price includes tax:

```
# US Store (tax not included)
# @OFFER
Price: 399.00
Currency: USD
TaxIncluded: False
TaxNote: "Sales tax calculated at checkout based on shipping address"

# EU Store (tax included)
# @OFFER  
Price: 399.00
Currency: EUR
TaxIncluded: True
TaxRate: 0.19
PriceExcludingTax: 335.29
TaxNote: "Includes 19% German VAT"
```

**Why this matters:**
- US: $399 → actual cost varies by state ($399-$440)
- EU: €399 → final cost is exactly €399 (tax included)

AI agents SHOULD inform users when tax is not included to avoid checkout surprise.

**Discontinued Products:**

```
# @OFFER
Price: 55.00
Currency: USD
Availability: Discontinued
DiscontinuedDate: 2023-08-29
DiscontinuedNote: "No longer offered for new purchases as of August 29, 2023"
```

**Example:**
```
# @OFFER
Price: 348.00
Currency: USD
Availability: InStock
Condition: New
TaxIncluded: False
```

---

### 4.7 @INVENTORY (Tier 2: Standard)

**Purpose:** Real-time stock level visibility for AI agents.

**Location:** Leaf (Product) files

**Mandatory Fields:**
- Stock: Integer (current units available)
- StockStatus: Enum (InStock|LowStock|OutOfStock|Backorder)
- LastUpdated: ISO-8601 timestamp

**Optional Fields:**
- LowStockThreshold: Integer (triggers LowStock status)
- RestockDate: ISO-8601 date (when new stock arrives)
- BackorderAvailable: Boolean
- MaxQuantityPerOrder: Integer
- EstimatedShipDate: ISO-8601 date (for backorders)

**Example:**
```
# @INVENTORY
Stock: 42
LowStockThreshold: 10
StockStatus: InStock
MaxQuantityPerOrder: 5
LastUpdated: 2025-12-16T09:30:00Z
```

**Critical Implementation Notes:**

1. **Cache Control Requirements:**
   Merchants providing @INVENTORY MUST configure appropriate HTTP Cache-Control headers to ensure data freshness:
   ```
   Cache-Control: max-age=300, must-revalidate  # 5 minutes for high-velocity products
   Cache-Control: max-age=3600, must-revalidate # 1 hour for stable inventory
   ```
   
2. **Dynamic Generation:**
   While CommerceTXT files appear as static `.txt`, high-traffic merchants SHOULD generate them dynamically at request time from their inventory database. The "static file" is an interface, not a requirement for static storage.

3. **Freshness Validation:**
   AI Agents MUST check `LastUpdated` timestamps and apply these freshness rules:
   - **< 1 hour:** Trusted (use without caveat)
   - **1-24 hours:** Acceptable (add caveat: "Inventory as of [time]")
   - **24-72 hours:** Stale (warn: "Inventory data may be outdated")
   - **> 72 hours:** Invalid (ignore inventory data, treat as Unknown)
   - **> 7 days:** Trust Score penalty
   
   High-frequency merchants (updating hourly) MAY receive Trust Score bonuses.

**AI Agent Behavior:**
- Stock > Threshold: "In stock, ready to ship"
- Stock ≤ Threshold: "Only X left in stock"
- Stock = 0 + Backorder: "Currently unavailable, ships [RestockDate]"

**Schema.org Mapping:**
- Stock → offer.inventoryLevel.value
- StockStatus → offer.availability
- RestockDate → offer.availabilityStarts

---

### 4.8 @SUBSCRIPTION (Tier 2: Standard, Optional)

**Purpose:** Define recurring payment options for subscription-based products.

**Location:** Leaf (Product) files

**Mandatory Fields:**
- Plans: Array of pricing tiers with interval and price
- CancelAnytime: Boolean

**Optional Fields:**
- Trial: Text (e.g., "7 Days Free", "First month 50% off")
- AutoRenew: Boolean (default: True)
- MinCommitment: Text or None
- SkipOrPause: Boolean (for physical subscriptions)
- Frequency: Text (for recurring physical goods)
- PromotionalPricing: Object (for limited-time offers)

**Promotional Pricing:**

For subscriptions with introductory offers, use the PromotionalPricing field:

```
# @SUBSCRIPTION
Plans:
  - Monthly: 29.99 | BilledAs: "$29.99/month"
  - Annual: 299.00 | BilledAs: "$299/year" | EffectiveMonthly: "$24.92"
  
PromotionalPricing:
  - Offer: First 3 months $9.99, then $29.99
  - Duration: "3 months"
  - ThenPrice: 29.99
  - TotalFirstYear: "$209.91 (3×$9.99 + 9×$29.99)"

Trial: 7 Days Free
CancelAnytime: True
```

This prevents confusion about "true cost" over time.

**Example (SaaS):**
```
# @SUBSCRIPTION
Plans:
  - Monthly: 29.99 | BilledAs: "$29.99/month"
  - Annual: 299.00 | BilledAs: "$299/year" | Savings: "Save 17%"
Trial: 7 Days Free
CancelAnytime: True
AutoRenew: True
MinCommitment: None
```

**Example (Physical Product):**
```
# @SUBSCRIPTION
Plans:
  - Weekly: 19.99 | Frequency: "1 bag/week"
  - BiWeekly: 19.99 | Frequency: "1 bag every 2 weeks"
  - Monthly: 19.99 | Frequency: "1 bag/month"
Trial: First bag 50% off
CancelAnytime: True
SkipOrPause: Available
```

**Schema.org Mapping:**
- Plans → offer.priceSpecification
- Trial → offer.eligibleDuration
- CancelAnytime → offer.termOfService

---

### 4.9 @REVIEWS (Tier 2: Standard, Optional)

**Purpose:** Aggregated review data to reduce hallucinations and token waste from scraping review pages.

**Location:** Leaf (Product) files

**Mandatory Fields:**
- Rating: Decimal (e.g., 4.7)
- RatingScale: String (e.g., "5.0")
- Count: Integer (total number of reviews)

**Optional Fields:**
- Verified: Percentage or count (verified purchase reviews)
- TopTags: Comma-separated quoted strings (max 5 tags, each max 20 characters)
- Source: URL to verification source (Trustpilot, Google Reviews, Yotpo, etc.)
- LastUpdated: ISO-8601 timestamp

**TopTags Format:**
- Comma-separated quoted strings
- Maximum 5 tags
- Each tag maximum 20 characters
- SHOULD represent balanced sentiment: include both positive and commonly mentioned concerns
- MUST be derived from actual review content, not marketing copy
- SHOULD NOT cherry-pick only positive tags when significant negative themes exist

**TopTags Guidelines:**
```
Recommended approach:
- Top 3 most frequent themes (regardless of sentiment)
- If negative themes exceed 20% of reviews, include at least 1 negative tag

Examples:

Balanced (preferred):
TopTags: "Great battery", "Comfortable", "Clear sound", "Tight fit", "Pricey"

Mostly positive (acceptable if reviews genuinely positive):
TopTags: "Excellent ANC", "Long battery", "Premium build", "Comfortable", "Worth it"

Cherry-picked (violation):
TopTags: "Amazing", "Best ever", "Perfect", "Love it", "5 stars"
(when actual reviews contain significant negative themes)
```

**Example:**
```
# @REVIEWS
Rating: 4.7
RatingScale: 5.0
Count: 1243
Verified: 89% (1107 verified purchases)
TopTags: "Great battery", "Comfortable", "Worth the price", "Tight fit", "Expensive"
Source: https://www.trustpilot.com/review/example.com
LastUpdated: 2025-12-16T08:00:00Z
```

**Benefits:**
- Reduces token usage from ~15,000 (scraping review pages) to ~50 tokens
- Prevents hallucination of fake reviews
- TopTags provide context without citing specific reviews (privacy + copyright)
- Source URL enables independent verification

**Schema.org Mapping:**
- Rating → aggregateRating.ratingValue
- RatingScale → aggregateRating.bestRating
- Count → aggregateRating.reviewCount

#### 4.7.1 @REVIEWS Source Validation

Agents SHOULD validate Source URLs against known review platforms to ensure authenticity.

**Trusted Platforms (Auto-Verified):**

These platforms provide independent, verified review aggregation:
- `trustpilot.com/review/*`
- `google.com/shopping/customerreviews/*`
- `reviews.io/*`
- `yotpo.com/reviews/*`
- `feefo.com/*`
- `bazaarvoice.com/*`
- `powerreviews.com/*`

**Custom Platforms:**

If Source points to the merchant's own domain (e.g., `example.com/reviews`), Agents SHOULD:
1. Check for Schema.org Review markup on the page
2. Compare aggregated data (Rating, Count) with CommerceTXT values
3. Apply higher scrutiny - any discrepancy >2% triggers Trust Score penalty
4. Consider the data "Unverified" in user-facing responses

**Example Agent Response:**
```
Trusted Source: "This product has 4.7/5 stars based on 1,243 verified reviews on Trustpilot."

Custom Source: "The merchant reports 4.7/5 stars based on 1,243 reviews (unverified source)."
```

---

### 4.10 @VARIANTS (Tier 3: Rich, Optional)

**Purpose:** Handle product variations (size, color, storage, etc.) without creating separate files for each variant.

**Location:** Leaf (Product) files

**Structure:** Flexible key-value pairs to accommodate any variant type.

**Syntax:**
```
# @VARIANTS
Type: <VariantName>
Options:
  - <OptionValue>: <Price> | <ModifierKey>: <ModifierValue>
  - <OptionValue>: <Price> | <ModifierKey>: <ModifierValue>
```

**Example (Storage Variants):**
```
# @VARIANTS
Type: Storage
Options:
  - 128GB: 999.00 | SKU: GA05843-128
  - 256GB: 1099.00 | SKU: GA05843-256
  - 512GB: 1299.00 | SKU: GA05843-512
  - 1TB: 1499.00 | SKU: GA05843-1TB
```

**Example (Color Variants):**
```
# @VARIANTS
Type: Color
Options:
  - Obsidian: +0.00 | Hex: #000000
  - Porcelain: +0.00 | Hex: #F5F5DC
  - Bay: +50.00 | Hex: #5F9EA0 | Note: "Limited Edition"
```

**IMPORTANT: Price Modifier Semantics**

When using relative price modifiers (e.g., `+50.00` or `-20.00`):

1. **Base Price Definition:**
   The base price MUST be defined in @OFFER before @VARIANTS
   
2. **Modifier Calculation:**
   Final price = Base price + Modifier
   
3. **Validation:**
   Parsers MUST validate that:
   - A base price exists in @OFFER
   - All modifiers are numeric
   - Final calculated prices are positive
   
4. **Alternative: Absolute Prices**
   For clarity, merchants MAY specify absolute prices instead of modifiers:
   ```
   Type: Color
   Options:
     - Obsidian: 348.00 | Hex: #000000
     - Porcelain: 348.00 | Hex: #F5F5DC  
     - Bay: 398.00 | Hex: #5F9EA0 | Note: "Limited Edition"
   ```
   
   This removes ambiguity but reduces flexibility.

**Example (Apparel Size):**
```
# @VARIANTS
Type: Size
Options:
  - Small: 49.99 | Stock: 12
  - Medium: 49.99 | Stock: 8
  - Large: 49.99 | Stock: 3
  - XL: 54.99 | Stock: 0 | Backorder: True
```

**Multiple Variant Types:**
```
# @VARIANTS
Type: Storage
Options:
  - 128GB: 999.00
  - 256GB: 1099.00

Type: Color
Options:
  - Obsidian: +0.00
  - Porcelain: +0.00
  - Bay: +50.00
```

**IMPORTANT: Handling Multi-Dimensional Variants (The "Flattened" Approach)**

For products with **multiple dependent variations** (e.g., Size AND Color, or Storage AND Color) where stock levels vary per combination, merchants SHOULD list **explicit combinations** rather than separate variant groups.

This ensures deterministic inventory tracking and links a specific SKU/Stock to the exact combination, preventing AI hallucinations about availability.

**Example (Complex Availability - Flattened Approach):**

Instead of defining `Type: Color` and `Type: Storage` separately, combine them into a single list of valid SKUs:

```
# @VARIANTS
Type: Model Selection
Options:
  # Obsidian Combinations
  - Obsidian / 128GB: 999.00  | SKU: GA-OBS-128 | Stock: 10
  - Obsidian / 256GB: 1099.00 | SKU: GA-OBS-256 | Stock: 35
  - Obsidian / 512GB: 1299.00 | SKU: GA-OBS-512 | Stock: 0 | Backorder: True
  
  # Porcelain Combinations
  - Porcelain / 128GB: 999.00 | SKU: GA-POR-128 | Stock: 15
  - Porcelain / 256GB: 1099.00 | SKU: GA-POR-256 | Stock: 23
  # Note: Porcelain / 512GB is omitted because it is discontinued
  
  # Hazel Combinations (Limited Edition)
  - Hazel / 256GB: 1149.00 | SKU: GA-HAZ-256 | Stock: 5 | Note: "Limited Edition"
```

**Why Flatten?**
- Deterministic: Each combination has explicit stock level
- No hallucinations: AI can't assume "Porcelain 512GB" exists if unlisted
- Prevents errors: "Hazel only in 256GB" is clear, not inferred
- Real-world accuracy: Reflects actual inventory constraints

**When NOT to Flatten:**
If all combinations are uniformly available (rare), you MAY use independent lists:
```
# Only if EVERY storage × color combo exists and has similar stock
Type: Storage
Options:
  - 128GB: 999.00
  - 256GB: 1099.00

Type: Color
Options:
  - Obsidian: +0.00
  - Porcelain: +0.00
```

**Benefits:**
- Reduces file count dramatically (1 file instead of 16 for 4 storage × 4 color options)
- Flexible structure accommodates any variant dimension
- Per-variant modifiers (price, SKU, stock, etc.)

**Complexity Guidelines:**

Use @VARIANTS when:
- Total combinations < 50
- Variants share the same base specifications (only superficial attributes differ)
- Example: Same headphones in 3 colors

Use separate product files when:
- Total combinations > 50 (becomes unmanageable)
- Variants have significantly different specifications
- Example: iPhone 15 vs iPhone 15 Pro (different cameras, materials, features)

**Schema.org Mapping:**
- Type → product.additionalProperty.name
- Options → product.offers (array)

---

### 4.11 @LOCALES (Tier 2: Standard)

**Purpose:** Multi-regional support with locale-specific context files.

**Location:** Root file only

**Example:**
```
# @LOCALES
en-US: /commerce.txt (Current)
en-GB: /uk/commerce.txt
de-DE: /de/commerce.txt
fr-FR: /fr/commerce.txt
```

**Resolution Algorithm:**
1. Identify User Agent Locale (e.g., fr-CA)
2. Exact Match: If fr-CA exists, load that path
3. Language Match: If fr exists, load that path
4. Fallback: Use current Root file

---

### 4.12 @SHIPPING (Tier 2: Standard)

**Purpose:** Shipping methods, costs, and carriers.

**Location:** Root or Category files

**Example:**
```
# @SHIPPING
- Standard: Free over $50 | 3-5 Days
- Express: $15.00 | 1-2 Days
- Overnight: $35.00 | Next Day
Carriers: FedEx, DHL, USPS
Regions: US, Canada, Mexico
```

---

### 4.13 @PAYMENT (Tier 2: Standard)

**Purpose:** Accepted payment methods.

**Location:** Root file

**Example:**
```
# @PAYMENT
Methods: Visa, MasterCard, Amex, PayPal, ApplePay, GooglePay
Installments: Available (Klarna, Affirm)
Currency: USD
```

---

### 4.14 @POLICIES (Tier 2: Standard)

**Purpose:** Store policies (returns, warranties, privacy).

**Location:** Root file (can be overridden in Category/Leaf)

**Example:**
```
# @POLICIES
Returns: 30 Days (Buyer pays return shipping)
Warranty: 1 Year Limited (Extended available for purchase)
Privacy: https://example.com/privacy
RefundMethod: Original payment method | 5-7 business days
```

---

### 4.15 @SPECS (Tier 2: Standard)

**Purpose:** Product specifications and technical details.

**Location:** Leaf (Product) files

**Example:**
```
# @SPECS
Display: 6.3" OLED, 120Hz
Processor: Google Tensor G4
RAM: 16GB
Storage: 512GB
Camera: 50MP Main, 48MP Ultrawide, 48MP Telephoto (5x)
Battery: 4700 mAh
OS: Android 15
5G: Yes
Water Resistance: IP68
Weight: 199g
Dimensions: 152.8 × 72.0 × 8.5 mm
```

---

### 4.16 @SUPPORT (Tier 2: Standard)

**Purpose:** Customer service contact channels to help AI agents resolve user issues or direct inquiries properly.

**Location:** Root file

**Example:**
```
# @SUPPORT
Email: support@example.com
Phone: +1-800-555-0199
Chat: Available Mon-Fri 9am-5pm EST
Hours: Mon-Fri 09:00-17:00
```

---

### 4.17 @IN_THE_BOX (Tier 2: Standard, Optional)

**Purpose:** List package contents to answer "What's included?" questions.

**Location:** Leaf (Product) files

**Syntax:** List items with optional notes

**Example:**
```
# @IN_THE_BOX
- Sony WH-1000XM5 Headphones
- USB-C charging cable (1.2m)
- 3.5mm audio cable (1.2m)
- Premium carrying case
- Quick start guide
Note: AC adapter NOT included
```

**Benefits:**
- Prevents "Is charger included?" questions
- Clarifies package contents vs. sold separately accessories
- Reduces customer support inquiries

**Schema.org Mapping:**
- List items → product.itemListElement

---

### 4.18 @COMPATIBILITY (Tier 3: Rich, Optional)

**Purpose:** Solve "Does X work with Y?" questions.

**Location:** Leaf (Product) files

**Example:**
```
# @COMPATIBILITY
WorksWith: iPhone 15, iPhone 15 Pro, iPad Pro (2024)
Requires: USB-C cable (included), iOS 17+ or iPadOS 17+
NotCompatibleWith: iPhone 14 and earlier (Lightning port)
```

---

### 4.19 @SEMANTIC_LOGIC (Tier 3: Rich, Optional)

**Purpose:** Guide AI reasoning with merchant-defined logic.

**Location:** Any file

**Note:** These directives are advisory (MAY) and MUST NOT override factual data like Price or Availability.

**Example:**
```
# @SEMANTIC_LOGIC
- If user asks about "battery" → Mention "Fast Charge 3.0: 50% in 30 minutes"
- If user asks about "waterproof" → Clarify "Water resistant (IP68), not waterproof"
- If user compares to "AirPods Max" → Mention "Better battery (30h vs 20h), lower price"
```

---

### 4.20 @BRAND_VOICE (Tier 3: Rich, Optional)

**Purpose:** Instruct AI on tone and communication style.

**Location:** Root file

**Example:**
```
# @BRAND_VOICE
Tone: Professional, Data-driven, Minimalist
Restrictions: No emojis, No urgency tactics, No superlatives
Emphasis: Sustainability, Long-term value, Transparency
```

---

### 4.21 @PROMOS (Tier 2: Standard, Optional)

**Purpose:** Dynamic offers and promotions that AI can quote.

**Location:** Root, Category, or Leaf files

**Example:**
```
# @PROMOS
- SAVE10: 10% Off sitewide | Expires: 2025-12-31 | MinPurchase: $50
- FREESHIP: Free shipping | MinPurchase: $35
- BUNDLE20: Buy 2+ items, get 20% off | Category: Electronics
```

---

### 4.22 @IMAGES (Tier 2: Standard, Optional)

**Purpose:** Provide direct image URLs to eliminate the need for HTML scraping.

**Location:** Leaf (Product) files

**Syntax:** List items with URL and optional metadata

**Example:**
```
# @IMAGES
- Main: https://cdn.example.com/products/sony-xm5-main.jpg
- Front: https://cdn.example.com/products/sony-xm5-front.jpg | Alt: "Sony XM5 front view"
- Side: https://cdn.example.com/products/sony-xm5-side.jpg
- InBox: https://cdn.example.com/products/sony-xm5-box.jpg | Alt: "Package contents"
```

**Why this matters:**

Without @IMAGES, AI agents must:
1. Scrape HTML to find `<img>` tags 
2. Extract image URLs from DOM
3. Make separate HTTP requests for each image
4. Process images with vision models (additional cost)

With @IMAGES:
1. Agent reads commerce.txt
2. Gets image URLs directly
3. Can fetch only needed images on-demand

**Benefits:**
- **Efficiency:** No HTML parsing needed for image discovery
- **Accuracy:** Ensures agents use canonical product images (not thumbnails or ads)
- **Performance:** Agents can pre-fetch images in parallel
- **User Experience:** Enables faster visual product recommendations in chat interfaces

**Schema.org Mapping:**
- Main → product.image
- Additional images → product.image (array)

---


### 4.23 @AGE_RESTRICTION (Tier 2: Standard, Optional)

**Purpose:** Indicate age requirements for purchase.

**Location:** Leaf (Product) files

**Example:**
```
# @AGE_RESTRICTION
MinimumAge: 18
Reason: "Contains alcohol"
VerificationRequired: True
RestrictedRegions: All
```

**Benefits:** AI can warn users before they attempt to purchase age-restricted items.

---

## 5. Auto-Discovery (robots.txt)

To ensure AI Agents and Crawlers can locate the `commerce.txt` file reliably (especially if redirects or non-standard paths are used), publishers SHOULD include a discovery directive in their `robots.txt` file.

**Syntax:**
`Commerce-TXT: <absolute_url>`

**Example:**

```
User-agent: *
Disallow: /checkout/
Disallow: /cart/

Sitemap: https://example.com/sitemap.xml
Commerce-TXT: https://example.com/commerce.txt
```

## 6. Schema.org Mapping Table

| Directive | CommerceTXT Key | Schema.org Property | Type |
|-----------|----------------|---------------------|------|
| @IDENTITY | Name | store.name | String |
| @PRODUCT | GTIN | product.gtin13 | String |
| @PRODUCT | SKU | product.sku | String |
| @PRODUCT | Brand | product.brand.name | String |
| @OFFER | Price | offer.price | Decimal |
| @OFFER | Currency | offer.priceCurrency | ISO 4217 |
| @OFFER | Availability | offer.availability | Enum |
| @INVENTORY | Stock | offer.inventoryLevel.value | Integer |
| @INVENTORY | StockStatus | offer.availability | Enum |
| @INVENTORY | RestockDate | offer.availabilityStarts | ISO-8601 |
| @REVIEWS | Rating | aggregateRating.ratingValue | Decimal |
| @REVIEWS | Count | aggregateRating.reviewCount | Integer |
| @SUBSCRIPTION | Plans | offer.priceSpecification | Array |
| @SHIPPING | Cost | offer.shippingDetails | Number |
| @SPECS | * | product.additionalProperty | Key-Value |
| @SUPPORT | Email | contactPoint.email | String |
| @SUPPORT | Phone | contactPoint.telephone | String |
| @IN_THE_BOX | * | product.itemListElement | Array |
| @IMAGES | Main | product.image | String |
| @IMAGES | Additional | product.image | Array |
| @AGE_RESTRICTION | MinimumAge | offer.eligibleAge | Integer |
---

## 7. Compliance Tiers

To accommodate different store sizes, compliance is defined in tiers.

### Tier 1: Minimal (Valid)

**Requirement:** Agent can identify the store and find products.

**Mandatory:**
- @IDENTITY
- @CATALOG (at least 1 link)
- @PRODUCT
- @OFFER

### Tier 2: Standard (Recommended)

**Requirement:** Agent can answer policy questions and handle regions.

**Mandatory:**
- Tier 1 + @POLICIES, @LOCALES, @SHIPPING, @PAYMENT, @INVENTORY

**Optional but Recommended:**
- @SUBSCRIPTION (if applicable)
- @REVIEWS
- @PROMOS
- @IN_THE_BOX
- @IMAGES
- @AGE_RESTRICTION (if applicable for regulated products)

### Tier 3: Rich (Agent Optimized)

**Requirement:** Agent can reason, upsell, and check compatibility.

**Mandatory:**
- Tier 2 + @SEMANTIC_LOGIC, @BRAND_VOICE, @COMPATIBILITY

**Optional:**
- @VARIANTS

---

## 8. Locale Resolution & Internationalization

For multi-regional stores, Agents MUST use the **@LOCALES** directive (see Section 4.9) in the Root file to determine the correct context.

**Quick Reference:**
1. **Identify:** User Agent Locale (e.g., fr-CA)
2. **Match:** Exact locale → Language fallback → Root fallback
3. **Load:** Corresponding file path from @LOCALES

For complete details and examples, see **Section 4.11 @LOCALES**.

---

## 9. Versioning Policy

This protocol adheres to Semantic Versioning (SemVer).

- **Major** (1.x → 2.x): Breaking changes to syntax or mandatory fields
- **Minor** (1.0 → 1.1): New optional directives (backward compatible)
- **Patch** (1.0.0 → 1.0.1): Clarifications to documentation

**Forward Compatibility:** Parsers MUST ignore unknown Directives or Keys encountered in valid files (Graceful Degradation). They SHOULD NOT throw errors on unknown fields prefixed with X-.

---

## 10. Error Handling, Security & Trust

### 10.1 Cross-Verification & Trust Scores (Anti-Hallucination Policy)

To prevent merchants from providing false context (e.g., inflating @REVIEWS ratings or misrepresenting @OFFER prices compared to checkout), AI Agents and Crawlers are advised to perform Cross-Verification.

#### Recommended Agent Behavior:

1. **Spot Check:** Periodically compare commerce.txt values (Price, Stock, Rating) against the rendered HTML page and Schema.org markup.
2. **Trust Score Penalty:** If a discrepancy exceeding 5% is detected (e.g., Price in commerce.txt is $100 but checkout shows $110+), the domain's Trust Score should be downgraded.
3. **Verification Sources:** For @REVIEWS, Agents SHOULD prioritize data backed by a verifiable Source URL (e.g., Trustpilot, Google Customer Reviews, Yotpo).

#### 10.1.1 Trust Score Model (Conceptual Framework)

The following is a **conceptual framework** for implementing merchant trust mechanisms. AI platforms are expected to develop their own sophisticated trust models (e.g., Bayesian scoring, machine learning-based reputation systems) adapted to their specific requirements and user protection needs.

**Conceptual Principles:**

1. **Baseline Trust:** New merchants begin with neutral trust status
2. **Verification:** Periodic cross-validation of CommerceTXT data against actual site data
3. **Penalties:** Significant deviations MUST result in downgraded trust status
4. **Recovery:** Merchants who correct discrepancies and maintain accuracy should be able to rebuild trust over time
5. **Transparency:** Platforms SHOULD communicate trust levels to users when appropriate

**Verification Scope:**

Trust verification MUST check multiple data points to prevent circumvention:
1. **Product page displayed price** (visible HTML)
2. **Schema.org offer.price markup** (structured data)
3. **Add-to-cart API response** (if publicly available)
4. **Checkout subtotal** (before shipping/tax, via headless browser simulation when feasible)

**Hidden Fee Policy:**
Fees that appear only at checkout (handling charges, convenience fees, mandatory insurance) and are not disclosed in CommerceTXT constitute a trust violation. Only standard shipping and location-based taxes are exempt from this requirement.

**Spot Check Frequency Guidelines:**
Platforms SHOULD adjust verification frequency based on:
- Site traffic volume and request patterns
- Historical accuracy record
- Transaction value and user risk exposure
- Resource constraints and crawling policies

**Suggested Categories:**
- **Trusted:** Consistently accurate data, no recent violations
- **Verified:** Generally accurate with minor historical issues
- **Questionable:** Frequent discrepancies or outdated data
- **Untrusted:** Significant violations or systematic misrepresentation

**User Communication:**
When trust levels are below "Trusted," AI responses SHOULD include appropriate caveats:
- Verified: "According to merchant data..." or "Merchant reports..."
- Questionable: "Merchant claims... but verification is pending"
- Untrusted: Exclude from recommendations or flag explicitly

**Platform Discretion:**
AI platforms MAY implement stricter or more lenient trust mechanisms based on:
- Industry vertical (e.g., luxury goods vs electronics)
- Transaction value (higher stakes = stricter requirements)
- Historical merchant behavior patterns
- User complaint and return rate data
- Regulatory requirements in their jurisdiction

### 10.2 404 Not Found
Agents MUST halt traversal for that specific branch and log "Context Unavailable".

### 10.3 Malformed Syntax
Agents MUST discard the specific line and continue parsing the rest of the file.

### 10.4 PII & Secrets
Files MUST NOT contain personally identifiable information (employee emails) or API secrets. Agents MUST ignore keys resembling credentials (e.g., client_secret, api_key).

### 10.5 Competitive Scraping & Data Protection

**Merchant Concern:**
A common objection to CommerceTXT is: "Won't this make it easier for competitors to steal my prices and undercut me?"

**Reality Check:**
Your pricing data is already public in your HTML. Competitors who want to scrape your prices are already doing so. CommerceTXT does not expose new data—it simply provides a more efficient format.

**Key Arguments:**

1. **No New Data Exposure:**
   Everything in CommerceTXT (price, inventory, specs) is already visible on your product pages. CommerceTXT is not a security vulnerability—it's a performance optimization.

2. **Reduced Server Load:**
   Without CommerceTXT, bots scrape your entire HTML (2.5 MB pages, JavaScript execution, multiple requests). With CommerceTXT, they fetch one 5KB file. This actually REDUCES the burden on your infrastructure.

3. **Legitimate AI vs Malicious Scrapers:**
   CommerceTXT is designed for legitimate AI assistants (ChatGPT, Claude, Gemini) helping consumers make informed decisions. Malicious scrapers will continue using HTML regardless.

**Protection Strategies:**

If you're concerned about aggressive scraping, implement these controls:

**A. User-Agent Filtering (WAF/CDN Level)**
```
# Allow only verified AI bots
Allow: Googlebot, GPTBot, ClaudeBot, ChatGPT-User
Block: * (all others)

# Rate limiting per user-agent
Max requests per hour: 1000 for verified bots, 10 for unknown
```

**B. robots.txt Guidance**
```
# Explicitly allow verified bots, disallow others
User-agent: GPTBot
Allow: /commerce.txt

User-agent: ClaudeBot
Allow: /commerce.txt

User-agent: *
Disallow: /commerce.txt
```

**C. Authentication (Advanced)**
Future versions may support API keys for high-sensitivity merchants:
```
# @IDENTITY
AccessControl: Authenticated
APIKeyRequired: True
ApplyAt: https://example.com/api-access
```

**D. Dynamic Obfuscation (Not Recommended)**
Some merchants may consider obfuscating prices (e.g., "Price: [REDACTED], visit site"). This defeats the purpose of CommerceTXT and will result in low Trust Scores. Not recommended.

**Bottom Line:**
CommerceTXT trades off marginal convenience for competitors (who can already scrape you) for massive convenience for legitimate AI assistants (driving traffic to your store). The benefits far outweigh the risks.

### 10.6 Size & Complexity Limits (DoS Protection)

**Requirement:** Agents and Parsers MUST enforce strict limits to prevent Denial of Service (DoS) attacks and resource exhaustion.

**Standard Limits:**
- **Max File Size:** 10 MB (10,485,760 bytes)
- **Max Line Length:** 100 KB (102,400 bytes)

**Implementation Behavior:**
- Parsers reading from a stream SHOULD abort the connection if limits are exceeded.
- Parsers MUST reject files larger than the 10 MB limit to protect memory.

---

## 11. Telemetry & Analytics

Agents are RECOMMENDED to include the following headers in HTTP requests when fetching CommerceTXT files:

```
X-Agent-Name: (e.g., "Claude", "ChatGPT")
X-Context-Version: (e.g., "1.0")
X-Agent-Session-ID: (optional, for analytics)
```

**Merchant Responsibilities:**

Merchants SHOULD configure appropriate HTTP response headers for CommerceTXT files:

**Cache-Control:**
```
# High-velocity inventory (frequent stock changes)
Cache-Control: max-age=300, must-revalidate   # 5 minutes

# Stable inventory (changes daily/weekly)
Cache-Control: max-age=3600, must-revalidate  # 1 hour

# Static content (policies, specs)
Cache-Control: max-age=86400, must-revalidate # 24 hours
```

**Content-Type:**
```
Content-Type: text/plain; charset=utf-8
```

**CORS (if accessed from browser-based tools):**
```
Access-Control-Allow-Origin: *
```

**Telemetry Benefits:**
- Merchants can track which AI platforms are reading their data
- Agents can respect cache headers for efficient updates
- Both parties can measure adoption and usage patterns

---

## 12. Future Considerations (Community Discussion Required)

The following directives are proposed for future versions but require broader community input and real-world testing before inclusion in the standard.

### 12.1 @ACTIONS (Proposed for v2.0+)

**Purpose:** Enable AI agents to perform transactional actions (add to cart, apply coupons, check real-time inventory via API).

**Status:** This is a HIGHLY EXPERIMENTAL concept that requires extensive security review and industry consensus before any implementation.

**Why it requires discussion:**
- **Security concerns:** OAuth flows, CSRF protection, user consent mechanisms, API authentication
- **User-in-the-loop requirement:** AI MUST NOT make purchases autonomously—every transaction requires explicit user confirmation
- **Standardization challenges:** Every e-commerce platform has different APIs
- **Liability questions:** Who is responsible if an AI makes a purchase error?
- **Privacy implications:** Sharing cart/checkout APIs with AI systems
- **Fraud prevention:** How to prevent malicious AI agents from abusing transactional endpoints

**CRITICAL SAFETY REQUIREMENT:**

Any implementation of @ACTIONS MUST enforce strict user-in-the-loop controls:
- AI cannot complete purchases autonomously
- Every action requires explicit user confirmation via secure UI
- Users must review cart, price, and shipping before authorizing payment
- Payment credentials MUST NEVER be accessible to AI agents
- All transactions must maintain full audit trail

**Proposed syntax (for discussion only - NOT for implementation):**
```
# @ACTIONS
CheckInventory: GET https://api.example.com/inventory/{sku}
  Response: { "stock": number, "available": boolean }
  Auth: None (read-only, public endpoint)
  
AddToCart: POST https://api.example.com/cart/add
  Params: sku, quantity
  Auth: OAuth2 with explicit user consent
  UserConfirmation: Required before execution
  RateLimiting: 10 requests per minute per user
  
ApplyCoupon: POST https://api.example.com/cart/coupon
  Params: code
  Auth: Session token
  UserConfirmation: Required
```

**Open questions for community:**
1. Should CommerceTXT remain read-only, or evolve into a transactional protocol?
2. How do we standardize authentication across diverse platforms?
3. What consumer protections are needed for AI-initiated transactions?
4. Should this be opt-in at both merchant AND user level?
5. How do we prevent abuse while maintaining convenience?
6. What liability framework is needed?

**Recommendation:**
CommerceTXT v1.0 should remain **read-only**. Transactional capabilities should only be considered after:
- Trust Score system is proven in production
- Industry-wide security standards are established
- User consent frameworks are legally validated
- Fraud prevention mechanisms are demonstrated

**Feedback mechanism:** Join discussion at https://github.com/commercetxt/commercetxt/discussions

---

### 12.2 @SUSTAINABILITY (Proposed for v1.1)

**Purpose:** Verified environmental and ethical claims to reduce greenwashing.

**Why it requires discussion:**
- **Verification problem:** How do we ensure claims are legitimate?
- **Certification standards:** Which certifications are recognized globally?
- **Proof requirement:** Should links to third-party verification be mandatory?
- **Scope definition:** Carbon footprint? Labor practices? Materials? All of the above?

**Proposed syntax (for discussion):**
```
# @SUSTAINABILITY
CarbonNeutral: Yes
  Verified: https://climatepartner.com/cert/12345
  Certificate: ClimatePartner ID 12345-2024
  
Packaging: 100% Recycled Materials
  Certification: FSC-C123456
  
RepairProgram: Available
  Duration: 7 years of spare parts
  Details: https://example.com/repair
  
EthicalSourcing: Fair Trade Certified
  Verification: https://fairtradecertified.org/verify/12345
  
TradeIn: $200 credit for old devices
  Link: https://example.com/trade-in
```

**Open questions for community:**
1. Should sustainability claims require third-party verification links?
2. Which certification bodies should be recognized in the standard?
3. How do we handle regional differences in sustainability standards?
4. Should unverified claims be allowed with disclaimers?

**Anti-greenwashing policy:** 
- Claims without verification URLs SHOULD include `Unverified: True` flag
- AI agents SHOULD caveat unverified claims when responding to users
- False claims violate the spirit of CC0 Public Domain and may be subject to consumer protection laws

**Feedback mechanism:** Join discussion at https://github.com/commercetxt/commercetxt/discussions

---

## 13. Complete Example: Full Implementation

This section provides a complete example of a Tier 3 (Rich) implementation across all three hierarchy levels.

### Level 1: Root File (commerce.txt)

```
# commerce.txt
Version: 1.0
LastUpdated: 2025-12-16T10:00:00Z

# @IDENTITY
Name: TechStore Global
URL: https://techstore.example.com
Currency: USD
Description: Premium consumer electronics and accessories

# @LOCALES
en-US: /commerce.txt (Current)
en-GB: /uk/commerce.txt
de-DE: /de/commerce.txt
fr-FR: /fr/commerce.txt
ja-JP: /jp/commerce.txt

# @PAYMENT
Methods: Visa, MasterCard, Amex, Discover, PayPal, ApplePay, GooglePay
Installments: Available (Klarna, Affirm, Afterpay)
Currency: USD
AcceptedCurrencies: USD, EUR, GBP, JPY

# @SHIPPING
- Standard: Free over $50 | 5-7 Business Days
- Express: $15.00 | 2-3 Business Days
- Overnight: $35.00 | Next Business Day
Carriers: FedEx, UPS, DHL
Regions: US, Canada, UK, EU, Japan, Australia
InternationalDuties: Customer responsibility (DDP available for EU)

# @POLICIES
Returns: 30 Days (Free return shipping for defective items)
Warranty: 1 Year Limited (Extended 3-year available for $49)
Privacy: https://techstore.example.com/privacy
RefundMethod: Original payment method | 5-7 business days
PriceMatch: Yes (within 14 days of purchase)

# @SUPPORT
Email: support@techstore.example.com
Phone: 1-800-TECH-STORE
Chat: Available 24/7
Hours: Mon-Fri 9AM-9PM EST, Sat-Sun 10AM-6PM EST

# @BRAND_VOICE
Tone: Professional, Informative, Tech-savvy
Restrictions: No emojis, No urgency tactics, No hyperbole
Emphasis: Product quality, Customer service, Technical accuracy

# @CATALOG
- Headphones: /categories/headphones.txt
- Smartphones: /categories/smartphones.txt
- Tablets: /categories/tablets.txt
- Smartwatches: /categories/smartwatches.txt
- Accessories: /categories/accessories.txt
```

### Level 2: Category File (headphones.txt)

```
# headphones.txt
Category: Wireless Headphones
LastUpdated: 2025-12-16T09:00:00Z

# @FILTERS
Brands: Sony, Bose, Apple, Sennheiser
Type: Over-Ear, On-Ear, Earbuds
Features: ANC (Active Noise Cancellation), Wireless, Bluetooth 5.3
PriceRange: $149-$549

# @POLICIES
Returns: 45 Days (Extended for this category)
TrialPeriod: 30-day satisfaction guarantee

# @PROMOS
- HEADPHONES20: 20% Off all headphones | Expires: 2025-12-31 | Code: HEADPHONES20
- FREESHIP: Free shipping on all orders | No minimum
- TRADE-IN: Up to $100 credit for old headphones

# @SEMANTIC_LOGIC
- If user asks about "noise cancelling" → Prioritize ANC models (Sony XM5, Bose QC45)
- If user asks about "best battery" → Mention Sony XM5 (30h) and Sennheiser Momentum 4 (60h)
- If user compares to "AirPods Max" → Mention Sony XM5 as "better value: $200 less, longer battery"

# @ITEMS
- Sony WH-1000XM5: /products/sony-xm5.txt
- Bose QuietComfort 45: /products/bose-qc45.txt
- Apple AirPods Max: /products/airpods-max.txt
- Sennheiser Momentum 4: /products/sennheiser-momentum4.txt
```

### Level 3: Product File (sony-xm5.txt)

```
# sony-xm5.txt
ProductID: SONY-XM5-2024
LastUpdated: 2025-12-16T09:30:00Z

# @PRODUCT
Name: Sony WH-1000XM5 Wireless Noise Cancelling Headphones
GTIN: 027242919412
SKU: WH1000XM5
URL: https://techstore.example.com/products/sony-wh-1000xm5
Brand: Sony
Model: WH-1000XM5
Category: Over-Ear Headphones
ReleaseDate: 2024-05-12

# @OFFER
Price: 348.00
Currency: USD
Availability: InStock
Condition: New
PriceValidUntil: 2025-12-31T23:59:59Z
TaxIncluded: False
TaxNote: "Sales tax calculated at checkout"
MSRP: 399.00
Discount: 13% Off

# @INVENTORY
Stock: 42
LowStockThreshold: 10
StockStatus: InStock
MaxQuantityPerOrder: 5
LastUpdated: 2025-12-16T09:30:00Z
ReservedStock: 3 (Pre-orders)
AvailableForPurchase: 39

# @VARIANTS
Type: Color
Options:
  - Black: 348.00 | SKU: WH1000XM5-BLK | Stock: 25 | Hex: #000000
  - Silver: 348.00 | SKU: WH1000XM5-SLV | Stock: 12 | Hex: #C0C0C0
  - Midnight Blue: 368.00 | SKU: WH1000XM5-BLU | Stock: 5 | Hex: #191970 | Note: "Limited Edition"

# @REVIEWS
Rating: 4.7
RatingScale: 5.0
Count: 1243
Verified: 89% (1107 verified purchases)
TopTags: "Best ANC", "Great battery", "Comfortable", "Tight fit", "Pricey"
Source: https://www.trustpilot.com/review/techstore.example.com
LastUpdated: 2025-12-16T08:00:00Z

# @SPECS
Type: Over-Ear, Closed-Back
Driver: 30mm
FrequencyResponse: 4 Hz - 40,000 Hz
Impedance: 48 ohms
Sensitivity: 102 dB/mW
Battery: 4700 mAh | 30 Hours (ANC On) | 40 Hours (ANC Off)
ChargingTime: 3.5 Hours (Full) | 10 min = 5 Hours (Quick Charge)
ChargingPort: USB-C
Bluetooth: 5.3 | Codecs: SBC, AAC, LDAC
ANC: Yes (Industry-leading with 8 microphones)
Microphones: 8 (4 for ANC, 4 for calls)
Controls: Touch panel (swipe, tap)
VoiceAssistant: Google Assistant, Alexa
Multipoint: Yes (connect 2 devices simultaneously)
Weight: 250g
Foldable: Yes (with carrying case)
WaterResistance: No (not rated)
IncludedAccessories: USB-C cable, 3.5mm audio cable, carrying case

# @IN_THE_BOX
- Sony WH-1000XM5 Headphones
- USB-C charging cable (1.2m)
- 3.5mm audio cable (1.2m)
- Premium carrying case
- Quick start guide
Note: AC adapter NOT included

# @COMPATIBILITY
WorksWith: iPhone 15/14/13, Samsung Galaxy S24/S23, iPad Pro, MacBook, Windows PC, Android 9+
Requires: Bluetooth 4.2+ or wired connection (3.5mm)
OptimalWith: Devices supporting LDAC codec (Sony Xperia, Pixel phones)
NotCompatibleWith: Devices without Bluetooth or 3.5mm jack

# @IMAGES
- Main: https://cdn.techstore.example.com/products/sony-xm5-main.jpg
- Front: https://cdn.techstore.example.com/products/sony-xm5-front.jpg | Alt: "Sony WH-1000XM5 front view"
- Side: https://cdn.techstore.example.com/products/sony-xm5-side.jpg | Alt: "Side profile showing touch controls"
- Wearing: https://cdn.techstore.example.com/products/sony-xm5-wearing.jpg | Alt: "Person wearing headphones"
- InBox: https://cdn.techstore.example.com/products/sony-xm5-contents.jpg | Alt: "Package contents laid out"

# @SEMANTIC_LOGIC
- If user asks about "ANC vs Bose" → "XM5 has slightly better ANC, longer battery (30h vs 24h)"
- If user asks about "for flying" → "Excellent for travel: 30h battery, superior ANC, foldable design"
- If user asks about "calls" → "Crystal clear calls with 4-mic beamforming and wind noise reduction"
- If user asks about "gaming" → "Not ideal for gaming (higher latency on Bluetooth). Consider wired mode."
- If user compares to "XM4" → "XM5: Better ANC, lighter (250g vs 254g), redesigned (not foldable hinges)"

# @PROMOS
- Applied: HEADPHONES20 (20% Off from category)
- TradeIn: Up to $100 credit for old Sony/Bose headphones

# @SUSTAINABILITY
Packaging: 100% Recycled Materials
  Certification: FSC-C123456
  Verified: https://fsc.org/verify/123456
RepairProgram: Available
  Duration: 7 years of spare parts availability
  Details: https://sony.com/repair-program
RecyclingProgram: Yes
  Details: https://sony.com/recycling
  TradeIn: $50 credit for recycling any brand headphones
Unverified: False
```

### Example: Age-Restricted Product (Wine)
```
# wine-cabernet.txt

# @PRODUCT
Name: Napa Valley Cabernet Sauvignon 2020
SKU: WINE-CAB-2020
URL: https://wineshop.example.com/products/cabernet-2020

# @OFFER
Price: 45.00
Currency: USD
Availability: InStock

# @AGE_RESTRICTION
MinimumAge: 21
Reason: "Alcoholic beverage"
VerificationRequired: True
RestrictedRegions: US, Canada
Note: "ID verification required at delivery"
```

---

## 14. Contributing & Governance

CommerceTXT is an open standard maintained by the community.

**How to contribute:**
1. Propose changes via GitHub Issues: https://github.com/commercetxt/commercetxt/issues
2. Discuss in community forums: https://github.com/commercetxt/commercetxt/discussions
3. Submit pull requests with spec updates
4. Participate in quarterly working group meetings (dates announced via GitHub)

**Governance Model:**
- **Working Group:** Open to all contributors, decisions by consensus
- **Maintainers:** Tsanko Zanov (founder), plus community-elected co-maintainers
- **RFC Process:** Major changes require 30-day comment period before adoption
- **Versioning Authority:** Working group votes on version bumps (majority rule)

**Communication Channels:**
- GitHub Discussions (primary): https://github.com/commercetxt/commercetxt/discussions
- Email: hello@commercetxt.org

**Validation Tools:**

The working group maintains reference implementations and validation tools:
- **Online Validator:** https://commercetxt.org/validator (coming soon) (validates syntax and semantic rules)
- **Python Parser:** https://github.com/commercetxt/parser-python (coming soon) (reference implementation)
- **JavaScript Parser:** https://github.com/commercetxt/parser-js (coming soon) (browser-compatible)

These tools enforce critical validation rules:
- @VARIANTS price modifiers require base @OFFER price
- @INVENTORY LastUpdated timestamps must be recent
- @REVIEWS TopTags must include balanced sentiment when applicable
- Schema.org mapping correctness
- UTF-8 encoding validation

**License:** CC0 1.0 Universal (Public Domain) - No attribution required, but appreciated.

**Trademark Notice:** "CommerceTXT" is maintained by the CommerceTXT Workgroup. While the spec is public domain, please respect the project name and attribution when implementing the standard.

---

## End of Specification

**Version:** 1.0.1 (Stable Release)  
**Last Modified:** 2026-01-08  
**Contact:** hello@commercetxt.org  
**GitHub:** https://github.com/commercetxt/commercetxt/
**Website:** https://commercetxt.org

For version history, see [CHANGELOG.md](../CHANGELOG.md).