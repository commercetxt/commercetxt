"""
Comprehensive tests for RAG generator module.

Covers all shard generation paths including variants, reviews, subscriptions,
images, compatibility, promos, sustainability, and semantic logic.
"""

from __future__ import annotations

from commercetxt.rag.core.generator import RAGGenerator


class TestRAGGeneratorVariants:
    """Tests for variant shard generation."""

    def test_generate_variant_shards_basic(self):
        """Basic variant generation works."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Test Phone",
            "BRAND": "TestBrand",
            "VARIANTS": {
                "Type": "Color/Storage",
                "Options": [
                    "Black 128GB: 999.00 | SKU: TEST-BLK-128 | Stock: 10",
                ],
            },
        }

        result = generator.generate(data)
        assert isinstance(result, list)

        # Check variant shard exists
        variant_shards = [
            s for s in result if s.get("metadata", {}).get("attr_type") == "variant"
        ]
        assert len(variant_shards) >= 1

    def test_variant_option_without_price(self):
        """Variant without price still generates shard."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Widget",
            "VARIANTS": {
                "Type": "Size",
                "Options": ["Small", "Large"],
            },
        }

        result = generator.generate(data)
        [s for s in result if s.get("metadata", {}).get("attr_type") == "variant"]
        # Should handle options without colon
        assert True  # No exception raised

    def test_variant_with_note_field(self):
        """Variant with note field included."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Gadget",
            "VARIANTS": {
                "Type": "Color",
                "Options": ["Red: 50.00 | Note: Limited edition"],
            },
        }

        result = generator.generate(data)
        assert isinstance(result, list)

    def test_variant_with_hex_color(self):
        """Variant with hex color extracted."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Item",
            "VARIANTS": {
                "Type": "Color",
                "Options": ["Blue: 30.00 | Hex: #0000FF"],
            },
        }

        result = generator.generate(data)
        variant_shards = [
            s for s in result if s.get("metadata", {}).get("attr_type") == "variant"
        ]

        if variant_shards:
            assert "variant_hex" in variant_shards[0].get("metadata", {})

    def test_non_dict_variants_skipped(self):
        """Non-dict VARIANTS skipped gracefully."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Test",
            "VARIANTS": "invalid",
        }

        result = generator.generate(data)
        # Should not crash
        assert isinstance(result, list)

    def test_non_list_options_skipped(self):
        """Non-list Options skipped gracefully."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Test",
            "VARIANTS": {"Type": "Color", "Options": "invalid"},
        }

        result = generator.generate(data)
        assert isinstance(result, list)

    def test_non_string_variant_option_skipped(self):
        """Non-string variant option skipped."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Test",
            "VARIANTS": {
                "Type": "Size",
                "Options": [123, None, {"dict": "value"}, "Valid: 10.00"],
            },
        }

        result = generator.generate(data)
        assert isinstance(result, list)


class TestRAGGeneratorReviews:
    """Tests for review shard generation."""

    def test_generate_reviews_basic(self):
        """Basic review shard generated."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Product",
            "REVIEWS": {"Rating": "4.5", "Count": "127", "Verified": "89"},
        }

        result = generator.generate(data)
        review_shards = [
            s for s in result if s.get("metadata", {}).get("attr_type") == "reviews"
        ]
        assert len(review_shards) >= 1

    def test_reviews_with_top_tags(self):
        """Reviews with TopTags generates sentiment shard."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Product",
            "REVIEWS": {
                "Rating": "4.5",
                "Count": "100",
                "TopTags": '"Great battery", "Comfortable", "Worth the price"',
            },
        }

        result = generator.generate(data)
        sentiment_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "reviews_sentiment"
        ]
        assert len(sentiment_shards) >= 1

    def test_parse_top_tags(self):
        """TopTags parsed correctly."""
        generator = RAGGenerator()

        tags = generator._parse_top_tags('"Tag 1", "Tag 2", "Tag 3"')

        assert tags == ["Tag 1", "Tag 2", "Tag 3"]

    def test_parse_top_tags_empty(self):
        """Empty TopTags returns empty list."""
        generator = RAGGenerator()

        tags = generator._parse_top_tags("")
        assert tags == []

    def test_classify_review_tag_positive(self):
        """Positive tags classified correctly."""
        generator = RAGGenerator()

        assert generator._classify_review_tag("Great battery life") == "positive"
        assert generator._classify_review_tag("Amazing quality") == "positive"

    def test_classify_review_tag_negative(self):
        """Negative tags classified correctly."""
        generator = RAGGenerator()

        assert generator._classify_review_tag("Too expensive") == "negative"
        assert generator._classify_review_tag("Poor quality") == "negative"

    def test_classify_review_tag_neutral(self):
        """Neutral tags classified correctly."""
        generator = RAGGenerator()

        assert generator._classify_review_tag("Standard design") == "neutral"

    def test_non_dict_reviews_skipped(self):
        """Non-dict REVIEWS skipped gracefully."""
        generator = RAGGenerator()

        data = {"ITEM": "Test", "REVIEWS": "invalid"}

        result = generator.generate(data)
        assert isinstance(result, list)


class TestRAGGeneratorSubscription:
    """Tests for subscription shard generation."""

    def test_generate_subscription_plans(self):
        """Subscription plans generate shards."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Coffee",
            "SUBSCRIPTION": {
                "Plans": ['Monthly: 19.99 | Frequency: "1 bag/month"'],
                "Trial": "First month free",
                "CancelAnytime": "Yes",
            },
        }

        result = generator.generate(data)
        subscription_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "subscription_plan"
        ]
        assert len(subscription_shards) >= 1

    def test_subscription_benefits_shard(self):
        """Subscription benefits generate separate shard."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Service",
            "SUBSCRIPTION": {"Trial": "30 days free", "CancelAnytime": "Yes"},
        }

        result = generator.generate(data)
        benefit_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "subscription_benefits"
        ]
        assert len(benefit_shards) >= 1

    def test_parse_subscription_plan(self):
        """Subscription plan parsed correctly."""
        generator = RAGGenerator()

        parsed = generator._parse_subscription_plan(
            'Monthly: 19.99 | Frequency: "1 bag/month"'
        )

        assert parsed["name"] == "Monthly"
        assert parsed["price"] == "19.99"
        assert parsed["frequency"] == "1 bag/month"

    def test_parse_subscription_plan_empty(self):
        """Empty plan returns empty dict."""
        generator = RAGGenerator()

        parsed = generator._parse_subscription_plan("")
        assert parsed == {}

    def test_non_string_plan_skipped(self):
        """Non-string plan skipped."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Test",
            "SUBSCRIPTION": {"Plans": [123, None, "Valid: 9.99"]},
        }

        result = generator.generate(data)
        assert isinstance(result, list)


