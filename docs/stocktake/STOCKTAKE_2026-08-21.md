# Repo & Deployment Stock-Take — 2026-08-21

**Scope:** local dev machine, GitHub, production server.
**Method:** read-only. No fetch, no commit, no push, no writes to the server, no changes to any branch.
**Purpose:** establish exactly where every line of work currently lives, before planning a merge.

---

## 1. Deploy pipeline — VERIFIED

Your assumed flow is correct and confirmed by evidence on both ends:

```
local dev (WSL bench)  --push-->  GitHub  --pull-->  production server
   remote: origin              BBbrighton/          remote: upstream
                             scrap_metal_suite
```

| Hop | Path | Remote name | URL |
|---|---|---|---|
| Local | `/home/brighton/frappe-bench/apps/scrap_metal_suite` | `origin` | `https://github.com/BBbrighton/scrap_metal_suite.git` |
| GitHub | `BBbrighton/scrap_metal_suite` | — | public repo |
| Server | `/home/taynaja/frappe-bench/apps/scrap_metal_suite` | `upstream` | `https://github.com/BBbrighton/scrap_metal_suite` |

**Same repository, two different remote names** — `origin` locally, `upstream` on the server. That is the most confusing thing about this setup day-to-day, but it is intentional and it works.

**Proof the pipeline is intact:** all three agree on `develop` at the same commit.

```
local  origin/develop   9bad181
GitHub develop          9bad181
server develop          9bad181   (clean tree, describe = v1.1.0-8-g9bad181)
```

There is no drift between what is on GitHub and what is deployed. The server has no local commits and no uncommitted edits.

---

## 2. Production server — health

| Item | Value |
|---|---|
| Host | `178.128.84.100` — `ubuntu-s-2vcpu-4gb-sgp1-01`, DigitalOcean Singapore |
| OS | Ubuntu 24.04.2 LTS |
| Uptime | 368 days |
| Disk | 39 GB used / 77 GB (51%) |
| Memory | 3.8 GB total, **1.4 GB available** |
| Bench | `/home/taynaja/frappe-bench` — 7 sites |
| Site | `smt.x-desk.tech` → **HTTP 200** in 0.57 s |

**Sites on this bench:** `smt.x-desk.tech`, `tub.x-desk.tech`, `md.x-desk.tech`, `vp.x-desk.tech`, `x-desk.tech`, `site1.x-desk.tech`, `site2.x-desk.tech`

**Installed app versions on `smt.x-desk.tech`:**

```
frappe             15.74.1        scrap_metal_suite  1.1.0
erpnext            15.70.2        qr_foundry         2.1.0
erpnext_thailand   1.0.1          tub_suite          2.1.19
hrms               16.0.0-dev     builder            2.0.0-dev
document_foundry   1.0.0          huahin_suite       0.0.1
payments           0.0.1
```

**SSH access note:** the PuTTY key (`privkey.ppk`, saved session `X-desk_DigitalOcean`) authenticates **`root` only** — `taynaja` refuses it. Bench commands therefore have to go through `sudo -u taynaja`. Never run `bench` as root; it will scramble file ownership across the bench.

---

## 3. Branch inventory — the actual state

### GitHub (source of truth for what is shared)

| Branch | SHA | Last commit | Note |
|---|---|---|---|
| `master` | `8154680` | 2025-12-05 | **default branch**, 72 commits behind `develop`, version `0.0.1` |
| `develop` | `9bad181` | 2026-04-24 | real trunk, what production runs |
| `cam_integration_v0` | `4803c08` | **2026-08-17** | 1 commit ahead of develop — CCTV camera integration |

Tags: `v1.1.0` (annotated → `66edb41`), `v1.0.0-develop3-merged-2026-04-14`
Open PRs: **none**

### Local dev machine (WSL bench)

| Branch | SHA | vs develop | Upstream | Note |
|---|---|---|---|---|
| `develop` | `9bad181` | — | `origin/develop` | in sync |
| `feature/container-redesign` | `ce7a9d6` | **4 ahead** | **none** | **never pushed — exists only here** |
| `master` | `8154680` | 72 behind | `origin/develop` (wrong) | stale |
| `origin` | `9bad181` | — | none | **stray branch literally named "origin"** |

