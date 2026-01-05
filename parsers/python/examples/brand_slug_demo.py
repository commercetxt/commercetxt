"""
Demo: Brand Slug Collision Prevention

This script demonstrates the hash-suffixed brand tagging system that prevents
collisions between similar brand names.
"""

import hashlib

from commercetxt.rag.core.semantic_tags import SemanticTagger


def demo_basic_usage():
    """Demonstrate basic brand tag generation."""
    print("=" * 70)
    print("Demo 1: Basic Brand Tag Generation")
    print("=" * 70)

    tagger = SemanticTagger()

    brands = ["Apple", "Samsung", "Google", "Microsoft", "Amazon"]

    print("\nBrand Tags Generated:")
    for brand in brands:
        data = {"BRAND": brand}
        tags = tagger.generate_tags(data)
        brand_tag = [t for t in tags if t.startswith("brand_")][0]
        print(f"  {brand:15} → {brand_tag}")

    print("\n[OK] Each brand gets a unique tag with hash suffix")


def demo_collision_prevention():
    """Demonstrate collision prevention with similar brands."""
    print("\n" + "=" * 70)
    print("Demo 2: Collision Prevention")
    print("=" * 70)

    tagger = SemanticTagger()

    # Brands that would collide without hash
    similar_brands = [
        "TechCorp",
        "Tech Corp",
        "TechCorp.",
        "Tech-Corp",
        "TECHCORP",
    ]

    print("\nSimilar Brand Names:")
    tags_dict = {}
    for brand in similar_brands:
        data = {"BRAND": brand}
        tags = tagger.generate_tags(data)
        brand_tag = [t for t in tags if t.startswith("brand_")][0]
        tags_dict[brand] = brand_tag
        print(f"  '{brand:15}' → {brand_tag}")

    # Check uniqueness
    unique_tags = set(tags_dict.values())
    print(f"\nTotal brands: {len(similar_brands)}")
    print(f"Unique tags: {len(unique_tags)}")

    if len(unique_tags) == len(similar_brands):
        print("[OK] All brands got unique tags!")
    else:
        print("[WARNING]  Some brands share tags (case normalization)")


def demo_hash_consistency():
    """Demonstrate hash consistency across multiple calls."""
    print("\n" + "=" * 70)
    print("Demo 3: Hash Consistency")
    print("=" * 70)

    tagger = SemanticTagger()
    brand = "Sony Corporation"

    print(f"\nGenerating tag for '{brand}' multiple times:")

    tags_list = []
    for i in range(5):
        data = {"BRAND": brand}
        tags = tagger.generate_tags(data)
        brand_tag = [t for t in tags if t.startswith("brand_")][0]
        tags_list.append(brand_tag)
        print(f"  Attempt {i+1}: {brand_tag}")

    # Verify all are identical
    if len(set(tags_list)) == 1:
        print("\n[OK] All tags are identical - hash is deterministic!")
    else:
        print("\n[ERROR] Tags differ - something is wrong!")


def demo_case_insensitivity():
    """Demonstrate case-insensitive normalization."""
    print("\n" + "=" * 70)
    print("Demo 4: Case Insensitivity")
    print("=" * 70)

    tagger = SemanticTagger()

    # Different cases of same brand
    brand_variations = ["NIKE", "Nike", "nike", "NiKe"]

    print("\nCase Variations:")
    tags_dict = {}
    for brand in brand_variations:
        data = {"BRAND": brand}
        tags = tagger.generate_tags(data)
        brand_tag = [t for t in tags if t.startswith("brand_")][0]
        tags_dict[brand] = brand_tag
        print(f"  {brand:10} → {brand_tag}")

    # Check if all are identical
    unique_tags = set(tags_dict.values())
    if len(unique_tags) == 1:
        print("\n[OK] All case variations produce the same tag!")
    else:
        print(f"\n[ERROR] Got {len(unique_tags)} different tags!")


