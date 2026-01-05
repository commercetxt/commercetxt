"""
CommerceTXT RAG Demo - Working with Real Data

This example shows how to use the RAG system with actual CommerceTXT files.
Uses the Google Store example data from the spec.

Requirements:
- Core: pip install sentence-transformers faiss-cpu numpy
- Optional: pip install aiosqlite (for caching)
"""

import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """
    Demonstrate RAG ingestion and search with CommerceTXT data.
    """
    print("=" * 70)
    print("CommerceTXT RAG System - Real Data Demo")
    print("=" * 70)

    # Step 1: Parse a real commerce.txt file
    print("\n[Step 1] Parsing commerce.txt file...")

    try:
        from commercetxt import parse_file
    except ImportError:
        print("✗ Error: commercetxt parser not found")
        print("  Make sure you're in the right directory")
        return

    # Use the Pixel 9 Pro example
    # Auto-detect the correct path based on where script is run from
    current_dir = Path(__file__).parent.absolute()

    # Try different possible locations
    possible_paths = [
        # From parsers/python/examples/
        current_dir
        / ".."
        / ".."
        / ".."
        / "examples"
        / "google-store"
        / "products"
        / "pixel-9-pro.txt",
        # From parsers/python/
        current_dir
        / ".."
        / ".."
        / "examples"
        / "google-store"
        / "products"
        / "pixel-9-pro.txt",
        # From root
        current_dir / "examples" / "google-store" / "products" / "pixel-9-pro.txt",
        # Relative from current working directory
        Path.cwd() / "examples" / "google-store" / "products" / "pixel-9-pro.txt",
        Path.cwd()
        / ".."
        / "examples"
        / "google-store"
        / "products"
        / "pixel-9-pro.txt",
    ]

    product_file = None
    for path in possible_paths:
        resolved = path.resolve()
        if resolved.exists():
            product_file = resolved
            break

    if product_file is None:
        print("✗ Error: Example file not found")
        print("  Tried paths:")
        for p in possible_paths:
            print(f"    - {p.resolve()}")
        print("\n  The examples/ directory should be at the repository root.")
        print(f"  Current script location: {current_dir}")
        print(f"  Current working dir: {Path.cwd()}")
        return

    # Parse the file
    parsed = parse_file(str(product_file))

    if parsed.errors:
        print(f"⚠ Parsing completed with {len(parsed.errors)} warnings")
        for err in parsed.errors[:3]:  # Show first 3
            print(f"  - {err}")

    product_name = parsed.directives.get("PRODUCT", {}).get("Name", "Unknown")
    print(f"[OK] Parsed: {product_name}")
    print(f"  Sections found: {list(parsed.directives.keys())}")

    # Step 2: Initialize RAG pipeline
    print("\n[Step 2] Initializing RAG pipeline...")

    try:
        from commercetxt.rag import RAGPipeline
    except ImportError as e:
        print(f"[ERROR] Error importing RAG: {e}")
        print("\n  Install core dependencies:")
        print("  pip install sentence-transformers faiss-cpu numpy")
        return

    pipeline = RAGPipeline()
    print("[OK] Pipeline initialized")

    # Step 3: Ingest the product
    print("\n[Step 3] Ingesting product into RAG...")

    try:
        # The pipeline expects data in a specific format
        # We need to transform the parsed CommerceTXT data
        rag_data = transform_to_rag_format(parsed.directives)

        count = pipeline.ingest(rag_data, namespace="google-store")
        print(f"[OK] Ingested {count} vector shards")

    except Exception as e:
        print(f"[ERROR] Ingestion failed: {e}")
        logger.exception("Ingestion error")
        return

    # Step 4: Search
    print("\n[Step 4] Searching for products...")

    queries = [
        "smartphone with good camera",
        "phone with long battery life",
        "device with wireless charging",
    ]

    for query in queries:
        print(f"\n  Query: '{query}'")
        results = pipeline.search(query, top_k=3, namespace="google-store")

        if results:
            print(f"  [OK] Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                text = result.get("text", "")[:80]
                score = result.get("score", 0)
                print(f"    {i}. [{score:.3f}] {text}...")
        else:
            print("  [!!] No results found")

    print("\n" + "=" * 70)
    print("[OK] Demo complete!")
    print("=" * 70)


def transform_to_rag_format(parsed_data: dict) -> dict:
    """
    Transform CommerceTXT parsed data to RAG-friendly format.

    Since the generator now handles all @SECTIONS natively,
    we can pass the parsed directives directly with minimal transformation.

    Args:
        parsed_data: Output from commercetxt.parse_file().directives

    Returns:
        Dictionary suitable for RAG ingestion
    """
    # The new generator handles nested sections natively,
    # so we pass the data as-is with just flat top-level fields extracted

    result = parsed_data.copy()

    # Extract flat fields for compatibility with old code
    if "PRODUCT" in parsed_data:
        product = parsed_data["PRODUCT"]
        result["ITEM"] = product.get("Name", "Unknown Product")
        result["BRAND"] = product.get("Brand", "")
        result["SKU"] = product.get("SKU", "")
        result["DESCRIPTION"] = product.get("Description", "")
        result["GTIN"] = product.get("GTIN", "")

    if "OFFER" in parsed_data:
        offer = parsed_data["OFFER"]
        result["PRICE"] = offer.get("Price", "")
        result["CURRENCY"] = offer.get("Currency", "USD")
        result["AVAILABILITY"] = offer.get("Availability", "")

    if "INVENTORY" in parsed_data:
        inventory = parsed_data["INVENTORY"]
        result["STOCK"] = inventory.get("Stock", "")
        result["STOCK_STATUS"] = inventory.get("StockStatus", "")

    # All other sections (@VARIANTS, @REVIEWS, @IMAGES, @COMPATIBILITY,
    # @PROMOS, @SUSTAINABILITY, @SEMANTIC_LOGIC) are kept as-is
    # The generator now handles them natively!

    return result


if __name__ == "__main__":
    main()
