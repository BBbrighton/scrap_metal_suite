# One-off diagnostics

Scripts written to answer a single question during development and kept for
reference. **They are deliberately outside the `scrap_metal_suite` package**, so
`bench execute scrap_metal_suite.api_test.<name>` cannot reach them and nobody
runs one by accident on a production box. Several mutate data.

Nothing in the app, the docs, or the deploy runbook references any of these — that
is the test they had to pass to be moved here. The tools that *are* referenced
stayed in `scrap_metal_suite/api_test/`:

| Still in `api_test/` | Cited by |
|---|---|
| `_e2e_walkthrough.py` | `docs/E2E_TESTING_OVERVIEW.md`, admin guide 20 |
| `_patch_print_format.py` | admin guides 11, 12 |
| `_patch_sticker.py` | `docs/DROPOFF_CONTAINER_REDESIGN.md` |
| `_release_stuck_scales.py` | **admin guide 60 (deploy runbook)**, guide 50 |
| `_render_dropoff_thermal.py` | admin guide 40 |
| `_sync_print_formats.py` | **admin guide 60 (deploy runbook)**, guides 40, 90 |

To run something from here, copy it into the app first, or paste it into
`bench --site <site> console`.
