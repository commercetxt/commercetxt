# Changelog

All notable changes to the CommerceTXT Protocol will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2025-12-24

### Enhanced

- **AI Bridge (`--prompt`)**: Comprehensive text output now includes:
    - @INVENTORY (stock levels)
    - @REVIEWS (ratings, tags)
    - @SPECS (top 5 technical details)
    - @VARIANTS (color/size options)
    - @SHIPPING (delivery methods)
    - @PROMOS (active promotions)
    - @COMPATIBILITY
    - @SEMANTIC_LOGIC
    - @BRAND_VOICE
    - @IMAGES (visual descriptions)
    - @AGE_RESTRICTION
- **Token efficiency**: ~120 tokens (vs 400+ in JSON, 8,500+ in HTML)
- **CLI**: Removed unnecessary header from `--prompt` output

### Fixed
- Bridge now correctly handles all directive types
- Improved output formatting for nested structures

## [1.0.1] - 2025-12-17

### Added
- **@IMAGES directive (Tier 2: Optional)**: Provides direct image URLs to eliminate HTML scraping overhead for product visuals
- **@AGE_RESTRICTION directive (Tier 2: Optional)**: Indicates age requirements for regulated products (alcohol, tobacco, etc.)

### Clarified
- **@PRODUCT URL field**: Added URL as a Recommended field with guidance on when and why to use it. While agents can construct URLs from file paths, explicit URLs prevent ambiguity for multi-language sites, non-standard URL patterns, and future transactional features.

### Changed
- Updated all examples in Section 12 (Complete Example) to include URL field in @PRODUCT directive
- Updated Schema.org Mapping Table to include @IMAGES and @AGE_RESTRICTION
- Updated Compliance Tiers (Section 6) to list new optional directives

### Documentation
- Added "Why URL is Recommended" explanation in Section 4.5
- Improved @IMAGES documentation to clarify efficiency benefits vs HTML scraping

## [1.0.0] - 2025-12-16

### Added
- Initial stable release of CommerceTXT Protocol Specification
- Core directives: @IDENTITY, @CATALOG, @PRODUCT, @OFFER, @INVENTORY
- Support for @SUBSCRIPTION, @REVIEWS, @VARIANTS
- Multi-regional support with @LOCALES
- Trust Score framework for merchant accountability
- Schema.org mapping table
- Complete implementation examples across three hierarchy levels (Root, Category, Product)
- Compliance tiers (Minimal, Standard, Rich)
- Error handling and security guidelines
- Future considerations: @ACTIONS and @SUSTAINABILITY

[1.0.1]: https://github.com/commercetxt/commercetxt/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/commercetxt/commercetxt/releases/tag/v1.0.0