Working tree: clean except untracked `.claude/settings.json`. No stash.
Last fetch: **2026-07-18** — so this machine has never seen `cam_integration_v0`.

### Production server

Only `develop` exists. Clean. Last fetch 2026-04-24.

---

## 4. Where the work actually lives — the core problem

Three bodies of work, in three places, and **no two of them are aware of each other**:

```
                    develop @ 9bad181  (2026-04-24, deployed, v1.1.0)
                            |
            +---------------+---------------+
            |                               |
  feature/container-redesign      cam_integration_v0
  ce7a9d6  (2026-07-18)           4803c08  (2026-08-17)
  4 commits, 94 files             1 commit, 19 files
  +13,777 / -384 lines            CCTV camera integration
  LOCAL MACHINE ONLY              GITHUB ONLY
```

Both fork cleanly from `develop` and both are **0 commits behind** it, so neither has drifted off a stale base. That is the good news — the merge starts from a clean three-way position.

### `feature/container-redesign` — 4 commits, local only

```
ce7a9d6  Add end-to-end test suite + headed demo for receiving flow
ab64ef6  wip: sync to other machine (unwind with git reset --soft HEAD~1)
773f775  Container redesign Waves 6-8: relocation, print finalization, naming series
8cca2f3  Add Container model: replace Scrap Weight with per-bag Scrap Weight Container
```

94 files, +13,777 / −384. This is the Container redesign (Waves 6–11) plus the full E2E test suite.

### `cam_integration_v0` — 1 commit, GitHub only

`4803c08 feat: Rebuild CCTV camera integration with local capture agent` — pushed 2026-08-17 from a different machine.

19 files: new `Camera` DocType, `api/v1/camera.py`, `camera/service.py`, a standalone `agent/smt_camera_agent.py` capture agent, `camera_client.js`, a `www/camera-test/` page, and a 719-line `docs/CAMERA_INTEGRATION_HANDOFF.md`.

---

## 5. Findings, by severity

**HIGH — the container redesign has no backup.**
`feature/container-redesign` is 4 commits and ~13.7k lines that exist on exactly one disk. It is not on GitHub and not on the server. A machine failure loses months of work. This is the most urgent item and it is fixable in one push.

**HIGH — the public default branch is stale.**
The repo is **public** and its default branch is `master`, last touched 2025-12-05, 72 commits behind, still declaring version `0.0.1`. Anyone landing on the repo sees an eight-month-old snapshot. `develop` is the real trunk.

**MEDIUM — two machines are diverging silently.**
Work from another machine (`cam_integration_v0`, Aug 17) has never been fetched here; work from here (the feature branch) has never been pushed. The commit message `ab64ef6 wip: sync to other machine` shows this has already bitten once.

**MEDIUM — both clones are behind GitHub.**
Local last fetched 2026-07-18, server last fetched 2026-04-24. GitHub last received a push 2026-08-17.

**LOW — `master` has the wrong upstream.**
Local `master` tracks `origin/develop`. A `git pull` while on `master` would drag `develop` into it.

**LOW — stray branch named `origin`.**
A local branch is literally named `origin`, which collides conceptually with the remote name. `git log origin` is now ambiguous with `origin/develop`. Almost certainly an accidental `git branch origin`.

**LOW — version string never moved.**
Both `develop` and `feature/container-redesign` declare `1.1.0`. The feature branch adds an entire subsystem without a version bump.

---

## 6. Merge inputs — conflict surface

Both branches fork from the same clean base. Overlap is **only two files**:

| File | `feature/container-redesign` | `cam_integration_v0` | Risk |
|---|---|---|---|
| `scrap_metal_suite/public/css/pos.css` | +595 (pure additions) | 36 changed | **Low** — feature appends, cam edits existing rules |
| `scrap_metal_suite/www/pos/truck.html` | 24 changed (10 del) | 429 changed | **Moderate** — cam substantially rewrites the file |

