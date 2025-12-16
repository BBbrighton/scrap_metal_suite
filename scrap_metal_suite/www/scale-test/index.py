import frappe

def get_context(context):
    """Scale Test Page - Standalone testing for WebSerial scale integration

    This page is for testing hardware scale connections without affecting POS operations.
    """
    context.no_cache = 1
    context.show_sidebar = False

    # Page metadata
    context.title = "Scale Connection Test"

    return context
