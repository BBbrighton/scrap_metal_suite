"""Manager Portal - World Price"""

no_cache = 1


def get_context(context):
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
