"""
CommerceTXT central constants unit.
SINGLE SOURCE OF TRUTH - All other modules import from here.
"""

from typing import Any

# =============================================================================
# SECURITY & NETWORK
# =============================================================================

LOOPBACK_IP_START: int = 2130706432  # 127.0.0.0
LOOPBACK_IP_END: int = 2147483647  # 127.255.255.255
MAX_URL_LENGTH: int = 2048

# =============================================================================
# VALIDATION THRESHOLDS
# =============================================================================

CURRENCY_CODE_LEN: int = 3
MIN_CURRENCY_LEN: int = 2
MAX_CURRENCY_LEN: int = 4
MAX_ALT_TEXT_LEN: int = 120

# Filters & Variants Limits
MAX_FILTER_OPTIONS: int = 50
MAX_FILTER_VALUE_LENGTH: int = 100
MAX_VARIANT_COMBINATIONS: int = 50
MAX_VARIANT_GROUPS: int = 2

# =============================================================================
# TRUST & INVENTORY THRESHOLDS
# =============================================================================

INVENTORY_STALE_HOURS: int = 72
INVENTORY_VERY_STALE_HOURS: int = 168

# =============================================================================
# ALLOWED ENUM SETS
# =============================================================================

VALID_AVAILABILITY: set[str] = {"InStock", "OutOfStock", "PreOrder", "Discontinued"}
VALID_CONDITION: set[str] = {"New", "Refurbished", "Used"}
VALID_STOCK_STATUS: set[str] = {"InStock", "LowStock", "OutOfStock", "Backorder"}

# =============================================================================
# COMMON KEYS
# =============================================================================

KEY_ITEMS: str = "items"
KEY_CHILDREN: str = "children"
KEY_VALUE: str = "value"

# =============================================================================
# LOGISTICS (Physical Units)
# =============================================================================

# Weight thresholds (in kg)
HEAVY_THRESHOLD_KG: float = 20.0
BULKY_THRESHOLD_KG: float = 5.0
LIGHTWEIGHT_THRESHOLD_KG: float = 0.5
LB_TO_KG_CONVERSION: float = 0.453592  # More accurate than 0.45

# Dimension thresholds (in cm)
OVERSIZED_THRESHOLD_CM: float = 150.0
LARGE_ITEM_THRESHOLD_CM: float = 100.0
INCH_TO_CM_CONVERSION: float = 2.54
DIMENSION_COUNT_REQUIRED: int = 3

# =============================================================================
# AI HEALTH CHECK THRESHOLDS
# =============================================================================

MIN_TECHNICAL_SPECS: int = 8
MAX_DESCRIPTION_LENGTH: int = 1500
HEALTH_EXCELLENT_LIMIT: int = 90
HEALTH_GOOD_LIMIT: int = 75
HEALTH_FAIR_LIMIT: int = 50

# =============================================================================
# CLI DISPLAY THRESHOLDS
# =============================================================================

CLI_SCORE_EXCELLENT: int = 85
CLI_SCORE_GOOD: int = 70
CLI_SCORE_FAIR: int = 50

# =============================================================================
# BRIDGE / DISPLAY LIMITS
# =============================================================================

GRADE_A_THRESHOLD: int = 90
GRADE_B_THRESHOLD: int = 70
MAX_VARIANT_OPTIONS_DISPLAY: int = 3
MAX_SPECS_DISPLAY: int = 5
MAX_SHIPPING_METHODS_DISPLAY: int = 2

# Default values for missing data in bridge (used to catch mutations)
DEFAULT_STORE_NAME: str = "Unknown"
DEFAULT_CURRENCY: str = "USD"
DEFAULT_ITEM_NAME: str = "Unknown Item"
DEFAULT_PRICE: str = "N/A"
DEFAULT_AVAILABILITY: str = "Unknown"

# Async parser executor types
EXECUTOR_TYPE_THREAD: str = "thread"
EXECUTOR_TYPE_PROCESS: str = "process"
VALID_EXECUTOR_TYPES: tuple[str, str] = (EXECUTOR_TYPE_THREAD, EXECUTOR_TYPE_PROCESS)

