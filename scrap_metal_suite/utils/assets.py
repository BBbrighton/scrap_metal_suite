"""Cache-busting token for hand-linked `/assets/...` URLs.

Extracted from `www/pos/terminal.py`, which solved this first, so every
terminal can share one implementation instead of copying it per page.

Frappe's hashed-bundle cache busting does not apply to these pages: they link
plain `/assets/scrap_metal_suite/...` paths, served with `Cache-Control:
max-age=43200`. With no version in the URL a browser keeps the old file for 12
hours, and neither `bench clear-cache` nor `bench build` can dislodge it —
those clear server state, not the browser's HTTP cache. After a deploy that
means a floor terminal can run half-day-old JS against a new API.

`get_build_version()` alone is not enough: it is the mtime of
sites/assets/assets.json, which only moves on `bench build`. The app's public/
dir is symlinked into sites/assets, so editing pos.css changes the file the
browser gets while leaving assets.json untouched — the token would not move and
the stale copy would survive.

So stamp the newest mtime of the files actually linked by the page. That is
correct in both directions: it moves the moment a file is edited locally, and
it moves on deploy when `git pull` rewrites them. `get_build_version()` remains
the fallback for when none of the files can be stat'd.
"""

import os

import frappe


def asset_version(linked_assets):
    """Version token for a page's hand-linked assets.

    Args:
        linked_assets: iterable of paths relative to the app's `public/` dir,
            kept in sync with the tags in that page's template.

    Returns:
        str: token to append as `?v=`
    """
    base = frappe.get_app_path("scrap_metal_suite", "public")
    newest = 0

    for rel in linked_assets:
        try:
            newest = max(newest, os.path.getmtime(os.path.join(base, rel)))
        except OSError:
            continue

    if newest:
        return str(int(newest))

    return frappe.utils.get_build_version()