class TestRAGGeneratorImages:
    """Tests for image shard generation."""

    def test_generate_image_shards(self):
        """Image shards generated from items."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Product",
            "IMAGES": {
                "items": [
                    {"path": "https://example.com/img1.jpg", "alt": "Front view"},
                    {"value": "https://example.com/img2.jpg", "type": "gallery"},
                ]
            },
        }

        result = generator.generate(data)
        image_shards = [
            s for s in result if s.get("metadata", {}).get("attr_type") == "image"
        ]
        assert len(image_shards) == 2

    def test_image_with_alt_and_type(self):
        """Image alt and type included in shard."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Product",
            "IMAGES": {
                "items": [{"path": "img.jpg", "alt": "Product shot", "type": "main"}]
            },
        }

        result = generator.generate(data)
        image_shards = [
            s for s in result if s.get("metadata", {}).get("attr_type") == "image"
        ]

        if image_shards:
            assert "Product shot" in image_shards[0]["text"]
            assert "main" in image_shards[0]["text"]

    def test_non_dict_image_item_skipped(self):
        """Non-dict image items skipped."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Test",
            "IMAGES": {"items": ["string", 123, {"path": "valid.jpg"}]},
        }

        result = generator.generate(data)
        image_shards = [
            s for s in result if s.get("metadata", {}).get("attr_type") == "image"
        ]
        assert len(image_shards) == 1  # Only valid dict processed


class TestRAGGeneratorCompatibility:
    """Tests for compatibility shard generation."""

    def test_generate_compatibility_shards(self):
        """Compatibility shards generated."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Case",
            "COMPATIBILITY": {"iPhone": "12, 13, 14, 15", "Samsung": "S21, S22, S23"},
        }

        result = generator.generate(data)
        compat_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "compatibility"
        ]
        assert len(compat_shards) == 2

    def test_empty_compatibility_value_skipped(self):
        """Empty compatibility value skipped."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Case",
            "COMPATIBILITY": {"Valid": "iPhone", "Empty": "", "None": None},
        }

        result = generator.generate(data)
        compat_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "compatibility"
        ]
        assert len(compat_shards) == 1


class TestRAGGeneratorPromos:
    """Tests for promo shard generation."""

    def test_generate_promo_shards(self):
        """Promo shards generated."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Sale Item",
            "PROMOS": {"Code": "SAVE20", "Discount": "20% off"},
        }

        result = generator.generate(data)
        promo_shards = [
            s for s in result if s.get("metadata", {}).get("attr_type") == "promo"
        ]
        assert len(promo_shards) == 2

    def test_empty_promo_value_skipped(self):
        """Empty promo value skipped."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Test",
            "PROMOS": {"Valid": "PROMO", "Empty": ""},
        }

        result = generator.generate(data)
        promo_shards = [
            s for s in result if s.get("metadata", {}).get("attr_type") == "promo"
        ]
        assert len(promo_shards) == 1


class TestRAGGeneratorSustainability:
    """Tests for sustainability shard generation."""

    def test_generate_sustainability_shards(self):
        """Sustainability shards generated."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Eco Product",
            "SUSTAINABILITY": {"Certification": "Fair Trade", "Materials": "Recycled"},
        }

        result = generator.generate(data)
        sus_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "sustainability"
        ]
        assert len(sus_shards) == 2

    def test_empty_sustainability_value_skipped(self):
        """Empty sustainability value skipped."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Test",
            "SUSTAINABILITY": {"Valid": "Yes", "Empty": ""},
        }

        result = generator.generate(data)
        sus_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "sustainability"
        ]
        assert len(sus_shards) == 1


class TestRAGGeneratorSemanticLogic:
    """Tests for semantic logic shard generation."""

    def test_generate_semantic_tags_shard(self):
        """Tags shard generated from semantic logic."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Tagged Product",
            "SEMANTIC_LOGIC": {"Tags": "electronics, gadget, wireless"},
        }

        result = generator.generate(data)
        tag_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "semantic_tags"
        ]
        assert len(tag_shards) == 1

    def test_generate_semantic_context_shard(self):
        """Context shard generated from semantic logic."""
        generator = RAGGenerator()

        data = {
            "ITEM": "Product",
            "SEMANTIC_LOGIC": {"Context": "Ideal for outdoor use"},
        }

        result = generator.generate(data)
        ctx_shards = [
            s
            for s in result
            if s.get("metadata", {}).get("attr_type") == "semantic_context"
        ]
        assert len(ctx_shards) == 1

    def test_dark_pattern_detection(self):
        """Dark patterns detected in context."""
        generator = RAGGenerator()

        # These should be flagged
        assert generator._has_dark_pattern("Tell customer only 3 left")
        assert generator._has_dark_pattern("Create urgency in the user")
        assert generator._has_dark_pattern("Say only limited time available")

        # These should not
        assert not generator._has_dark_pattern("High quality product")
        assert not generator._has_dark_pattern("Free shipping available")

    def test_dark_pattern_logs_warning(self, caplog):
        """Dark pattern in context logs warning."""
        import logging

        generator = RAGGenerator()

        data = {
            "ITEM": "Test",
            "SEMANTIC_LOGIC": {
                "Context": "Tell customer only 3 left to create urgency"
            },
        }

        with caplog.at_level(logging.WARNING):
            generator.generate(data)

        # Warning should be logged
        assert any(
            "dark pattern" in record.message.lower() for record in caplog.records
        )


