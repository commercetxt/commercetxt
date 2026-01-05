"""
Schema.org bridge for CommerceTXT.
Converts parsed data to JSON-LD markup.

Supports all 12 CommerceTXT sections with proper Schema.org mappings.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..core.constants import KNOWN_SECTIONS


class SchemaBridge:
    """
    Converts CommerceTXT data to Schema.org Product JSON-LD.

    Handles both flat and nested data structures:
    - Flat: {"NAME": "X", "PRICE": "99", ...}
    - Nested: {"PRODUCT": {"Name": "X"}, "OFFER": {"Price": "99"}, ...}
    """

    def to_json_ld(self, data: dict[str, Any], base_url: str | None = None) -> str:
        """
        Generates Schema.org Product JSON-LD from CommerceTXT data.

        Args:
            data: Parsed CommerceTXT data (flat or nested)
            base_url: Optional base URL for constructing product URLs

        Returns:
            JSON-LD string
        """
        product_data = self._extract_product_data(data)
        offer_data = self._extract_offer_data(data)

        schema: dict[str, Any] = {
            "@context": "https://schema.org/",
            "@type": "Product",
        }

        # === PRODUCT FIELDS ===

        # Name
        name = self._get_value(product_data, ["Name", "NAME", "name"])
        if name is not None:
            schema["name"] = str(name)

        # Brand
        brand = self._get_value(product_data, ["Brand", "BRAND", "brand"])
        if brand is not None:
            schema["brand"] = {"@type": "Brand", "name": str(brand)}

        # SKU
        sku = self._get_value(product_data, ["SKU", "sku"])
        if sku is not None:
            schema["sku"] = str(sku)

        # GTIN
        gtin = self._get_value(product_data, ["GTIN", "gtin", "gtin13"])
        if gtin is not None:
            schema["gtin13"] = str(gtin)

        # URL
        url = self._get_value(product_data, ["URL", "url"])
        if url is not None:
            schema["url"] = str(url)
        elif base_url and sku:
            schema["url"] = f"{base_url.rstrip('/')}/products/{sku}"

        # Model
        model = self._get_value(product_data, ["Model", "MODEL", "model"])
        if model is not None:
            schema["model"] = str(model)

        # === OFFER FIELDS ===

        price = self._get_value(offer_data, ["Price", "PRICE", "price"])
        if price is not None:
            offer: dict[str, Any] = {
                "@type": "Offer",
                "price": str(price),
            }

            # Currency
            currency = self._get_value(offer_data, ["Currency", "CURRENCY", "currency"])
            if currency is None:
                # Fallback to IDENTITY.Currency in nested mode
                identity = data.get("IDENTITY", {})
                if isinstance(identity, dict):
                    currency = self._get_value(
                        identity, ["Currency", "CURRENCY", "currency"]
                    )
            if currency is not None:
                offer["priceCurrency"] = str(currency)

            # Availability
            availability = self._get_value(
                offer_data, ["Availability", "AVAILABILITY", "availability"]
            )
            if availability is not None:
                availability_map = {
                    "InStock": "https://schema.org/InStock",
                    "OutOfStock": "https://schema.org/OutOfStock",
                    "PreOrder": "https://schema.org/PreOrder",
                    "Discontinued": "https://schema.org/Discontinued",
                }
                offer["availability"] = availability_map.get(
                    str(availability), "https://schema.org/InStock"
                )

            # Condition
            condition = self._get_value(
                offer_data, ["Condition", "CONDITION", "condition"]
            )
            if condition is not None:
                condition_map = {
                    "New": "https://schema.org/NewCondition",
                    "Refurbished": "https://schema.org/RefurbishedCondition",
                    "Used": "https://schema.org/UsedCondition",
                }
                offer["itemCondition"] = condition_map.get(
                    str(condition), "https://schema.org/NewCondition"
                )

            # Offer URL (fallback to product url)
            offer_url = self._get_value(offer_data, ["URL", "url"])
            if offer_url is not None:
                offer["url"] = str(offer_url)
            elif "url" in schema:
                offer["url"] = schema["url"]

            schema["offers"] = offer

        # === REVIEWS ===
        reviews = data.get("REVIEWS", {})
        if reviews and isinstance(reviews, dict):
            rating = self._get_value(reviews, ["Rating", "RATING", "rating"])
            count = self._get_value(reviews, ["Count", "COUNT", "reviewCount", "count"])

            if rating is not None and count is not None:
                schema["aggregateRating"] = {
                    "@type": "AggregateRating",
                    "ratingValue": str(rating),
                    "reviewCount": str(count),
                }
                scale = self._get_value(
                    reviews, ["RatingScale", "RATINGSCALE", "bestRating"]
                )
                if scale is not None:
                    schema["aggregateRating"]["bestRating"] = str(scale)

        # === SPECS ===
        specs = data.get("SPECS", {})
        if specs and isinstance(specs, dict):
            additional_props = []
            for key, value in specs.items():
                if key == "items":
                    continue
                if value is None or value == "":
                    continue
                additional_props.append(
                    {
                        "@type": "PropertyValue",
                        "name": str(key),
                        "value": str(value),
                    }
                )
            if additional_props:
                schema["additionalProperty"] = additional_props

        # === IMAGES ===
        images_data = data.get("IMAGES", {})
        if images_data and isinstance(images_data, dict):
            items = images_data.get("items", [])
            if isinstance(items, list) and items:
                image_urls = []
                for item in items:
                    if isinstance(item, dict):
                        img_url = item.get("path") or item.get("value")
                        if isinstance(img_url, str) and img_url:
                            image_urls.append(img_url)
                if image_urls:
                    schema["image"] = (
                        image_urls[0] if len(image_urls) == 1 else image_urls
                    )

        # === VARIANTS ===
        # Map to schema.org offers array with different variants
        variants = data.get("VARIANTS", {})
        if variants and isinstance(variants, dict):
            variants.get("Type", "Variant")
            options = variants.get("Options", [])

            if isinstance(options, list) and options:
                variant_offers = []
                for option in options:
                    if not isinstance(option, str):
                        continue

                    parsed = self._parse_variant_option(option)
                    if parsed:
                        # Get currency from schema offers or default to USD
                        currency = "USD"
                        if "offers" in schema and isinstance(schema["offers"], dict):
                            currency = schema["offers"].get("priceCurrency", "USD")

                        variant_offer = {
                            "@type": "Offer",
                            "name": parsed["name"],
                            "price": parsed.get("price", ""),
                            "priceCurrency": currency,
                        }

                        if parsed.get("sku"):
                            variant_offer["sku"] = parsed["sku"]

                        # Map stock to availability
                        if parsed.get("stock") is not None:
                            stock_num = parsed["stock"]
                            if stock_num > 0:
                                variant_offer["availability"] = (
                                    "https://schema.org/InStock"
                                )
                                variant_offer["inventoryLevel"] = {
                                    "@type": "QuantitativeValue",
                                    "value": stock_num,
                                }
                            else:
                                variant_offer["availability"] = (
                                    "https://schema.org/OutOfStock"
                                )

                        variant_offers.append(variant_offer)

                if variant_offers:
                    # Convert single offer to array and add variants
                    if "offers" in schema and not isinstance(schema["offers"], list):
                        schema["offers"] = [schema["offers"]] + variant_offers
                    else:
                        schema["offers"] = variant_offers

        # === SUBSCRIPTION ===
        # Map to schema.org Offer with priceSpecification
        subscription = data.get("SUBSCRIPTION", {})
        if subscription and isinstance(subscription, dict):
            plans = subscription.get("Plans", [])
            if isinstance(plans, list) and plans:
                subscription_offers = []
                for plan in plans:
                    if not isinstance(plan, str):
                        continue

                    parsed = self._parse_subscription_plan(plan)
                    if parsed:
                        # Get currency from schema offers or default to USD
                        currency = "USD"
                        if "offers" in schema and isinstance(schema["offers"], dict):
                            currency = schema["offers"].get("priceCurrency", "USD")

                        sub_offer = {
                            "@type": "Offer",
                            "name": parsed["name"],
                            "price": parsed["price"],
                            "priceCurrency": currency,
                            "priceSpecification": {
                                "@type": "UnitPriceSpecification",
                                "referenceQuantity": {
                                    "@type": "QuantitativeValue",
                                    "value": "1",
                                },
                            },
                        }

                        if parsed.get("frequency"):
                            sub_offer["priceSpecification"]["billingIncrement"] = (
                                parsed["frequency"]
                            )

                        subscription_offers.append(sub_offer)

                # Add subscription benefits if any
                subscription.get("Trial")
                subscription.get("CancelAnytime")

                if subscription_offers:
                    if "offers" in schema and not isinstance(schema["offers"], list):
                        schema["offers"] = [schema["offers"]] + subscription_offers
                    elif subscription_offers:
                        if "offers" not in schema:
                            schema["offers"] = subscription_offers
                        else:
                            schema["offers"].extend(subscription_offers)

        # === COMPATIBILITY ===
        # Map to schema.org additionalProperty
        compatibility = data.get("COMPATIBILITY", {})
        if compatibility and isinstance(compatibility, dict):
            if "additionalProperty" not in schema:
                schema["additionalProperty"] = []

            for key, value in compatibility.items():
                if value:
                    schema["additionalProperty"].append(
                        {
                            "@type": "PropertyValue",
                            "name": f"Compatible with {key}",
                            "value": str(value),
                        }
                    )

        # === SUSTAINABILITY ===
        # Map to schema.org additionalProperty or use sustainability extensions
        sustainability = data.get("SUSTAINABILITY", {})
        if sustainability and isinstance(sustainability, dict):
            if "additionalProperty" not in schema:
                schema["additionalProperty"] = []

            for key, value in sustainability.items():
                if value:
                    schema["additionalProperty"].append(
                        {
                            "@type": "PropertyValue",
                            "propertyID": "sustainability",
                            "name": f"Sustainability: {key}",
                            "value": str(value),
                        }
                    )

        # === PROMOS ===
        # Can be mapped to offers or additionalProperty
        promos = data.get("PROMOS", {})
        if promos and isinstance(promos, dict):
            if "additionalProperty" not in schema:
                schema["additionalProperty"] = []

            for key, value in promos.items():
                if value:
                    schema["additionalProperty"].append(
                        {
                            "@type": "PropertyValue",
                            "propertyID": "promotion",
                            "name": f"Promotion: {key}",
                            "value": str(value),
                        }
                    )

        # === SEMANTIC_LOGIC ===
        # Map tags to keywords or category
        semantic_logic = data.get("SEMANTIC_LOGIC", {})
        if semantic_logic and isinstance(semantic_logic, dict):
            tags = semantic_logic.get("Tags", "")
            if tags:
                # Map to schema.org keywords
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                if tag_list:
                    schema["keywords"] = ", ".join(tag_list)

            # Context can be mapped to description if main description is missing
            context = semantic_logic.get("Context", "")
            if context and "description" not in schema:
                schema["description"] = context

        return json.dumps(schema, indent=2, ensure_ascii=False)

    def _extract_product_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract product data from nested or flat structure.

        IMPORTANT FIX:
        - Handles empty dict {} vs missing key distinction
        - Uses KNOWN_SECTIONS for schema-aware filtering in flat mode
        - Case-insensitive lookup is handled by _get_value
        """
        product = data.get("PRODUCT")

        # Nested mode: non-empty PRODUCT section exists
        if isinstance(product, dict) and product:
            return product

        # Flat mode: exclude known non-product sections
        # This preserves NAME, BRAND, etc. while removing OFFER, IMAGES, etc.
        return {
            k: v
            for k, v in data.items()
            if k.upper() not in KNOWN_SECTIONS or k.upper() == "PRODUCT"
        }

    def _extract_offer_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract offer data from nested or flat structure.

        IMPORTANT FIX:
        - Handles empty dict {} vs missing key distinction
        - In flat mode, returns whole dict for PRICE/CURRENCY lookup
        """
        offer = data.get("OFFER")

        # Nested mode: non-empty OFFER section exists
        if isinstance(offer, dict) and offer:
            return offer

        # Flat mode: return whole dict
        # PRICE, CURRENCY, AVAILABILITY are typically at top level in flat mode
        return data

    def _get_value(self, data: dict[str, Any], keys: list[str]) -> Any:
        """
        Case-insensitive key lookup. Returns first matching value or None.
        """
        if not data or not isinstance(data, dict):
            return None

        data_lower = {str(k).lower(): v for k, v in data.items()}
        for key in keys:
            val = data_lower.get(str(key).lower())
            if val is not None:
                return val
        return None

    def _parse_variant_option(self, option: str) -> dict[str, Any]:
        """
        Parse variant option string.

        Format: "Name: Price | Key: Value | Key: Value"
        Example: "Obsidian / 128GB: 999.00 | SKU: GA05843-128-OBS | Stock: 22"
        """

        result: dict[str, Any] = {}
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
                # Extract number
                match = re.search(r"\d+", value)
                if match:
                    result["stock"] = (
                        match.group()
                    )  # Store as string to match dict[str, str]

        return result

    def _parse_subscription_plan(self, plan: str) -> dict[str, str]:
        """
        Parse subscription plan string.

        Format: "Monthly: 19.99 | Frequency: 1 bag/month"
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
