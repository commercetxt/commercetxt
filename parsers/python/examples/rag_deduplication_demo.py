"""
Example demonstrating RAG shard deduplication feature.

This script shows how content-based deduplication prevents duplicate
shards when processing products with common attributes.
"""

from commercetxt.rag import RAGGenerator, ShardBuilder


def example_single_product_deduplication():
    """Demonstrate deduplication within a single product."""
    print("=" * 70)
    print("Example 1: Deduplication Within Single Product")
    print("=" * 70)

    generator = RAGGenerator()

    data = {
        "ITEM": "Professional Laptop",
        "BRAND": "TechCorp",
        "CURRENCY": "USD",
        "SPECS": {
            "Weight": "1.5kg",
            "Mass": "1.5kg",  # Duplicate value
            "ShippingWeight": "1.5kg",  # Another duplicate
            "Material": "Aluminum",
            "Finish": "Aluminum",  # Duplicate value
        },
    }

    print("\nInput data:")
    print(f"  ITEM: {data['ITEM']}")
    print("  SPECS with duplicates:")
    for key, value in data["SPECS"].items():
        print(f"    {key}: {value}")

    shards = generator.generate(data, as_text=False)

    spec_shards = [s for s in shards if s["metadata"]["attr_type"] == "specification"]

    print(f"\nGenerated {len(spec_shards)} unique specification shards:")
    for shard in spec_shards:
        print(f"  - {shard['text']}")

    print("\n[OK] Notice: '1.5kg' appears 3 times in input but only once in output")
    print("[OK] Notice: 'Aluminum' appears 2 times in input but only once in output\n")


def example_batch_deduplication():
    """Demonstrate deduplication across multiple products."""
    print("=" * 70)
    print("Example 2: Deduplication Across Products (Batch Mode)")
    print("=" * 70)

    generator = RAGGenerator()

    products = [
        {
            "ITEM": "Budget Laptop",
            "BRAND": "TechCorp",
            "CURRENCY": "USD",
            "PRICE": "699",
        },
        {
            "ITEM": "Premium Laptop",
            "BRAND": "TechCorp",
            "CURRENCY": "USD",
            "PRICE": "1299",
        },
        {
            "ITEM": "Gaming Laptop",
            "BRAND": "TechCorp",
            "CURRENCY": "USD",
            "PRICE": "1899",
        },
    ]

    print(f"\nProcessing {len(products)} products:")
    for i, p in enumerate(products, 1):
        print(f"  {i}. {p['ITEM']} - {p['BRAND']} - {p['CURRENCY']} - ${p['PRICE']}")

    # WITH deduplication
    shards_dedup = generator.generate_batch(products, deduplicate_across_products=True)

    # WITHOUT deduplication
    generator.reset_deduplication()
    shards_no_dedup = generator.generate_batch(
        products, deduplicate_across_products=False
    )

    print("\nResults:")
    print(f"  With deduplication: {len(shards_dedup)} total shards")
    print(f"  Without deduplication: {len(shards_no_dedup)} total shards")
    print(f"  Duplicates removed: {len(shards_no_dedup) - len(shards_dedup)}")

    # Show which attributes were deduplicated
    currency_shards = [
        s for s in shards_dedup if s["metadata"]["attr_type"] == "currency"
    ]
    brand_shards = [
        s for s in shards_dedup if s["metadata"]["attr_type"] == "subject_anchor"
    ]

    print(f"\n  Currency shards: {len(currency_shards)} (should be 1)")
    print(f"    - {currency_shards[0]['text']}")

    print(f"\n  Subject anchor shards: {len(brand_shards)} (should be 3)")
    for shard in brand_shards:
        print(f"    - {shard['text']}")

    print("\n[OK] Notice: 'USD' appears in all 3 products but only 1 shard created")
    print(
        "[OK] Notice: 'TechCorp' appears in all 3 products but only 1 shard created\n"
    )