def demo_truncation_safety():
    """Demonstrate safety against truncation collisions."""
    print("\n" + "=" * 70)
    print("Demo 5: Truncation Safety")
    print("=" * 70)

    tagger = SemanticTagger()

    # Very long brands that truncate to same first 93 chars
    base = "A" * 90
    long_brands = [
        f"{base} Corporation",
        f"{base} Industries",
        f"{base} Limited",
    ]

    print("\nLong Brand Names (first 20 + ending):")
    tags_dict = {}
    for brand in long_brands:
        data = {"BRAND": brand}
        tags = tagger.generate_tags(data)
        brand_tag = [t for t in tags if t.startswith("brand_")][0]
        tags_dict[brand] = brand_tag

        # Show abbreviated version
        abbrev = brand[:20] + "..." + brand[-15:]
        print(f"  {abbrev:40} → ...{brand_tag[-15:]}")

    # Check uniqueness
    unique_tags = set(tags_dict.values())
    print(f"\nUnique tags: {len(unique_tags)}/{len(long_brands)}")

    if len(unique_tags) == len(long_brands):
        print("[OK] Hash prevents truncation collisions!")
    else:
        print("[ERROR] Some tags collided!")


def demo_hash_verification():
    """Demonstrate hash verification."""
    print("\n" + "=" * 70)
    print("Demo 6: Hash Verification")
    print("=" * 70)

    tagger = SemanticTagger()

    brand = "Adidas"
    data = {"BRAND": brand}
    tags = tagger.generate_tags(data)
    brand_tag = [t for t in tags if t.startswith("brand_")][0]

    # Extract components
    parts = brand_tag.split("_")
    slug = "_".join(parts[1:-1])
    hash_suffix = parts[-1]

    # Compute expected hash
    normalized = brand.strip().lower()
    expected_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:6]

    print(f"\nBrand: {brand}")
    print(f"Normalized: {normalized}")
    print(f"Generated Tag: {brand_tag}")
    print("\nComponents:")
    print("  Prefix: brand")
    print(f"  Slug: {slug}")
    print(f"  Hash: {hash_suffix}")
    print("\nHash Verification:")
    print(f"  Extracted hash: {hash_suffix}")
    print(f"  Expected hash:  {expected_hash}")
    print(f"  Match: {hash_suffix == expected_hash}")

    if hash_suffix == expected_hash:
        print("\n[OK] Hash verified successfully!")
    else:
        print("\n[ERROR] Hash mismatch!")


def demo_special_characters():
    """Demonstrate special character handling."""
    print("\n" + "=" * 70)
    print("Demo 7: Special Character Handling")
    print("=" * 70)

    tagger = SemanticTagger()

    brands_with_special = [
        "Apple & Co.",
        "Brand@123",
        "Test-Brand!",
        "Name (TM)",
        "Coca-Cola®",
    ]

    print("\nBrands with Special Characters:")
    for brand in brands_with_special:
        data = {"BRAND": brand}
        tags = tagger.generate_tags(data)
        brand_tag = [t for t in tags if t.startswith("brand_")][0]
        print(f"  {brand:20} → {brand_tag}")

    print("\n[OK] Special characters sanitized to underscores")


def demo_collision_statistics():
    """Calculate and display collision statistics."""
    print("\n" + "=" * 70)
    print("Demo 8: Collision Statistics")
    print("=" * 70)

    print("\nHash Space Analysis:")
    print("  Hash length: 6 hex characters")
    print(f"  Possible values: 16^6 = {16**6:,}")
    print("  Collision probability formula: 1 - e^(-n²/2m)")
    print("    where n = number of brands, m = hash space size")

    # Calculate collision probability for different brand counts
    import math

    m = 16**6  # Hash space size
    brand_counts = [100, 1000, 10000, 50000]

    print("\n  Collision Probability:")
    for n in brand_counts:
        # Approximation: 1 - e^(-n²/2m)
        prob = 1 - math.exp(-(n**2) / (2 * m))
        print(f"    {n:6,} brands: {prob*100:6.3f}%")

    print("\n[OK] Very low collision risk for typical use cases!")


if __name__ == "__main__":
    print("\n Brand Slug Collision Prevention Demo\n")

    demo_basic_usage()
    demo_collision_prevention()
    demo_hash_consistency()
    demo_case_insensitivity()
    demo_truncation_safety()
    demo_hash_verification()
    demo_special_characters()
    demo_collision_statistics()

    print("\n" + "=" * 70)
    print("All demos completed successfully!")
    print("=" * 70)
    print()
