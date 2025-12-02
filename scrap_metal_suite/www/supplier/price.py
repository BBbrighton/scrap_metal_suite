"""Supplier Portal - Price"""

from scrap_metal_suite.www.supplier.utils import get_supplier_context

no_cache = 1


def get_context(context):
    context.title = "Price - Supplier Portal"
    context.active_page = "price"
    get_supplier_context(context)
    return context
