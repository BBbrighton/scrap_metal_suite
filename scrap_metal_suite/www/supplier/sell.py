"""Supplier Portal - Sell"""

from scrap_metal_suite.www.supplier.utils import get_supplier_context

no_cache = 1


def get_context(context):
    context.title = "Sell - Supplier Portal"
    context.active_page = "sell"
    get_supplier_context(context)
    return context