# Supported file encodings for parser
SUPPORTED_ENCODINGS: tuple[str, ...] = (
    "utf-8-sig",  # UTF-8 with BOM
    "utf-8",  # UTF-8 without BOM
    "utf-16",  # UTF-16 with BOM (auto-detects LE/BE)
    "utf-16-le",  # UTF-16 Little Endian
    "utf-16-be",  # UTF-16 Big Endian
    "utf-32",  # UTF-32 with BOM
    "utf-32-le",  # UTF-32 Little Endian
    "utf-32-be",  # UTF-32 Big Endian
)

# Penalties for AI readiness scoring
PENALTY_MISSING_VERSION: int = 10
PENALTY_MISSING_OFFER: int = 30
PENALTY_PER_ERROR: int = 20
PENALTY_STALE_INVENTORY: int = 15

# =============================================================================
# RAG (Retrieval-Augmented Generation) CONSTANTS
# =============================================================================

# Security limits
MAX_TEXT_LENGTH: int = 10000
MAX_SHARDS: int = 1000
MAX_LIST_ITEMS: int = 100

# Default plural attributes for RAG generation
DEFAULT_PLURAL_ATTRIBUTES: set[str] = {
    "dimensions",
    "features",
    "colors",
    "sizes",
    "variants",
    "options",
    "benefits",
    "ingredients",
}

# =============================================================================
# SEMANTIC TAGGING DATA (Shared by RAG and Core)
# =============================================================================

# Price segmentation thresholds (consistent float values)
PRICE_TIERS: dict[str, tuple[float, float]] = {
    "budget_friendly": (0.0, 50.0),
    "mid_range": (50.0, 200.0),
    "premium": (200.0, 500.0),
    "luxury": (500.0, float("inf")),
}

# Category detection keywords
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "electronics": ["phone", "laptop", "tablet", "computer", "watch", "headphones"],
    "apparel": ["shirt", "pants", "shoes", "dress", "jacket", "clothing"],
    "home_goods": ["furniture", "lamp", "chair", "table", "sofa"],
    "toys": ["toy", "doll", "puzzle", "game", "lego", "playset"],
}

# Material classifications (extended for both RAG and Filters)
MATERIAL_TYPES: dict[str, list[str]] = {
    "natural": [
        "cotton",
        "wool",
        "silk",
        "leather",
        "wood",
        "linen",
        "bamboo",
        "hemp",
        "stone",
        "clay",
    ],
    "synthetic": ["plastic", "polyester", "nylon", "acrylic", "vinyl", "synthetic"],
    "metal": [
        "steel",
        "iron",
        "aluminum",
        "metal",
        "silver",
        "gold",
        "copper",
        "brass",
    ],
    "glass_ceramic": ["glass", "ceramic", "porcelain"],
}

# Seasonal keywords by month range
SEASONAL_KEYWORDS: dict[str, dict[str, Any]] = {
    "winter": {
        "months": [12, 1, 2],
        "keywords": [
            "coat",
            "jacket",
            "heater",
            "snow",
            "winter",
            "cold",
            "warm",
            "thermal",
            "ski",
            "snowboard",
        ],
    },
    "summer": {
        "months": [6, 7, 8],
        "keywords": [
            "swimsuit",
            "shorts",
            "fan",
            "cooling",
            "summer",
            "beach",
            "sun",
            "swim",
            "sunscreen",
            "sandals",
        ],
    },
    "spring": {
        "months": [3, 4, 5],
        "keywords": ["garden", "plant", "outdoor", "spring", "rain", "umbrella"],
    },
    "fall": {
        "months": [9, 10, 11],
        "keywords": ["autumn", "fall", "halloween", "harvest", "thanksgiving"],
    },
    "holiday": {
        "months": [11, 12],
        "keywords": ["christmas", "holiday", "decoration", "festive", "gift", "lights"],
    },
}

# Sustainability certifications
SUSTAINABILITY_CERTS: dict[str, list[str]] = {
    "fair_trade": ["fair trade", "fairtrade"],
    "organic": ["organic", "bio", "usda organic"],
    "fsc": ["fsc", "forest stewardship"],
    "energy_star": ["energy star", "energystar"],
    "eco": ["eco-friendly", "recycled"],
    "b_corp": ["b corp", "bcorp"],
}

# =============================================================================
# TRUSTED REVIEW PLATFORMS (Section 4.7.1)
# =============================================================================

TRUSTED_REVIEW_DOMAINS: list[str] = [
    "trustpilot.com",
    "google.com",
    "reviews.io",
    "yotpo.com",
    "feefo.com",
    "bazaarvoice.com",
    "powerreviews.com",
]
