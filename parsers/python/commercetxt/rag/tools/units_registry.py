"""
Registry of physical units and their conversion factors to base SI units.
Includes common e-commerce units used by Amazon, Shopify, WooCommerce, and Magento.
"""

# Base unit: meter (m)
# Used for: product dimensions, shipping box sizes, fabric lengths
DISTANCE_UNITS = {
    # Metric (SI standard)
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "metre": 1.0,  # UK spelling
    "metres": 1.0,
    "cm": 0.01,
    "centimeter": 0.01,
    "centimeters": 0.01,
    "centimetre": 0.01,  # UK spelling
    "centimetres": 0.01,
    "mm": 0.001,
    "millimeter": 0.001,
    "millimeters": 0.001,
    "millimetre": 0.001,  # UK spelling
    "millimetres": 0.001,
    "km": 1000.0,
    "kilometer": 1000.0,
    "kilometre": 1000.0,  # UK spelling
    # Imperial (US/UK - Amazon, Shopify default for US market)
    "in": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
    '"': 0.0254,  # Common shorthand (e.g., 10" screen)
    "ft": 0.3048,
    "foot": 0.3048,
    "feet": 0.3048,
    "'": 0.3048,  # Common shorthand (e.g., 6' tall)
    "yd": 0.9144,
    "yard": 0.9144,
    "yards": 0.9144,
    "mile": 1609.34,
    "miles": 1609.34,
    "mi": 1609.34,
}

# Base unit: kilogram (kg)
# Used for: product weight, shipping weight, package weight
WEIGHT_UNITS = {
    # Metric (SI standard - WooCommerce, Magento default for EU)
    "kg": 1.0,
    "kilogram": 1.0,
    "kilograms": 1.0,
    "kgs": 1.0,
    "g": 0.001,
    "gram": 0.001,
    "grams": 0.001,
    "mg": 0.000001,
    "milligram": 0.000001,
    "milligrams": 0.000001,
    "t": 1000.0,
    "ton": 1000.0,  # Metric ton
    "tonne": 1000.0,
    "mt": 1000.0,  # Metric ton abbreviation
    # Imperial (US - Amazon US default)
    "lb": 0.453592,
    "lbs": 0.453592,
    "pound": 0.453592,
    "pounds": 0.453592,
    "oz": 0.0283495,
    "ounce": 0.0283495,
    "ounces": 0.0283495,
    # UK Imperial (slightly different from US)
    "stone": 6.35029,  # Used in UK for body weight
    "st": 6.35029,
}

# Base unit: liter (l)
# Used for: liquid volume, beverage containers, fuel capacity
VOLUME_UNITS = {
    # Metric (SI standard)
    "l": 1.0,
    "liter": 1.0,
    "litre": 1.0,  # UK spelling
    "liters": 1.0,
    "litres": 1.0,
    "ml": 0.001,
    "milliliter": 0.001,
    "millilitre": 0.001,  # UK spelling
    "milliliters": 0.001,
    "millilitres": 0.001,
    "cl": 0.01,
    "centiliter": 0.01,
    "centilitre": 0.01,  # UK spelling
    "dl": 0.1,
    "deciliter": 0.1,
    "decilitre": 0.1,  # UK spelling
    # Cubic measurements (often used for packaging)
    "m3": 1000.0,
    "m³": 1000.0,
    "cubic meter": 1000.0,
    "cubic metre": 1000.0,
    "cm3": 0.001,
    "cm³": 0.001,
    "cubic centimeter": 0.001,
    "cc": 0.001,  # Common abbreviation
    # US Imperial (Amazon US, Shopify US default)
    "gal": 3.78541,  # US gallon
    "gallon": 3.78541,
    "gallons": 3.78541,
    "qt": 0.946353,  # US quart
    "quart": 0.946353,
    "quarts": 0.946353,
    "pt": 0.473176,  # US pint
    "pint": 0.473176,
    "pints": 0.473176,
    "cup": 0.236588,  # US cup (cooking)
    "cups": 0.236588,
    "fl oz": 0.0295735,  # US fluid ounce
    "floz": 0.0295735,
    "fluid ounce": 0.0295735,
    "fluid ounces": 0.0295735,
    "tbsp": 0.0147868,  # Tablespoon (cooking)
    "tablespoon": 0.0147868,
    "tsp": 0.00492892,  # Teaspoon (cooking)
    "teaspoon": 0.00492892,
    # UK Imperial (slightly different from US)
    "uk gal": 4.54609,  # UK gallon
    "uk gallon": 4.54609,
    "uk pt": 0.568261,  # UK pint
    "uk pint": 0.568261,
    "uk fl oz": 0.0284131,  # UK fluid ounce
}
