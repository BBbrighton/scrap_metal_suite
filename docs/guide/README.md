# Scrap Metal Suite — Documentation

Two tiers, one per audience. Start with whichever describes you.

| I am… | Read | Language |
|---|---|---|
| A yard operator, weighing bags or trucks | **[user/](user/)** | ไทย + English |
| Office staff pricing and settling | **[user/30-settlement.md](user/30-settlement.md)** | ไทย + English |
| A developer, maintainer, or system admin | **[admin/](admin/)** | English |

---

## User guide — คู่มือผู้ใช้งาน

Task-shaped. Every module has numbered walkthroughs with real values and what appears on screen after each step.

| # | Guide | Covers |
|---|---|---|
| 00 | [Start here](user/00-start-here.md) | How the yard flow fits together, logging in, shared UI |
| 01 | [Adding Items to the Screen](user/01-adding-items-to-the-screen.md) | Office: the two places that decide which grade buttons appear |
| 10 | [POS Scrap Terminal](user/10-pos-scrap-terminal.md) | Sessions, scales, the weighing screen |
| 11 | [Truck Terminal](user/11-truck-terminal.md) | Weighbridge: gross, tare, net, reweigh |
| 12 | [Drop-off & Container Weighing](user/12-dropoff-receiving.md) | The core receiving flow, bag by bag |
| 13 | [Scheduling a Drop-off](user/13-scheduling-a-dropoff.md) | Office: turning a POS Order into a Dropoff the yard can weigh |
| 20 | [Production Sorting](user/20-production-sorting.md) | QA/QC grading after receiving |
| 30 | [Price Lock & Settlement](user/30-settlement.md) | Quoting, purchase orders, final money |
| 40 | [Printing & Labels](user/40-printing.md) | Receipts, stickers, QR codes |
| 80 | [Portals (Preview)](user/80-portals-preview.md) | ⚠️ **Not production-ready** |
| 90 | [Troubleshooting](user/90-troubleshooting.md) | Symptom → cause → fix, across all modules |

## Developer & admin guide

Reference-shaped. Data models, state machines, API contracts, failure modes.

| # | Reference | Covers |
|---|---|---|
| 00 | [Architecture](admin/00-architecture.md) | System map, module boundaries, tech stack |
| 01 | [Master Data & Setup](admin/01-master-data-and-setup.md) | Everything a human must enter in the desk, in order, and which settings actually take effect |
| 10 | [POS Scrap Terminal](admin/10-pos-scrap-terminal.md) | Sessions, profiles, scale hardware |
| 11 | [Truck Terminal](admin/11-truck-terminal.md) | Weighbridge, variance, serial protocols |
| 12 | [Drop-off & Containers](admin/12-dropoff-receiving.md) | Core data model, immutability, allocation |
| 20 | [Production Sorting](admin/20-production-sorting.md) | Sorting model, variance, verification |
| 30 | [Settlement](admin/30-settlement.md) | Price locks, POs, allocation algorithm |
| 40 | [Print Formats & Bilingual](admin/40-printing.md) | Formats, QR, thermal rules, i18n |
| 50 | [Platform, Roles & Scheduler](admin/50-platform-roles-scheduler.md) | hooks, permissions, cron, patches |
| 60 | [Deployment & Operations](admin/60-deployment-operations.md) | Install, deploy, backup, runbook |
| 70 | [Testing](admin/70-testing.md) | Every suite and how to run it |
| 80 | [Portals internals](admin/80-portals-internals.md) | ⚠️ **Incomplete module** |
| 90 | [Extending this app](admin/90-extending-this-app.md) | Adding a module — code *and* docs |

---

## Conventions

**Status banners.** Every document declares its maturity at the top:

> **Status:** Production — shipped, in daily use
> **Status:** ⚠️ NOT PRODUCTION-READY — exists in code, incomplete

**Verification marks.** Anything the author could not confirm against running code is tagged inline:

> ⚠️ UNVERIFIED — *reason*

Treat an unmarked claim as verified against source at the time of writing. Treat a marked one as a lead.

**Item names are never translated.** Item names are canonical Thai (`ทองแดงปอก`, `อลูมิเนียมฉาก`). They are the identifier, not a label. Rendering an English "equivalent" invents an alias that exists nowhere else in the system, breaks search, and risks the wrong grade being paid out. This rule holds in the UI, in print, in error messages, and in every example in these documents. See [BILINGUAL_GUIDE.md](../BILINGUAL_GUIDE.md).

**Numbering.** The leading number groups related modules and keeps user/ and admin/ mirrored: `12-dropoff-receiving.md` exists in both, covering the same subsystem at two depths. Gaps in the sequence are deliberate — they leave room to insert without renumbering.

| Range | Reserved for |
|---|---|
| 00–09 | Orientation, architecture |
| 10–19 | Receiving: terminals, scales, drop-offs |
| 20–29 | Production: sorting, grading |
| 30–39 | Commercial: pricing, settlement |
| 40–49 | Cross-cutting: printing, i18n |
| 50–79 | Platform (admin only): roles, deploy, testing |
| 80–89 | Preview / incomplete modules |
| 90–99 | Troubleshooting, extension guides |

---

## Keeping this current

These documents are expected to drift. The structure is designed so that a new module is an *addition*, not a rewrite:

1. Copy [TEMPLATE-user.md](TEMPLATE-user.md) → `user/NN-<module>.md`
2. Copy [TEMPLATE-admin.md](TEMPLATE-admin.md) → `admin/NN-<module>.md`
3. Add two rows to the tables above
4. Follow the checklist in [admin/90-extending-this-app.md](admin/90-extending-this-app.md)

Nothing else needs touching. No shared file has to be restructured, and no other document has to be renumbered.

**When code changes, the doc that describes it changes in the same commit.** A guide that lies is worse than no guide — the reader trusts it and acts on it. If you cannot verify a claim while updating, mark it UNVERIFIED rather than leaving it looking confirmed.

---

## Related documents

Design history and working notes live outside this guide. They record *why* decisions were made and are not maintained as user-facing reference:

- [DROPOFF_CONTAINER_REDESIGN.md](../DROPOFF_CONTAINER_REDESIGN.md) — the container redesign log (current, but a design journal)
- [PRICE_LOCK_SETTLEMENT_DESIGN.md](../PRICE_LOCK_SETTLEMENT_DESIGN.md) — settlement design
- [UI_TERMINAL_UNIFORMITY_PLAN.md](../UI_TERMINAL_UNIFORMITY_PLAN.md) — terminal CSS/JS unification plan
- [THERMAL_PRINT_GUIDE.md](../THERMAL_PRINT_GUIDE.md) — thermal print rules
- [BILINGUAL_GUIDE.md](../BILINGUAL_GUIDE.md) — translation rules and terminology
- [E2E_TESTING_OVERVIEW.md](../E2E_TESTING_OVERVIEW.md) — test strategy
- [stocktake/](../stocktake/) — point-in-time repo and environment surveys

Older files in `docs/` (`DROPOFF_ARCHITECTURE.md`, `PHASE_8_DROPOFF_REDESIGN.md`, `USER_MANUAL.md`, `USER_GUIDE_V2*.md`, the `POS_*_GUIDE_TH*` set) predate the container redesign. **They are historical.** Where they disagree with this guide, this guide is right.
