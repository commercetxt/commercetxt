"""
Shared test fixtures for CommerceTXT test suite.

Provides common fixtures for CLI testing and real data file access
from examples/google-store/ and vectors/ directories.
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from commercetxt.cli import main

# =============================================================================
# Path Configuration
# =============================================================================

TESTS_DIR = Path(__file__).parent
VECTORS_DIR = TESTS_DIR / "vectors"
EXAMPLES_DIR = TESTS_DIR.parent.parent.parent / "examples" / "google-store"
VALID_DIR = VECTORS_DIR / "valid"
RAG_EXPECTED_DIR = VECTORS_DIR / "rag"


# =============================================================================
# CLI Fixtures
# =============================================================================


@pytest.fixture
def run_cli():
    """Execute CLI commands and capture output."""

    def _run(args_list):
        with patch.object(sys, "argv", ["commercetxt", *args_list]):
            out, err = StringIO(), StringIO()
            with patch("sys.stdout", out), patch("sys.stderr", err):
                code = 0
                try:
                    main()
                except SystemExit as e:
                    code = e.code
                return code, out.getvalue(), err.getvalue()

    return _run


# =============================================================================
# Google Store Example Fixtures
# =============================================================================


@pytest.fixture
def pixel_9_pro_path():
    """Google Pixel 9 Pro product file (tier 3 reference implementation)."""
    path = EXAMPLES_DIR / "products" / "pixel-9-pro.txt"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def pixel_8a_path():
    """Google Pixel 8a product file."""
    path = EXAMPLES_DIR / "products" / "pixel-8a.txt"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def google_commerce_path():
    """Google Store main commerce.txt."""
    path = EXAMPLES_DIR / "commerce.txt"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def smartphones_category_path():
    """Google Store smartphones category with filters and semantic logic."""
    path = EXAMPLES_DIR / "categories" / "smartphones.txt"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


# =============================================================================
# Test Vector Fixtures
# =============================================================================


@pytest.fixture
def subscription_product_path():
    """Subscription product with plans and trial period."""
    path = VALID_DIR / "subscription_product.txt"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def complete_store_path():
    """Complete store with all tier 1-3 directives."""
    path = VALID_DIR / "complete_store.txt"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def full_product_path():
    """Full product with variants, reviews, and images."""
    path = VALID_DIR / "full_product.txt"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def minimal_product_path():
    """Minimal valid product fixture."""
    path = VALID_DIR / "minimal_product.txt"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def pixel_9_pro_expected():
    """Expected RAG output for Pixel 9 Pro validation."""
    path = RAG_EXPECTED_DIR / "pixel_9_pro_expected.json"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Component Fixtures
# =============================================================================


@pytest.fixture
def products_storage():
    """LocalStorage initialized with Google Store products directory."""
    from commercetxt.rag.drivers.local_storage import LocalStorage

    products_dir = EXAMPLES_DIR / "products"
    if not products_dir.exists():
        pytest.skip("Products directory not found")
    return LocalStorage(root_path=str(products_dir))


@pytest.fixture
def rag_generator():
    """RAG shard generator instance."""
    from commercetxt.rag.core.generator import RAGGenerator

    return RAGGenerator()


@pytest.fixture
def schema_bridge():
    """Schema.org JSON-LD bridge instance."""
    from commercetxt.rag.tools.schema_bridge import SchemaBridge

    return SchemaBridge()


@pytest.fixture
def health_checker():
    """AI health checker instance."""
    from commercetxt.rag.tools.health_check import AIHealthChecker

    return AIHealthChecker()


# Session-scoped embedder to avoid repeated model loading (expensive)
@pytest.fixture(scope="session")
def local_embedder_session():
    """Session-scoped local embedder (loads model once per test session)."""
    try:
        from commercetxt.rag.drivers.local_embedder import LocalEmbedder

        return LocalEmbedder()
    except ImportError:
        pytest.skip("sentence-transformers not installed")


@pytest.fixture
def local_embedder(local_embedder_session):
    """Local sentence-transformers embedder (uses session-scoped instance)."""
    return local_embedder_session
    try:
        from commercetxt.rag.drivers.local_embedder import LocalEmbedder

        return LocalEmbedder()
    except ImportError:
        pytest.skip("sentence-transformers not installed")


@pytest.fixture
def product_comparator():
    """Product comparator instance."""
    from commercetxt.rag.tools.comparator import ProductComparator

    return ProductComparator()


@pytest.fixture
def semantic_normalizer():
    """Semantic normalizer instance."""
    from commercetxt.rag.tools.normalizer import SemanticNormalizer

    return SemanticNormalizer()
