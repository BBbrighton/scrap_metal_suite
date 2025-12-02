"""Supplier Portal - Dashboard"""

from scrap_metal_suite.www.supplier.utils import get_supplier_context

no_cache = 1


def get_context(context):
    context.title = "Dashboard - Supplier Portal"
    context.active_page = "dashboard"
    get_supplier_context(context)
    return context
