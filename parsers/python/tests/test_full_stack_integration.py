"""
Complex Full-Stack Integration Test for CommerceTXT.
Exercises: Fractal Inheritance, Multi-Product RAG, CLI Comparison, and Unit Normalization.
"""

import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from commercetxt.cache import parse_cached
from commercetxt.cli import main
from commercetxt.rag.container import RAGContainer
from commercetxt.rag.pipeline import RAGPipeline
from commercetxt.resolver import CommerceTXTResolver
from commercetxt.validator import CommerceTXTValidator

# =============================================================================
# COMPLEX TEST DATA (Fractal Inheritance)
# =============================================================================

ROOT_COMMERCE_TXT = """
# @IDENTITY
Name: Multiverse Store
Currency: EUR
URL: https://multiverse.example.com

# @SHIPPING
- Global Express: 3-5 days | Price: 25.00
- Standard: Free
"""

LAPTOP_COMMERCE_TXT = f"""
# @PRODUCT
Name: Quantum X-1 Pro Engineering Laptop
SKU: QX1-PRIME
Brand: NexaGen
URL: https://multiverse.example.com/products/qx1

# @OFFER
Price: 3200.00
Availability: InStock
Condition: New

# @SPECS
Weight: 1400 g
Width: 14 in
Processor: Quantum-X1 Core
RAM: 32 GB
Storage: 1TB NVMe
Battery: 99Wh
Display: 4K OLED

# @INVENTORY
LastUpdated: {datetime.now(timezone.utc).isoformat()}
StockLevel: 25

# @SEMANTIC_LOGIC
- Highlight the "Quantum" processing power for engineers.
"""

LAMP_COMMERCE_TXT = f"""
# @PRODUCT
Name: Solaris Ultra Desk Lamp with Daylight Balance
SKU: SL-200
Brand: IllumiNet
URL: https://multiverse.example.com/products/lamp

# @OFFER
Price: 89.00
Availability: InStock
Condition: New

# @SPECS
Weight: 500 g
Brightness: 1200 lumens
ColorTemp: 5000K
Lifespan: 50000 hours
Input: 220V
Modes: Auto, Reading, Sleep

# @INVENTORY
LastUpdated: {datetime.now(timezone.utc).isoformat()}
StockLevel: 100

# @SEMANTIC_LOGIC
- Emphasize the daylight-balanced color temperature.
"""

LAPTOP_V2_COMMERCE_TXT = """
# @PRODUCT
Name: Quantum X-2 Ultra Workstation
SKU: QX2-ULTRA
Brand: NexaGen
URL: https://multiverse.example.com/products/qx2

# @OFFER
Price: 3500.00
Availability: InStock

# @SPECS
Weight: 1.3 kg
Processor: Quantum-X2 Ultra
RAM: 64 GB
Storage: 2TB NVMe
"""

# =============================================================================
# CLI HELPER
# =============================================================================


def run_cli_internal(args_list):
    with patch.object(sys, "argv", ["commercetxt", *args_list]):
        out, err = StringIO(), StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = 0
            try:
                main()
            except SystemExit as e:
                code = e.code
            return code, out.getvalue(), err.getvalue()


# =============================================================================
# COMPLEX INTEGRATION TEST
# =============================================================================


class MockEmbedder:
    def embed_shards(self, shards):
        for s in shards:
            t = s["text"].lower()
            if "quantum" in t or "laptop" in t:
                s["values"] = [1.0, 0.0] + [0.0] * 382
            elif "lamp" in t or "solaris" in t or "lumens" in t:
                s["values"] = [0.0, 1.0] + [0.0] * 382
            else:
                s["values"] = [0.0, 0.0] + [0.0] * 382
        return shards

    def embed_text(self, text):
        t = text.lower()
        if "laptop" in t or "quantum" in t:
            return [1.0, 0.0] + [0.0] * 382
        if "lamp" in t or "light" in t or "solar" in t or "bright" in t:
            return [0.0, 1.0] + [0.0] * 382
        return [0.0, 0.0] + [0.0] * 382


class MockVectorStore:
    def __init__(self, **kwargs):
        self.data = {}

    def connect(self):
        return True

    def upsert(self, shards, namespace="default"):
        for s in shards:
            shard_id = s.get("metadata", {}).get("id") or f"id_{len(self.data)}"
            self.data[shard_id] = s
        return len(shards)

    def search(self, query_vector, top_k=5, namespace="default"):
        results = []
        for k, v in self.data.items():
            # Dot product on first 2 dims
            score = query_vector[0] * v["values"][0] + query_vector[1] * v["values"][1]
            results.append(
                {"id": k, "score": score, "text": v["text"], "metadata": v["metadata"]}
            )
        return sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]


