"""Manager Portal - World Price

NOTE ON THE FILENAME: this file was `world-price.py` (hyphen) and was therefore
NEVER LOADED. Frappe resolves a www controller by replacing hyphens with
underscores in the template's basename (`template_page.py:143`), so it looked
for `world_price.py` and found nothing — the page rendered with no controller
and, critically, no auth check. Renamed 2026-08-21 to close that hole.

The `world_prices` / `exchange_rates` context below is FABRICATED SAMPLE DATA
and is not referenced by `world-price.html` (verified: 0 references), which
hardcodes its own figures. Nothing here reaches a real market feed. Do not
present this page's numbers as real prices.
"""

no_cache = 1


from scrap_metal_suite.www.manager.utils import require_login


def get_context(context):
    require_login(context, "/manager/world-price")
    context.active_page = "world-price"

    # Placeholder for world prices
    # In production, you would fetch from an API like:
    # - LME (London Metal Exchange)
    # - Kitco
    # - MetalPrices API
    # - Trading Economics

    context.world_prices = [
        {
            "name": "Copper",
            "market": "LME Official",
            "price": 8945,
            "unit": "USD/Tonne",
            "change": 1.2,
            "icon": "🥇"
        },
        {
            "name": "Aluminum",
            "market": "LME Official",
            "price": 2485,
            "unit": "USD/Tonne",
            "change": -0.5,
            "icon": "🥈"
        },
        {
            "name": "Steel (HRC)",
            "market": "China Export FOB",
            "price": 520,
            "unit": "USD/Tonne",
            "change": 0.0,
            "icon": "⚙️"
        },
    ]

    context.exchange_rates = {
        "USD_THB": 34.85,
        "EUR_THB": 37.20,
        "CNY_THB": 4.82
    }

    return context