The other 111 files are fully disjoint. `CLAUDE.md` is touched by the cam branch only.

A merge should be tractable. `truck.html` is the one file that needs a careful, hand-read resolution.

---

## 7. Agreed plan (decided 2026-08-21)

**Production goes from v1.1.0 to a single new version containing BOTH the cam integration and the container redesign.** No intermediate deploy of one without the other. The container redesign is a breaking data-model change with a migration patch; running that cutover twice doubles the risk for no benefit.

**Everything below is gated on the container design being finished first.** The merge does not start mid-Wave.

| # | Step | Notes |
|---|---|---|
| 0 | **Finish the container design** | gate for all of the below |
| 1 | Push `feature/container-redesign` to GitHub | backup only — merges nothing, touches no server |
| 2 | Fetch + merge `cam_integration_v0` into the container branch | confirm the cam branch is finished first |
| 3 | Prove the **merged** tree green locally | green container tests + green cam tests ≠ green merged tree |
| 4 | Migration dry-run on a **production snapshot** | the real gate — see below |
| 5 | Version bump + tag | `2.0.0` is the honest choice for a breaking model change |
| 6 | Deploy as one release | backup → pull → migrate → build → clear-cache → restart, as `taynaja` |

### The testing gate — code is replaced, data is not

`bench migrate` on production runs `patches/v2_0/migrate_to_containers.py` against a year of real Scrap Weight rows that have drifted into shapes no local fixture has ever produced. Local suites passing does not answer whether that migration is correct. **Only a restored production backup can.**

This is already designed — see `DROPOFF_CONTAINER_REDESIGN.md` §10 (migration algorithm), §10.4 (rollback via the `use_container_model` flag), §10.6 (pre-migration duplicate report), §11.4 (staging test), and the patch itself, registered in `patches.txt`. Nothing new needs writing. What is missing is **execution against real data** — the three PENDING items under Phase 8:

- [ ] Dry-run on staging (production snapshot)
- [ ] Verify post-migration aggregate kg matches pre-migration truck net per supplier
- [ ] Spot-check 20+ dropoffs manually

Those are the deploy gate, not the unit/integration suites.

---

## 8. Still open — decide at the merge session

1. **Merge order** — container-first preferred, so `truck.html` is resolved once against a settled base.
2. **Is `cam_integration_v0` finished**, or still moving on the other machine? Merging a moving branch is worse than waiting.
3. **Does `master` still mean anything?** If not, make `develop` the GitHub default and either delete `master` or reset it to `develop`. The repo is public and `master` is the current default.
4. **Deploy timing** — the server has 1.4 GB RAM available across 7 sites. A `migrate` + `build` of this size wants a quiet window and a verified backup.
5. **Local junk** — delete the stray `origin` branch; fix `master`'s upstream (it wrongly tracks `origin/develop`).
6. **Asset cache-busting before deploy** — the terminal pages hand-link `/assets/...` with no version, served `Cache-Control: max-age=43200`. Floor terminals can therefore run **12-hour-stale JS against a new API** after a deploy, and no server-side command can dislodge it (`bench clear-cache` and `bench build` clear server state, not the browser's HTTP cache). `pos/terminal.html` is fixed; six pages plus cam's `camera-test/` still need it. See `DROPOFF_CONTAINER_REDESIGN.md` §14.23.

---

## Appendix — evidence trail

Commands used, all read-only:

- Server: `plink -load 'X-desk_DigitalOcean' -l root -batch "sudo -u taynaja git -C <repo> ..."`
- GitHub: `gh api repos/BBbrighton/scrap_metal_suite/...`, `git ls-remote` (no local ref mutation)
- Local: `git branch -vv`, `git rev-list --left-right --count`, `git diff --stat`

Local bench sites present: `metal` (dev), `huahin`, `huahin.localhost`, `localhost`, `md-metal`, `salon`, `tub`, `vp`, `worldcontainer`.

No other clone of `scrap_metal_suite` exists on this machine outside the bench.