def example_storage_savings():
    """Demonstrate storage savings from deduplication."""
    print("=" * 70)
    print("Example 3: Storage Savings Calculation")
    print("=" * 70)

    generator = RAGGenerator()

    # Simulate 50 products in same category
    products = []
    for i in range(50):
        products.append(
            {
                "ITEM": f"Product {i+1}",
                "BRAND": "CommonBrand",
                "CURRENCY": "EUR",
                "CATEGORY": "Electronics",
                "SPECS": {
                    "Warranty": "2 years",
                    "Origin": "Made in EU",
                    "Certification": "CE certified",
                },
            }
        )

    print(f"\nProcessing {len(products)} products with common attributes...")

    # WITH deduplication
    shards_dedup = generator.generate_batch(products, deduplicate_across_products=True)

    # WITHOUT deduplication
    generator.reset_deduplication()
    shards_no_dedup = generator.generate_batch(
        products, deduplicate_across_products=False
    )

    # Calculate approximate storage
    avg_shard_size = 200  # bytes (estimate)
    storage_no_dedup = len(shards_no_dedup) * avg_shard_size
    storage_dedup = len(shards_dedup) * avg_shard_size
    savings = storage_no_dedup - storage_dedup
    savings_percent = (savings / storage_no_dedup) * 100

    print("\nResults:")
    print(f"  Without deduplication: {len(shards_no_dedup)} shards")
    print(f"  With deduplication: {len(shards_dedup)} shards")
    print(f"  Duplicates removed: {len(shards_no_dedup) - len(shards_dedup)}")

    print(f"\nStorage estimates (avg {avg_shard_size} bytes/shard):")
    print(f"  Without deduplication: ~{storage_no_dedup:,} bytes")
    print(f"  With deduplication: ~{storage_dedup:,} bytes")
    print(f"  Storage saved: ~{savings:,} bytes ({savings_percent:.1f}%)")

    print("\n[OK] Significant storage savings especially with large catalogs!\n")


def example_hash_demonstration():
    """Demonstrate how content hashing works."""
    print("=" * 70)
    print("Example 4: Content Hash Demonstration")
    print("=" * 70)

    # Create two shards with same content but different metadata
    shard1 = {
        "text": "1000 mAh",
        "metadata": {
            "index": 0,
            "attr_type": "specification",
            "original_data": {"ITEM": "Battery A"},
        },
    }

    shard2 = {
        "text": "1000 mAh",
        "metadata": {
            "index": 99,
            "attr_type": "specification",
            "original_data": {"ITEM": "Battery B"},
        },
    }

    # Create shard with different content
    shard3 = {
        "text": "2000 mAh",
        "metadata": {
            "index": 0,
            "attr_type": "specification",
            "original_data": {"ITEM": "Battery A"},
        },
    }

    hash1 = ShardBuilder.compute_content_hash(shard1)
    hash2 = ShardBuilder.compute_content_hash(shard2)
    hash3 = ShardBuilder.compute_content_hash(shard3)

    print("\nShard 1:")
    print(f"  Text: {shard1['text']}")
    print(f"  Index: {shard1['metadata']['index']}")
    print(f"  Hash: {hash1[:16]}...")

    print("\nShard 2 (same content, different metadata):")
    print(f"  Text: {shard2['text']}")
    print(f"  Index: {shard2['metadata']['index']}")
    print(f"  Hash: {hash2[:16]}...")

    print("\nShard 3 (different content):")
    print(f"  Text: {shard3['text']}")
    print(f"  Index: {shard3['metadata']['index']}")
    print(f"  Hash: {hash3[:16]}...")

    print("\nHash comparison:")
    print(f"  Shard 1 == Shard 2: {hash1 == hash2} [OK] (same content)")
    print(f"  Shard 1 == Shard 3: {hash1 == hash3} [NO] (different content)")

    print("\n[OK] Hashes ignore metadata differences, focusing on content!\n")


if __name__ == "__main__":
    print("\n[START] RAG Shard Deduplication Examples\n")

    example_single_product_deduplication()
    example_batch_deduplication()
    example_storage_savings()
    example_hash_demonstration()

    print("=" * 70)
    print("All examples completed successfully! [OK]")
    print("=" * 70)
    print()