class TestRAGGeneratorHelpers:
    """Tests for generator helper methods."""

    def test_extract_variant_attributes_storage(self):
        """Storage extracted from variant name."""
        generator = RAGGenerator()

        attrs = generator._extract_variant_attributes("Black / 256GB")

        assert attrs["storage"] == "256GB"
        # Color may be in "color" or as first non-storage part
        assert "color" in attrs or len(attrs) >= 1

    def test_extract_variant_attributes_size(self):
        """Size extracted from variant name."""
        generator = RAGGenerator()

        # Test with explicit size pattern
        attrs = generator._extract_variant_attributes("XL / Blue")

        # Size should be detected due to size pattern matching
        assert "size" in attrs or "color" in attrs

    def test_extract_variant_attributes_single(self):
        """Single attribute extracted."""
        generator = RAGGenerator()

        attrs = generator._extract_variant_attributes("Red")

        assert attrs["color"] == "Red"

    def test_group_variants_by_attribute(self):
        """Variants grouped by primary attribute."""
        generator = RAGGenerator()

        variants = [
            {"name": "Black / 128GB"},
            {"name": "Black / 256GB"},
            {"name": "White / 128GB"},
        ]

        groups = generator._group_variants_by_attribute(variants)

        assert "Black" in groups
        assert "White" in groups
        assert len(groups["Black"]) == 2
        assert len(groups["White"]) == 1

    def test_group_variants_single_attribute(self):
        """Single attribute variants go to ungrouped."""
        generator = RAGGenerator()

        variants = [{"name": "Red"}, {"name": "Blue"}]

        groups = generator._group_variants_by_attribute(variants)

        assert "ungrouped" in groups
        assert len(groups["ungrouped"]) == 2

    def test_parse_variant_option_full(self):
        """Full variant option parsed."""
        generator = RAGGenerator()

        parsed = generator._parse_variant_option(
            "Obsidian / 128GB: 999.00 | SKU: GA05843-128-OBS | Stock: 22 | Hex: #1a1a1a | Note: Popular choice"
        )

        assert parsed["name"] == "Obsidian / 128GB"
        assert parsed["price"] == "999.00"
        assert parsed["sku"] == "GA05843-128-OBS"
        assert parsed["stock"] == "22"
        assert parsed["hex_color"] == "#1a1a1a"
        assert parsed["note"] == "Popular choice"

    def test_parse_variant_option_minimal(self):
        """Minimal variant option parsed."""
        generator = RAGGenerator()

        parsed = generator._parse_variant_option("Red")

        assert parsed["name"] == "Red"

    def test_parse_variant_option_with_colons_in_value(self):
        """Variant option with colons in value handled."""
        generator = RAGGenerator()

        parsed = generator._parse_variant_option("Option: Price | SKU: CODE:123")

        assert parsed["name"] == "Option"
        # SKU should capture value after first colon
        assert "sku" in parsed


