"""Manager Portal - Price Announcement"""

import frappe

no_cache = 1


def get_context(context):
    context.active_page = "price"

    # Get prices from Item Price if available
    # This is a placeholder - you'll want to customize based on your price list setup
    context.prices = []

    # Try to get items with prices from different price lists
    try:
        items = frappe.get_all(
            "Item",
            filters={"item_group": ["like", "%Scrap%"]},
            fields=["name", "item_name", "stock_uom"],
            limit=20
        )

        for item in items:
            item_data = {
                "item_code": item.name,
                "item_name": item.item_name,
                "uom": item.stock_uom,
                "standard_price": get_item_price(item.name, "Standard Buying"),
                "vip_price": get_item_price(item.name, "VIP Buying"),
                "premium_price": get_item_price(item.name, "Premium Buying"),
                "modified": frappe.utils.nowdate()
            }
            context.prices.append(item_data)

    except Exception:
        # If no items found, context.prices remains empty
        # The template will show sample data
        pass

    return context


def get_item_price(item_code, price_list):
    """Get price for an item from a specific price list"""
    try:
        price = frappe.db.get_value(
            "Item Price",
            {
                "item_code": item_code,
                "price_list": price_list,
                "buying": 1
            },
            "price_list_rate"
        )
        return price
    except Exception:
        return None
