"""
Main RAG Generator class.
"""

from __future__ import annotations

import re
from typing import Any

from .constants import (
    DEFAULT_PLURAL_ATTRIBUTES,
    MAX_LIST_ITEMS,
    MAX_SHARDS,
    MIN_VARIANT_GROUP_PARTS,
)
from .semantic_tags import SemanticTagger
from .shards import ShardBuilder


class RAGGenerator:
    """
    Generates Retrieval-Augmented Generation (RAG) text shards.

    Converts CommerceTXT structured data into vector-database-ready shards
    with semantic tagging for intelligent filtering.
    """

    include_metadata: bool
    tagger: SemanticTagger
    shard_builder: ShardBuilder
    plural_attributes: set[str]
    _seen_hashes: set[str]

    def __init__(
        self,
        include_metadata: bool = True,
        extra_plural: set[str] | None = None,
        include_confidence: bool = True,
        include_negative_tags: bool = True,
    ) -> None:
        self.include_metadata = include_metadata
        self.tagger = SemanticTagger()
        self.shard_builder = ShardBuilder(
            include_metadata=include_metadata,
            include_confidence=include_confidence,
            include_negative_tags=include_negative_tags,
        )

        # Plural attributes
        self.plural_attributes: set[str] = DEFAULT_PLURAL_ATTRIBUTES.copy()
        if extra_plural:
            self.plural_attributes.update(extra_plural)

        # Deduplication tracking (explicit type annotation)
        self._seen_hashes: set[str] = set()

        # Batch mode flag (explicit initialization instead of hasattr check)
        self._batch_mode: bool = False

    def _add_unique_shard(
        self, shard: dict[str, Any], shards_list: list[dict[str, Any]]
    ) -> bool:
        """
        Add shard to list only if it's unique (not seen before).

        Returns:
            True if shard was added, False if it was a duplicate.
        """
        shard_hash = self.shard_builder.compute_content_hash(shard)

        if shard_hash not in self._seen_hashes:
            self._seen_hashes.add(shard_hash)
            shards_list.append(shard)
            return True
        return False

    def reset_deduplication(self) -> None:
        """Reset the deduplication cache. Useful for batch processing."""
        self._seen_hashes.clear()

    def generate(
        self, data: dict[str, Any], as_text: bool = False
    ) -> str | list[dict[str, Any]]:
        """
        Main generation method.

        Automatically resets deduplication cache in single-product mode.
        For batch processing, use generate_batch() which controls deduplication.

        Args:
            data: Product data dictionary
            as_text: If True, return concatenated text instead of shard list

        Returns:
            List of shards or concatenated text string
        """
        # Auto-reset deduplication for single-product mode
        # (batch mode is controlled by generate_batch)
        if not self._batch_mode:
            self.reset_deduplication()

        all_shards: list[dict[str, Any]] = []
        semantic_tags = self.tagger.generate_tags(data)

        # Subject anchor
        brand = str(data.get("BRAND") or "").strip()
        item = str(data.get("ITEM") or "").strip()
        item_id = f"{brand} {item}"
        item_id = re.sub(r"\s+", " ", item_id).strip()
        item_id = ShardBuilder.truncate_text(item_id)

        shard = self.shard_builder.create_shard(
            item_id, data, "subject_anchor", 0, semantic_tags
        )
        self._add_unique_shard(shard, all_shards)

        # Price & Currency
        if data.get("PRICE"):
            price = ShardBuilder.truncate_text(str(data["PRICE"]))
            shard = self.shard_builder.create_shard(
                price, data, "price", 1, semantic_tags
            )
            self._add_unique_shard(shard, all_shards)

        if data.get("CURRENCY"):
            currency = ShardBuilder.truncate_text(str(data["CURRENCY"]))
            shard = self.shard_builder.create_shard(
                currency, data, "currency", 2, semantic_tags
            )
            self._add_unique_shard(shard, all_shards)

        # Specs
        specs = data.get("SPECS", {})
        if isinstance(specs, dict):
            for idx, (_key, value) in enumerate(specs.items()):
                if value is None:
                    continue

                if isinstance(value, list):
                    value = value[:MAX_LIST_ITEMS]

                value_str = ShardBuilder.truncate_text(str(value))
                shard = self.shard_builder.create_shard(
                    value_str, data, "specification", idx + 3, semantic_tags
                )
                self._add_unique_shard(shard, all_shards)

        # Description
        if data.get("DESCRIPTION"):
            desc = ShardBuilder.truncate_text(str(data["DESCRIPTION"]))
            shard = self.shard_builder.create_shard(
                desc, data, "description", len(all_shards), semantic_tags
            )
            self._add_unique_shard(shard, all_shards)

        # Brand voice
        if data.get("BRAND_VOICE"):
            voice = ShardBuilder.truncate_text(str(data["BRAND_VOICE"]))
            shard = self.shard_builder.create_shard(
                voice, data, "brand_voice", len(all_shards), semantic_tags
            )
            self._add_unique_shard(shard, all_shards)

        # Variants
        variant_shards = self._generate_variant_shards(data, semantic_tags)
        for shard in variant_shards:
            self._add_unique_shard(shard, all_shards)

        # Reviews
        review_shards = self._generate_reviews_shards(data, semantic_tags)
        for shard in review_shards:
            self._add_unique_shard(shard, all_shards)

        # Subscription
        subscription_shards = self._generate_subscription_shards(data, semantic_tags)
        for shard in subscription_shards:
            self._add_unique_shard(shard, all_shards)

        # Images
        image_shards = self._generate_image_shards(data, semantic_tags)
        for shard in image_shards:
            self._add_unique_shard(shard, all_shards)

        # Compatibility
        compatibility_shards = self._generate_compatibility_shards(data, semantic_tags)
        for shard in compatibility_shards:
            self._add_unique_shard(shard, all_shards)

        # Promotions
        promo_shards = self._generate_promo_shards(data, semantic_tags)
        for shard in promo_shards:
            self._add_unique_shard(shard, all_shards)

        # Sustainability
        sustainability_shards = self._generate_sustainability_shards(
            data, semantic_tags
        )
        for shard in sustainability_shards:
            self._add_unique_shard(shard, all_shards)

        # Semantic logic
        semantic_logic_shards = self._generate_semantic_logic_shards(
            data, semantic_tags
        )
        for shard in semantic_logic_shards:
            self._add_unique_shard(shard, all_shards)

        # Limit total shards
        all_shards = all_shards[:MAX_SHARDS]

        if as_text:
            return "\n\n".join([s["text"] for s in all_shards])
        return all_shards

    def generate_batch(
        self,
        items: list[dict[str, Any]],
        as_text: bool = False,
        deduplicate_across_products: bool = True,
    ) -> list[dict[str, Any]] | str:
        """
        Batch processing with error recovery and deduplication.

        Args:
            items: List of product data dictionaries
            as_text: Return as text instead of list of shards
            deduplicate_across_products: If True, deduplicate across all products.
                                        If False, reset cache between products.

        Returns:
            List of shards or text output

        Note:
            Sets _batch_mode flag to prevent auto-reset in generate().
        """
        all_shards = []
        errors = []

        # Enable batch mode to prevent auto-reset in generate()
        original_batch_mode = self._batch_mode
        self._batch_mode = True

        try:
            # Reset deduplication cache for batch
            if deduplicate_across_products:
                self.reset_deduplication()

            for idx, item_data in enumerate(items):
                try:
                    # Reset per-product if not deduplicating across products
                    if not deduplicate_across_products:
                        self.reset_deduplication()

                    product_shards = self.generate(item_data, as_text=False)
                    if isinstance(product_shards, list):
                        all_shards.extend(product_shards)
                except Exception as e:
                    errors.append(
                        {
                            "index": idx,
                            "item": item_data.get("ITEM", "Unknown"),
                            "error": str(e),
                        }
                    )
                    continue

            if as_text:
                return "\n\n".join([s["text"] for s in all_shards])
            return all_shards

        finally:
            # Restore original batch mode state
            self._batch_mode = original_batch_mode

    def _generate_variant_shards(
        self, data: dict[str, Any], semantic_tags: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate separate shards for each variant.

        Each variant becomes searchable independently.
        Example: "Obsidian 128GB" → finds this specific variant

        Args:
            data: Product data dictionary
            semantic_tags: Semantic tags for the product

        Returns:
            List of variant shards
        """
        shards: list[dict[str, Any]] = []

        if "VARIANTS" not in data:
            return shards

        variants = data["VARIANTS"]
        if not isinstance(variants, dict):
            return shards

        variant_type = variants.get("Type", "Variant")
        options = variants.get("Options", [])

        if not isinstance(options, list):
            return shards

        for _idx, option in enumerate(options):
            if not isinstance(option, str):
                continue

            parsed = self._parse_variant_option(option)

            if not parsed:
                continue

            # Extract structured attributes (color, storage, size, etc)
            attributes = self._extract_variant_attributes(parsed["name"])

            # Generate searchable text
            text = f"{variant_type}: {parsed['name']}"
            if parsed.get("price"):
                text += f" - ${parsed['price']}"
            if parsed.get("stock"):
                text += f" ({parsed['stock']} in stock)"

            # Add note if present
            if parsed.get("note"):
                text += f" - {parsed['note']}"

            # Create shard with variant metadata
            metadata = data.copy() if self.include_metadata else {}
            metadata.update(
                {
                    "attr_type": "variant",
                    "variant_type": variant_type,
                    "variant_name": parsed["name"],
                    "variant_sku": parsed.get("sku"),
                    "variant_price": parsed.get("price"),
                    "variant_stock": parsed.get("stock"),
                    "variant_hex": parsed.get("hex_color"),
                    "variant_attributes": attributes,
                    "original_data": option,
                }
            )

            shard = {
                "text": ShardBuilder.truncate_text(text),
                "metadata": metadata,
            }
            shards.append(shard)

        return shards

    def _parse_variant_option(self, option: str) -> dict[str, Any]:
        """
        Parse variant option string.

        Format: "Name: Price | Key: Value | Key: Value"
        Example: "Obsidian / 128GB: 999.00 | SKU: GA05843-128-OBS | Stock: 22"

        Args:
            option: Variant option string

        Returns:
            Dictionary with parsed variant data
        """
        result: dict[str, Any] = {}

        # Split by pipe
        parts = [p.strip() for p in option.split("|")]

        if not parts:
            return result

        # First part: "Name: Price"
        first = parts[0]
        if ":" in first:
            name_part, price_part = first.split(":", 1)
            result["name"] = name_part.strip()
            result["price"] = price_part.strip()
        else:
            result["name"] = first.strip()

        # Remaining parts: "Key: Value"
        for part in parts[1:]:
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "sku":
                result["sku"] = value
            elif key == "stock":
                # Extract number from "22" or "22 units"
                match = re.search(r"\d+", value)
                if match:
                    result["stock"] = str(match.group())
            elif key == "hex":
                result["hex_color"] = value
            elif key == "note":
                result["note"] = value

        return result

    def _generate_reviews_shards(
        self, data: dict[str, Any], semantic_tags: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate shards from @REVIEWS including TopTags intelligence.

        TopTags provide semantic context about customer sentiment.

        Args:
            data: Product data dictionary
            semantic_tags: Semantic tags for the product

        Returns:
            List of review shards
        """
        shards: list[dict[str, Any]] = []

        if "REVIEWS" not in data:
            return shards

        reviews = data["REVIEWS"]
        if not isinstance(reviews, dict):
            return shards

        # Basic review shard
        rating = reviews.get("Rating")
        count = reviews.get("Count")

        if rating and count:
            text = f"Customer rating: {rating}/5 based on {count} reviews"

            verified = reviews.get("Verified")
            if verified:
                text += f" ({verified} verified)"

            metadata = data.copy() if self.include_metadata else {}
            metadata.update(
                {
                    "attr_type": "reviews",
                    "rating": float(rating),
                    "review_count": int(count),
                    "rating_scale": reviews.get("RatingScale", "5.0"),
                }
            )

            shard = {
                "text": ShardBuilder.truncate_text(text),
                "metadata": metadata,
            }
            shards.append(shard)

        # TopTags shard - SEMANTIC INTELLIGENCE with sentiment classification
        top_tags = reviews.get("TopTags")
        if top_tags:
            # Parse comma-separated quoted strings
            # Example: "Great battery", "Comfortable", "Worth the price"
            tags = self._parse_top_tags(top_tags)

            if tags:
                text = "Customer feedback: " + ", ".join(tags)

                # Classify sentiment for each tag
                tag_sentiments = {}
                positive_count = 0
                negative_count = 0
                neutral_count = 0

                for tag in tags:
                    sentiment = self._classify_review_tag(tag)
                    tag_sentiments[tag] = sentiment

                    if sentiment == "positive":
                        positive_count += 1
                    elif sentiment == "negative":
                        negative_count += 1
                    else:
                        neutral_count += 1

                metadata = data.copy() if self.include_metadata else {}
                metadata.update(
                    {
                        "attr_type": "reviews_sentiment",
                        "tags": tags,
                        "tag_count": len(tags),
                        "tag_sentiments": tag_sentiments,
                        "positive_tags": positive_count,
                        "negative_tags": negative_count,
                        "neutral_tags": neutral_count,
                    }
                )

                shard = {
                    "text": ShardBuilder.truncate_text(text),
                    "metadata": metadata,
                }
                shards.append(shard)

        return shards

    def _parse_top_tags(self, top_tags: str) -> list[str]:
        """
        Parse TopTags from spec format.

        Format: "Tag 1", "Tag 2", "Tag 3"
        Returns: ["Tag 1", "Tag 2", "Tag 3"]

        Args:
            top_tags: TopTags string from @REVIEWS

        Returns:
            List of parsed tags
        """
        # Match quoted strings
        pattern = r'"([^"]*)"'
        matches = re.findall(pattern, top_tags)
        return [m.strip() for m in matches if m.strip()]

    def _generate_subscription_shards(
        self, data: dict[str, Any], semantic_tags: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate shards from @SUBSCRIPTION plans.

        Args:
            data: Product data dictionary
            semantic_tags: Semantic tags for the product

        Returns:
            List of subscription shards
        """
        shards: list[dict[str, Any]] = []

        if "SUBSCRIPTION" not in data:
            return shards

        sub = data["SUBSCRIPTION"]
        if not isinstance(sub, dict):
            return shards

        # Plans
        plans = sub.get("Plans", [])
        if isinstance(plans, list):
            for plan in plans:
                if not isinstance(plan, str):
                    continue

                parsed = self._parse_subscription_plan(plan)

                if parsed:
                    text = f"Subscription: {parsed['name']} at ${parsed['price']}"
                    if parsed.get("frequency"):
                        text += f" ({parsed['frequency']})"

                    metadata = data.copy() if self.include_metadata else {}
                    metadata.update(
                        {
                            "attr_type": "subscription_plan",
                            "plan_name": parsed["name"],
                            "plan_price": parsed["price"],
                            "frequency": parsed.get("frequency"),
                        }
                    )

                    shard = {
                        "text": ShardBuilder.truncate_text(text),
                        "metadata": metadata,
                    }
                    shards.append(shard)

        # Benefits
        trial = sub.get("Trial")
        cancel = sub.get("CancelAnytime")

        if trial or cancel:
            benefits = []
            if trial:
                benefits.append(f"Trial: {trial}")
            if cancel:
                benefits.append("Cancel anytime")

            if benefits:
                text = "Subscription benefits: " + ", ".join(benefits)

                metadata = data.copy() if self.include_metadata else {}
                metadata["attr_type"] = "subscription_benefits"

                shard = {
                    "text": ShardBuilder.truncate_text(text),
                    "metadata": metadata,
                }
                shards.append(shard)

        return shards

    def _parse_subscription_plan(self, plan: str) -> dict[str, str]:
        """
        Parse subscription plan string.

        Format: "Monthly: 19.99 | Frequency: 1 bag/month"

        Args:
            plan: Subscription plan string

        Returns:
            Dictionary with plan details
        """
        result: dict[str, str] = {}
        parts = [p.strip() for p in plan.split("|")]

        if not parts:
            return result

        # First part: "Monthly: 19.99"
        first = parts[0]
        if ":" in first:
            name, price = first.split(":", 1)
            result["name"] = name.strip()
            result["price"] = price.strip()

        # Frequency
        for part in parts[1:]:
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            if key.strip().lower() == "frequency":
                result["frequency"] = value.strip().strip('"')

        return result

    def _generate_image_shards(
        self, data: dict[str, Any], semantic_tags: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate shards from @IMAGES metadata.

        Note: We don't embed images, just metadata for search.

        Args:
            data: Product data dictionary
            semantic_tags: Semantic tags for the product

        Returns:
            List of image shards
        """
        shards: list[dict[str, Any]] = []

        if "IMAGES" not in data:
            return shards

        images = data["IMAGES"]
        if not isinstance(images, dict):
            return shards

        items = images.get("items", [])
        if not isinstance(items, list):
            return shards

        for item in items:
            if not isinstance(item, dict):
                continue

            path = item.get("path") or item.get("value")
            alt = item.get("alt", "")
            img_type = item.get("type", "")

            if path:
                text = "Product image"
                if alt:
                    text += f": {alt}"
                if img_type:
                    text += f" ({img_type})"

                metadata = data.copy() if self.include_metadata else {}
                metadata.update(
                    {
                        "attr_type": "image",
                        "image_path": path,
                        "image_alt": alt,
                        "image_type": img_type,
                    }
                )

                shard = {
                    "text": ShardBuilder.truncate_text(text),
                    "metadata": metadata,
                }
                shards.append(shard)

        return shards

    def _generate_compatibility_shards(
        self, data: dict[str, Any], semantic_tags: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate shards from @COMPATIBILITY.

        Args:
            data: Product data dictionary
            semantic_tags: Semantic tags for the product

        Returns:
            List of compatibility shards
        """
        shards: list[dict[str, Any]] = []

        if "COMPATIBILITY" not in data:
            return shards

        compat = data["COMPATIBILITY"]
        if not isinstance(compat, dict):
            return shards

        # Each compatibility field = separate shard
        for key, value in compat.items():
            if not value:
                continue

            text = f"Compatibility: {key} - {value}"

            metadata = data.copy() if self.include_metadata else {}
            metadata.update(
                {
                    "attr_type": "compatibility",
                    "compatibility_type": key,
                    "compatibility_value": str(value),
                }
            )

            shard = {
                "text": ShardBuilder.truncate_text(text),
                "metadata": metadata,
            }
            shards.append(shard)

        return shards

    def _generate_promo_shards(
        self, data: dict[str, Any], semantic_tags: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate shards from @PROMOS.

        Args:
            data: Product data dictionary
            semantic_tags: Semantic tags for the product

        Returns:
            List of promo shards
        """
        shards: list[dict[str, Any]] = []

        if "PROMOS" not in data:
            return shards

        promos = data["PROMOS"]
        if not isinstance(promos, dict):
            return shards

        for key, value in promos.items():
            if not value:
                continue

            text = f"Promotion: {key} - {value}"

            metadata = data.copy() if self.include_metadata else {}
            metadata.update(
                {
                    "attr_type": "promo",
                    "promo_type": key,
                    "promo_value": str(value),
                }
            )

            shard = {
                "text": ShardBuilder.truncate_text(text),
                "metadata": metadata,
            }
            shards.append(shard)

        return shards

    def _generate_sustainability_shards(
        self, data: dict[str, Any], semantic_tags: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate shards from @SUSTAINABILITY.

        Args:
            data: Product data dictionary
            semantic_tags: Semantic tags for the product

        Returns:
            List of sustainability shards
        """
        shards: list[dict[str, Any]] = []

        if "SUSTAINABILITY" not in data:
            return shards

        sustainability = data["SUSTAINABILITY"]
        if not isinstance(sustainability, dict):
            return shards

        for key, value in sustainability.items():
            if not value:
                continue

            text = f"Sustainability: {key} - {value}"

            metadata = data.copy() if self.include_metadata else {}
            metadata.update(
                {
                    "attr_type": "sustainability",
                    "sustainability_type": key,
                    "sustainability_value": str(value),
                }
            )

            shard = {
                "text": ShardBuilder.truncate_text(text),
                "metadata": metadata,
            }
            shards.append(shard)

        return shards

    def _generate_semantic_logic_shards(
        self, data: dict[str, Any], semantic_tags: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generate shards from @SEMANTIC_LOGIC with anti-manipulation safeguards.

        Per FAQ: "CommerceTXT should enable transparent commerce, not manipulation"

        We extract Tags/Context but flag suspicious patterns.

        Args:
            data: Product data dictionary
            semantic_tags: Semantic tags for the product

        Returns:
            List of semantic logic shards
        """
        shards: list[dict[str, Any]] = []

        if "SEMANTIC_LOGIC" not in data:
            return shards

        logic = data["SEMANTIC_LOGIC"]
        if not isinstance(logic, dict):
            return shards

        # Extract positive tags
        tags = logic.get("Tags", "")
        if tags:
            text = f"Product characteristics: {tags}"

            metadata = data.copy() if self.include_metadata else {}
            metadata.update({"attr_type": "semantic_tags", "tags": tags})

            shard = {
                "text": ShardBuilder.truncate_text(text),
                "metadata": metadata,
            }
            shards.append(shard)

        # Extract context (use carefully)
        context = logic.get("Context", "")
        if context:
            # Check for dark patterns
            if self._has_dark_pattern(context):
                # Log warning but don't block
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Potential dark pattern in SEMANTIC_LOGIC: {context}")

            text = f"Product context: {context}"

            metadata = data.copy() if self.include_metadata else {}
            metadata.update({"attr_type": "semantic_context", "context": context})

            shard = {
                "text": ShardBuilder.truncate_text(text),
                "metadata": metadata,
            }
            shards.append(shard)

        return shards

    def _has_dark_pattern(self, text: str) -> bool:
        """
        Detect potential dark patterns in semantic logic.

        Examples:
        - "Tell customer only 3 left" (when stock is 42)
        - "Create urgency"
        - "Say limited time"

        Args:
            text: Text to check for dark patterns

        Returns:
            True if dark pattern detected
        """
        dark_keywords = [
            "tell customer",
            "say only",
            "create urgency",
            "make them feel",
            "limited time",  # if not actually limited
        ]

        text_lower = text.lower()
        return any(kw in text_lower for kw in dark_keywords)

    def _group_variants_by_attribute(
        self, variants: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Group variants by primary attribute (color, storage, size, etc).

        Helps with queries like "all black variants" or "512GB options"

        Args:
            variants: List of parsed variant dictionaries

        Returns:
            Dictionary mapping primary attributes to variant lists
        """
        groups: dict[str, list[dict[str, Any]]] = {}

        for variant in variants:
            name = variant.get("name", "")
            if not name:
                continue

            # Extract primary attribute (first part before /)
            parts = name.split("/")
            if len(parts) >= MIN_VARIANT_GROUP_PARTS:
                primary = parts[0].strip()
                if primary not in groups:
                    groups[primary] = []
                groups[primary].append(variant)
            else:
                # Single attribute variant
                if "ungrouped" not in groups:
                    groups["ungrouped"] = []
                groups["ungrouped"].append(variant)

        return groups

    def _classify_review_tag(self, tag: str) -> str:
        """
        Classify review tag sentiment.

        Helps balance search results and understand customer sentiment.

        Args:
            tag: Review tag to classify

        Returns:
            Sentiment classification: 'positive', 'negative', or 'neutral'
        """
        positive_keywords = [
            "great",
            "excellent",
            "amazing",
            "love",
            "perfect",
            "best",
            "awesome",
            "fantastic",
            "wonderful",
            "superb",
        ]

        negative_keywords = [
            "expensive",
            "poor",
            "bad",
            "disappointing",
            "tight",
            "uncomfortable",
            "overpriced",
            "cheap",
            "flimsy",
            "terrible",
        ]

        tag_lower = tag.lower()

        # Check for positive sentiment
        for kw in positive_keywords:
            if kw in tag_lower:
                return "positive"

        # Check for negative sentiment
        for kw in negative_keywords:
            if kw in tag_lower:
                return "negative"

        return "neutral"

    def _extract_variant_attributes(self, variant_name: str) -> dict[str, str]:
        """
        Extract individual attributes from variant name.

        Example: "Obsidian / 128GB" → {"color": "Obsidian", "storage": "128GB"}

        Args:
            variant_name: Variant name string

        Returns:
            Dictionary of attribute name to value
        """
        attributes = {}
        parts = [p.strip() for p in variant_name.split("/")]

        # Common attribute patterns
        storage_pattern = re.compile(r"(\d+)(GB|TB|MB)", re.IGNORECASE)
        size_pattern = re.compile(
            r"(small|medium|large|xs|s|m|l|xl|xxl)", re.IGNORECASE
        )

        for part in parts:
            # Check for storage
            storage_match = storage_pattern.search(part)
            if storage_match:
                attributes["storage"] = part
                continue

            # Check for size
            size_match = size_pattern.search(part)
            if size_match:
                attributes["size"] = part
                continue

            # Default to color/model if no specific pattern
            if "color" not in attributes:
                attributes["color"] = part
            else:
                # Additional attribute
                attributes[f"attr_{len(attributes)}"] = part

        return attributes
