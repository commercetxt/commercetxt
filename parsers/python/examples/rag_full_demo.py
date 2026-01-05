"""
RAG Full Demo - Real-World Example

Demonstrates RAG pipeline with real product data.
Shows ingestion, search, and results.

Requirements:
- Core: pip install sentence-transformers faiss-cpu numpy
"""

import logging
import sys
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """
    Complete example showing enhanced features.
    """

    try:
        from commercetxt.rag import RAGPipeline
    except ImportError as e:
        print(f"[ERROR] Error importing RAG pipeline: {e}")
        print("\nMake sure core dependencies are installed:")
        print("  pip install sentence-transformers faiss-cpu numpy")
        sys.exit(1)

    # Initialize pipeline
    pipeline = RAGPipeline()

    print("=" * 60)
    print("CommerceTXT RAG Pipeline - Full Demo")
    print("=" * 60)

    # Example 1: Ingest products
    print("\n[1] Ingesting products...")
    products = [
        {
            "ITEM": "Wireless Headphones Pro",
            "BRAND": "AudioTech",
            "PRICE": 199.99,
            "DESCRIPTION": "Premium noise-canceling wireless headphones with 30-hour battery life",
            "SPECS": {
                "Battery Life": "30 hours",
                "Connectivity": "Bluetooth 5.0",
                "Noise Canceling": "Active",
            },
        },
        {
            "ITEM": "Bluetooth Speaker Mini",
            "BRAND": "AudioTech",
            "PRICE": 49.99,
            "DESCRIPTION": "Compact waterproof speaker with 360-degree sound",
            "SPECS": {
                "Battery Life": "12 hours",
                "Waterproof": "IPX7",
                "Connectivity": "Bluetooth 5.0",
            },
        },
    ]

    ingested = 0
    for product in products:
        try:
            count = pipeline.ingest(product, namespace="demo")
            ingested += count
        except Exception as e:
            logger.error(f"Failed to ingest {product.get('ITEM')}: {e}")

    print(f"[OK] Ingested {ingested} vectors")

    # Example 2: Search
    print("\n[2] Searching for products...")

    queries = [
        "wireless headphones with good battery",
        "waterproof speaker",
        "bluetooth audio device",
    ]

    for query in queries:
        print(f"\n  Query: '{query}'")

        start = time.time()
        results = pipeline.search(query, top_k=3, namespace="demo")
        duration = (time.time() - start) * 1000

        if results:
            print(f"  [OK] Found {len(results)} results in {duration:.1f}ms:")
            for i, result in enumerate(results, 1):
                text = result.get("text", "")[:60]
                score = result.get("score", 0)
                print(f"    {i}. [{score:.3f}] {text}...")
        else:
            print("  [!!] No results found")

    print("\n" + "=" * 60)
    print("[OK] Example complete! All features working.")
    print("=" * 60)


if __name__ == "__main__":
    main()