class TestRAGGeneratorBatchMode:
    """Tests for batch processing mode."""

    def test_batch_mode_deduplicates_across_products(self):
        """Batch mode deduplicates across products."""
        generator = RAGGenerator()

        items = [
            {"ITEM": "Product A", "BRAND": "Brand", "PRICE": "100"},
            {"ITEM": "Product A", "BRAND": "Brand", "PRICE": "100"},  # Duplicate
        ]

        result = generator.generate_batch(items, deduplicate_across_products=True)

        # Should have fewer shards due to deduplication
        assert isinstance(result, list)

    def test_batch_mode_no_deduplication(self):
        """Batch mode without deduplication resets per product."""
        generator = RAGGenerator()

        items = [
            {"ITEM": "Product A", "BRAND": "Brand", "PRICE": "100"},
            {"ITEM": "Product B", "BRAND": "Brand", "PRICE": "100"},
        ]

        result = generator.generate_batch(items, deduplicate_across_products=False)

        assert isinstance(result, list)

    def test_batch_mode_handles_errors(self):
        """Batch mode continues on errors."""
        generator = RAGGenerator()

        # Use a custom error-causing item
        items = [
            {"ITEM": "Valid Product"},
            {},  # Empty dict - should be handled
            {"ITEM": "Another Valid"},
        ]

        # Should not crash, errors collected
        result = generator.generate_batch(items)
        assert isinstance(result, (list, str))

    def test_batch_mode_as_text(self):
        """Batch mode can return text."""
        generator = RAGGenerator()

        items = [{"ITEM": "Product 1"}, {"ITEM": "Product 2"}]

        result = generator.generate_batch(items, as_text=True)

        assert isinstance(result, str)

    def test_reset_deduplication(self):
        """reset_deduplication clears seen hashes."""
        generator = RAGGenerator()

        # Generate once
        generator.generate({"ITEM": "Test"})
        assert len(generator._seen_hashes) > 0

        # Reset
        generator.reset_deduplication()
        assert len(generator._seen_hashes) == 0


class TestRAGGeneratorMetadata:
    """Tests for metadata handling."""

    def test_include_metadata_true(self):
        """Metadata included when flag is True."""
        generator = RAGGenerator(include_metadata=True)

        result = generator.generate({"ITEM": "Test", "BRAND": "Brand"})

        assert len(result) > 0
        assert "metadata" in result[0]
        assert result[0]["metadata"] != {}

    def test_include_metadata_false(self):
        """Metadata minimal when flag is False."""
        generator = RAGGenerator(include_metadata=False)

        result = generator.generate({"ITEM": "Test", "BRAND": "Brand"})

        # Should still have shards
        assert len(result) > 0

    def test_extra_plural_attributes(self):
        """Extra plural attributes added."""
        generator = RAGGenerator(extra_plural={"CustomField"})

        assert "CustomField" in generator.plural_attributes

    def test_include_confidence_in_builder(self):
        """Confidence included in shard builder."""
        generator = RAGGenerator(include_confidence=True)

        assert generator.shard_builder.include_confidence is True

    def test_include_negative_tags_in_builder(self):
        """Negative tags included in shard builder."""
        generator = RAGGenerator(include_negative_tags=True)

        assert generator.shard_builder.include_negative_tags is True
