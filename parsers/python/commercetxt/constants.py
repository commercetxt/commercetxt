"""
CommerceTXT validation constants.
Rules are set here. Keep them sharp.
"""

# Trust thresholds
INVENTORY_STALE_HOURS = 72
INVENTORY_VERY_STALE_HOURS = 168

# Allowed sets
VALID_AVAILABILITY = {"InStock", "OutOfStock", "PreOrder", "Discontinued"}
VALID_CONDITION = {"New", "Refurbished", "Used"}
VALID_STOCK_STATUS = {"InStock", "LowStock", "OutOfStock", "Backorder"}

# Keys
KEY_ITEMS = "items"
KEY_CHILDREN = "children"
KEY_VALUE = "value"