def _get_rag_data(result):
    """Helper to prepare flat RAG data from ParseResult."""
    prod = result.directives.get("PRODUCT", {})
    offer = result.directives.get("OFFER", {})
    ident = result.directives.get("IDENTITY", {})

    flat = {
        "ITEM": prod.get("Name"),
        "BRAND": prod.get("Brand"),
        "PRICE": offer.get("Price"),
        "CURRENCY": ident.get("Currency") or ident.get("Currency"),  # Try to find it
        "AVAILABILITY": offer.get("Availability"),
        "SPECS": result.directives.get("SPECS", {}),
        "SEMANTIC_LOGIC": result.directives.get("SEMANTIC_LOGIC"),
        "directives": result.directives,
    }
    # Also include raw specs at top level for health checker
    flat.update(result.directives.get("SPECS", {}))
    return flat


def test_complex_integration(tmp_path):
    # 1. SETUP FILE SYSTEM
    (tmp_path / "commerce.txt").write_text(ROOT_COMMERCE_TXT, encoding="utf-8")
    (tmp_path / "laptop.txt").write_text(LAPTOP_COMMERCE_TXT, encoding="utf-8")
    (tmp_path / "lamp.txt").write_text(LAMP_COMMERCE_TXT, encoding="utf-8")
    (tmp_path / "laptop_v2.txt").write_text(LAPTOP_V2_COMMERCE_TXT, encoding="utf-8")

    rag_dir = tmp_path / ".rag"
    rag_dir.mkdir()

    # 2. RESOLVER & INHERITANCE
    # Exercises: resolver.py, parser.py
    resolver = CommerceTXTResolver()

    # Root level
    root_res = parse_cached(ROOT_COMMERCE_TXT)

    # Laptop level (Fractal inheritance: Laptop -> Root)
    laptop_res = parse_cached(LAPTOP_COMMERCE_TXT)
    merged_laptop = resolver.merge(root_res, laptop_res)

    assert merged_laptop.directives["IDENTITY"]["Name"] == "Multiverse Store"
    assert "SHIPPING" in merged_laptop.directives
    assert merged_laptop.directives["PRODUCT"]["SKU"] == "QX1-PRIME"

    # 3. VALIDATOR
    validator = CommerceTXTValidator(strict=True)
    val_laptop = validator.validate(merged_laptop)
    assert not val_laptop.errors

    # 4. RAG PIPELINE (Multi-Product Ingestion)
    config = {
        "RAG_EMBEDDER": "local",
        "RAG_VECTOR_DB": "faiss",
        "FAISS_DIR": str(rag_dir / "faiss"),
        "COMMERCETXT_ROOT": str(tmp_path),
    }

    with (
        patch(
            "commercetxt.rag.drivers.local_embedder.LocalEmbedder",
            return_value=MockEmbedder(),
        ),
        patch(
            "commercetxt.rag.drivers.faiss_store.FaissStore",
            return_value=MockVectorStore(),
        ),
    ):

        container = RAGContainer(config=config)
        pipeline = RAGPipeline(container=container)

        # Ingest Laptop
        laptop_rag_data = _get_rag_data(val_laptop)
        ingest_count = pipeline.ingest(laptop_rag_data)
        assert ingest_count > 0

        # Ingest Lamp
        lamp_res = parse_cached(LAMP_COMMERCE_TXT)
        merged_lamp = resolver.merge(root_res, lamp_res)
        lamp_rag_data = _get_rag_data(merged_lamp)
        pipeline.ingest(lamp_rag_data)

        # Verify Semantic Search discrimination
        res_laptop = pipeline.search(
            "Tell me about the processor in the laptop", top_k=1
        )
        assert "Quantum" in res_laptop[0]["text"]

        res_lamp = pipeline.search("How bright is the lamp?", top_k=5)
        assert any("1200 lumens" in r["text"] for r in res_lamp)

    # 5. CLI ORCHESTRATION (Advanced Flags)

    # Test --compare (QX1 vs QX2)
    # Note: run_cli_internal uses the real _load_and_merge which detects 'commerce.txt'
    # in the same directory and handles inheritance automatically.
    code, stdout, _ = run_cli_internal(
        [str(tmp_path / "laptop.txt"), str(tmp_path / "laptop_v2.txt"), "--compare"]
    )
    assert code == 0
    assert "Product Comparison" in stdout
    assert "laptop.txt vs laptop_v2.txt" in stdout
    assert "Processor" in stdout
    assert "Quantum-X1" in stdout
    assert "Quantum-X2" in stdout

    # Test --health on laptop (should include inherited identity)
    code, stdout, _ = run_cli_internal([str(tmp_path / "laptop.txt"), "--health"])
    assert code == 0
    assert "AI Health Score" in stdout

    # Test --prompt on lamp (should see inheritied Multiverse Store)
    code, stdout, _ = run_cli_internal([str(tmp_path / "lamp.txt"), "--prompt"])
    assert code == 0
    assert "STORE: Multiverse Store" in stdout
    assert "Solaris" in stdout

    print("\n[SUCCESS] Complex full-stack integration test passed.")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_complex_integration(Path(tmp))
