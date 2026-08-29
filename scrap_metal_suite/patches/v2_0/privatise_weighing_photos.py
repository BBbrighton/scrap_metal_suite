"""Move weighing photos out of the publicly served files directory.

Every photo the system has ever taken was created with `is_private = 0`. Frappe
serves those straight from nginx under `/files/` with no permission check of any
kind - no session, no cookie, no role. Anyone holding the URL could fetch the
full image, and there was no record that they had.

The images show licence plates, drivers' and workers' faces, weight readings and
supplier activity. Plates and faces are personal data under Thailand's PDPA.

Filenames offered some obscurity but not protection, and unevenly: the CCTV
names end in an 8-character digest, while `scrap_photo_WGT-2026-00001_1_<epoch
ms>.jpg` carries a sequential document number and a small index, leaving only the
millisecond to guess. More to the point, any URL that leaked - a forwarded
screenshot, browser history, a referrer header - stayed live forever.

Setting `is_private` through the document (not `db_set`) makes Frappe's
`handle_is_private_changed` move the file on disk and rewrite `file_url`.
Nothing renders these through a print format, so no PDF depends on the old URL;
the terminals show them via `<img>` in a logged-in browser, which sends the
session cookie and passes the permission check.

Idempotent: files already private are skipped. Safe to re-run.
"""

import os

import frappe

# Every prefix the system has ever written a weighing photo under. The last two
# come from the terminals calling Frappe's own upload_file endpoint, which is
# why they do not share the naming of the two the app builds itself.
PHOTO_PREFIXES = (
    "cctv_",
    "scrap_photo_",
    "truck_photo_",
    "truck_weight_",
)


def execute():
    conditions = " OR ".join(["file_name LIKE %s"] * len(PHOTO_PREFIXES))
    names = frappe.db.sql(
        """
        SELECT name, file_name FROM `tabFile`
        WHERE is_private = 0 AND ({0})
        """.format(conditions),
        tuple(p + "%" for p in PHOTO_PREFIXES),
        as_dict=True,
    )

    if not names:
        print("  no public weighing photos - nothing to do")
        return

    moved = skipped = failed = 0

    for row in names:
        # handle_is_private_changed throws if the source file is not on disk.
        # A File row whose bytes are already gone is a pre-existing problem and
        # not this patch's to solve - flag it and carry on, rather than letting
        # one orphan abort the whole migration.
        public_path = frappe.get_site_path("public", "files", row.file_name)
        if not os.path.exists(public_path):
            print("  skip (file missing on disk): {0}".format(row.file_name))
            skipped += 1
            continue

        try:
            doc = frappe.get_doc("File", row.name)
            doc.is_private = 1
            doc.save(ignore_permissions=True)
            moved += 1
        except Exception as e:  # noqa: BLE001 - one bad row must not stop the rest
            print("  FAILED {0}: {1}".format(row.file_name, e))
            failed += 1

    frappe.db.commit()
    print("  privatised {0} photo(s), skipped {1}, failed {2}".format(moved, skipped, failed))

    if failed:
        print("  re-run this patch after investigating the failures above")
