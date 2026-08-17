# CCTV Camera Integration — Deployment & Handoff

**Module:** Hikvision CCTV capture for the POS weighing terminals
**App:** `scrap_metal_suite`
**Status:** Rebuilt and verified against real hardware (2026-08-17). Not yet deployed to production.
**Branch:** `cam_integration_v0`
**Scope of this document:** everything the next person needs to deploy this,
extend it, and recognise every way we know it can break.

> **History:** this module was originally built in July 2026 but was never
> committed, and the working tree was lost in a Windows reformat. It was rebuilt
> from the surviving design docs on 2026-08-17. That is why it arrives as one
> commit with no incremental history.

Design background lives in the Windows docs folder
(`smt_claude_md/02_architecture/CAMERA_INTEGRATION.md`,
`smt_claude_md/04_design_plans/CAMERA_CAPTURE_AGENT_DESIGN.md`). Those are
excluded from this repo by `.gitignore` (`*_DESIGN.md`), so they will not arrive
with a `git pull`. **Ask for them if you need the original design rationale** —
this document is self-contained for deploying and extending, but those two cover
*why* the architecture is shaped this way.

---

## 0. Start here

If you have just pulled this branch, read in this order:

1. **§1** — what the module does and the two transports. Ten minutes; without it
   the rest will not make sense, because almost every gotcha is transport-specific.
2. **§3** — three things that are *not* in git. **The permission fix in §3.1 is
   mandatory and fixes a bug that exists on production today, cameras or not.**
3. **§4** — deployment order, and how to verify the cameras work.
4. **§5** — 25 known failure modes, grouped by symptom. Skim now, return when
   something misbehaves.
5. **§6** — what is verified versus what is not, so you know what to trust.
6. **§9** — **read this first if the cameras have been shipped to you** and you
   are wiring the hardware up from scratch. Credentials are deliberately not in
   this repo; §9.1 explains where to get them.

**To get it running locally**, fastest path:

```bash
bench --site <site> migrate            # creates the Camera table
bench build --app scrap_metal_suite
bench --site <site> clear-cache
# apply §3.1 permissions, create Camera records per §3.2
# then open /camera-test and press "Test All"
```

`/camera-test` is the single best diagnostic and needs no POS session, no
dropoff, and no weighing. Start there.

**The code is organised so the backend is reusable.** `camera/service.py` is
transport- and terminal-agnostic; `api/v1/camera.py` is thin wrappers over it.
Phase 2 (scrap terminal) and Phase 3 (production terminal) need no backend work
at all — see §8.

---

## 1. What it does

Saving a Gross or Tare weight on the truck terminal auto-captures a still from
every active truck camera, attaches it to that Truck Weight, then shows the
operator the photos and waits for confirmation before the ticket prints
(see §1.1).

Two transports feed one storage path. **Terminal code is identical either way** —
`CameraClient` picks the transport from its `agentUrl` option:

| Transport | Who fetches the JPEG | Use when |
|---|---|---|
| **Backend fetch** | The Frappe backend (`camera/service.py`) | Dev / on-prem — the server is on the camera LAN |
| **Local agent** | An agent on the on-site PC (`agent/`) | **Cloud prod** — the cloud cannot reach the LAN |

```
Cloud (agent) mode:
  browser ──HTTP localhost──▶ agent ──Digest GET (LAN)──▶ cameras
                                │ JPEG
                                ▼  REST + API token
                     api/v1/camera.receive_weight_photo  ──▶ File + Weight Photo
```

Why an agent is unavoidable: browsers cannot fetch a Hikvision snapshot (Digest
auth, no CORS, HTTPS mixed content), and the DigitalOcean server has no route to
`192.168.1.x`. Same shape as the scale — read hardware locally, send the result.

### 1.1 Terminal flow (changed 2026-08-17)

```
enter weight → Save Weight → existing confirm modal → weight COMMITTED
                                                           │
                                              cameras capture automatically
                                                           ▼
                                      ┌────────────────────────────────┐
                                      │ ✔ Weight Recorded              │
                                      │   12,340.00 Kg — Gross         │
                                      │   2 photo(s) captured          │
                                      │  [ photo ]      [ photo ]      │
                                      │  TRUCK-CAM-01  TRUCK-CAM-02    │
                                      │   🔄 Recapture Weight          │
                                      │   🖨 Confirm & Print            │
                                      └────────────────────────────────┘
```

Three design rules here, all load-bearing:

- **The weight is committed before this modal appears.** A camera failure can
  never undo a weigh. If capture fails the modal still opens, shows a warning,
  and *Confirm & Print* still works — you never lose the ability to print a
  ticket because a camera is down.
- **Printing is gated, weighing is not.** `printTruckWeight()` used to fire
  automatically inside `saveWeightByType()`. It now runs only from
  `confirmWeighAndPrint()`.
- **Only the photos from *this* capture are shown.** The modal snapshots which
  `Weight Photo` rows existed before capturing and displays the difference, so a
  reweigh does not re-present earlier photos. Earlier rows stay on the record.

*Recapture Weight* returns the operator to the weight input. It does **not**
delete anything — saving again goes through the existing reweigh path, which
requires a reason and stamps `is_reweight`, keeping the audit trail intact.

The old **📷 Photo** (device webcam) and **📹 CCTV** (manual per-camera capture)
buttons were **removed** from the terminal on request, along with the CCTV modal
and its four functions. The webcam `photoModal` and its helpers
(`openPhotoCapture`, `saveAllPhotos`, `updatePhotoThumbnails`, `b64toBlob`, the
zoom/tilt controls) are **still present in `truck.html` but unreachable** — left
in deliberately rather than risk a wide deletion. Removing them is a safe
follow-up cleanup.

The 📹 **camera badge in the header remains** — it is a status indicator and the
route to `/camera-test`, not a capture control.

### 1.2 Where photos are stored, and how they are named

Every capture produces **one file and two records**:

1. A Frappe **`File`** record (public), written to
   `sites/<site>/public/files/` and served at `/files/<name>`. It is attached to
   the parent Truck Weight, so it also appears in that document's attachments.
2. A **`Weight Photo`** child row on the Truck Weight, holding the photo URL,
   filename, `captured_at` (server time), `weight_type`, `dropoff` and `session`.

In cloud/agent mode the file is written on the **server**, not the weighbridge
PC. The agent keeps no local copy — which is also why a permanently failed
upload loses that photo (§5.4 item 17).

**Filename pattern:**

```
cctv_20260817_145959_truck-cam-01_truck-gross_6d3ec6c8.jpg
     └──date──┘└time┘ └──camera───┘└─weight type┘ └─hash─┘
```

The leading `YYYYMMDD_HHMMSS` is deliberate: a plain directory listing sorts
chronologically, so **backups and retention cleanups can be scoped by date
without querying the database**:

```bash
ls  public/files/cctv_20260817_*                     # one day
ls  public/files/cctv_*_truck-cam-01_*               # one camera
find public/files -name 'cctv_2026*' ! -newermt '2026-06-01'   # older than a date
```

Timestamps come from `now_datetime()` (server time), so they match
`Weight Photo.captured_at` and are unaffected by the camera clocks.

The trailing 8-char SHA1 of the content keeps names unique and makes identical
frames visible — repeated hashes are a useful hint that a camera is serving a
frozen image.

Fields are separated by `_`; `_slug()` converts everything non-alphanumeric to
`-`, so no field can contain an underscore. That keeps the five fields reliably
splittable.

**Two older patterns exist in the data** and are not migrated — the URLs are
referenced from `Weight Photo` rows, so renaming would break them:

| Origin | Pattern |
|---|---|
| current CCTV | `cctv_<date>_<time>_<camera>_<type>_<hash>.jpg` |
| early CCTV (test data, Aug 2026) | `cctv_<camera>_<type>_<hash>.jpg` — no date |
| device webcam (historical) | `truck_photo_<TW>_<n>_<epoch_ms>.jpg` |

---

## 2. File manifest (what arrives with a pull)

```
scrap_metal_suite/
├── camera/
│   ├── __init__.py
│   └── service.py                      # reusable backend library
├── api/v1/camera.py                    # whitelisted endpoints + agent upload
├── agent/
│   ├── smt_camera_agent.py             # on-site local service (Python → .exe)
│   ├── config.example.json             # config template
│   └── README.md                       # agent setup / build / autostart
├── scrap_metal_suite/doctype/camera/
│   ├── camera.json                     #   Camera doctype
│   ├── camera.py                       #   get_snapshot_url()
│   └── camera.js                       #   Test Connection / Live Frame buttons
├── public/js/camera_client.js          # frontend CameraClient (both transports)
├── public/js/pos-translations.js       # + CCTV / review EN+TH keys   (modified)
├── public/css/pos.css                  # + .partial dot, review grid  (modified)
├── www/camera-test/                    # /camera-test verification page
│   ├── index.html
│   └── index.py
└── www/pos/
    ├── truck.html                      # auto-capture, review modal, badge (modified)
    └── truck.py                        # reads camera_agent_url          (modified)
```

No changes to `hooks.py`, `dropoff.py`, or the `Weight Photo` doctype.

### Where to make changes

| Want to... | Touch |
|---|---|
| Add a camera vendor / change the snapshot URL | `doctype/camera/camera.py` → `get_snapshot_url()` |
| Change fetch, fallback or storage behaviour | `camera/service.py` |
| Add an endpoint | `api/v1/camera.py` (thin wrapper + `check_pos_operator()`) |
| Change browser behaviour, either transport | `public/js/camera_client.js` |
| Wire a new terminal (Phase 2/3) | that terminal's `.html` only — see §8 |
| Change agent behaviour or clock sync | `agent/smt_camera_agent.py` |

`camera/service.py` never imports terminal or request state, so it is safe to
call from a scheduler job or a patch.

---

## 3. ⚠️ Three things that are NOT in git

A `git pull` gives you code only. These are database records or site config and
**must be created in every environment**. Miss any one and the feature fails,
mostly with unhelpful errors.

### 3.1 `POS Operator` write permission on Truck Weight and Dropoff

**This is a live pre-existing bug on production, independent of cameras.**

`Truck Weight` and `Dropoff` have **Custom DocPerm** rows. In Frappe, Custom
DocPerms *replace* the standard doctype permissions wholesale. When `SMT Manager`
was added at some point via the Role Permission Manager, `POS Operator` was
dropped from both — but survived on `Scrap Weight`:

| Doctype | Standard write | Custom write (actually in force) |
|---|---|---|
| Scrap Weight | POS Operator, System Manager | **POS Operator**, SMT Manager, System Manager |
| Truck Weight | POS Operator, System Manager | ~~POS Operator~~ SMT Manager, System Manager |
| Dropoff | POS Operator, System Manager | ~~POS Operator~~ Production Manager, SMT Manager, System Manager |

Consequences for any user holding **only** `POS Operator`:

- Cannot **reweigh** a truck (`dropoff.py:409` does a plain `truck_weight.save()`)
- Cannot attach **any** photo to a Truck Weight — including via the existing
  webcam button (`save_weight_photo` → `parent.save()`)
- The *first* weigh works, because `dropoff.py:583` uses
  `insert(ignore_permissions=True)` — which is why this has gone unnoticed
- Saving a Truck Weight also cascades into `dropoff.save()` via
  `TruckWeight.on_update` → `update_dropoff_weight()`, so **Dropoff** write is
  required too

It is masked in testing because most operator accounts also hold `SMT Manager`.

Fix (run on each site):

```python
from frappe.permissions import add_permission, update_permission_property
for dt in ["Truck Weight", "Dropoff"]:
    add_permission(dt, "POS Operator", 0)
    for ptype in ("read", "write", "create"):
        update_permission_property(dt, "POS Operator", 0, ptype, 1)
frappe.db.commit()
frappe.clear_cache()
```

Verify: `frappe.set_user("<pure POS Operator user>")` then
`frappe.has_permission("Truck Weight", "write")` must be `True`.

> Applied on local `smt.local` on 2026-08-17. **Not yet applied on production.**

### 3.2 `Camera` records

Desk → **Camera** → New, one per camera:

| Field | Value |
|---|---|
| `camera_name` | e.g. `TRUCK-CAM-01` — **must exactly match** the agent's config `name` |
| `usage_type` | `Truck` |
| `is_active` | checked |
| `ip_address`, `channel` | `192.168.1.11`, `102` |
| `password` | **leave blank in cloud/agent mode** |

In agent mode the cloud never contacts the camera — `ip_address`, `username`
and `password` are labels only. Real credentials stay in the agent's local
`config.json`.

### 3.3 The `camera-agent` user and `camera_agent_url`

Create a dedicated user with the **`POS Operator`** role and nothing more.
Generate an API key + secret (User form → Settings → API Access).

> `receive_weight_photo` runs `check_pos_operator()` like every other POS
> endpoint. `POS Operator` is **required and sufficient** — given §3.1 is fixed.
> Do **not** grant System Manager. An earlier version of the agent README said
> "a role that can create File + Weight Photo"; that was wrong.

Then point the terminal at the agent:

```bash
bench --site smt.x-desk.tech set-config camera_agent_url "http://127.0.0.1:8787"
```

---

## 4. Deployment order

> Wiring up freshly shipped hardware? Do **§9** first, then come back here.

1. Apply §3.1 (permissions) — **do this first**, everything else 403s without it
2. `git pull` → `bench --site <site> migrate` (creates the `Camera` table)
3. `bench build --app scrap_metal_suite` → `clear-cache` → `bench restart`
4. Create the `Camera` records (§3.2)
5. Create the agent user + API keys, and `set-config camera_agent_url` (§3.3)
6. On the weighbridge PC: static IP, `config.json`, run the agent, autostart
   — see `agent/README.md`
7. Live test: `/pos/truck` → save Gross → expect a green `📷 (2)` badge and
   thumbnails → confirm both photos on the Truck Weight
8. **Reboot the PC and confirm the agent restarts by itself before leaving site**

Run git and bench on the server as **`taynaja`, never root** — root triggers the
dubious-ownership guard and can leave root-owned files in `.git/`.

### Verifying the cameras

Three places to check, mirroring how the scale is verified:

**1. `/camera-test`** — a standalone page modelled on `/scale-test`. Lists every
configured camera and, per camera, does a real fetch and reports the channel used,
payload size and pixel dimensions, plus a live preview toggle. In agent mode it
also shows the agent's `/health`: version, cloud reachability, pending uploads and
per-camera clock-sync results. This is the first thing to open when someone says
"the cameras aren't working" — it separates *camera unreachable* from
*agent down* from *cloud rejecting the upload*.

**2. The camera badge in the truck terminal header** — sits next to the scale
badge and behaves the same way: a coloured dot (green all reachable, amber some,
red none) with the camera count. Its menu offers *Test Cameras* and a link to
`/camera-test`. Hidden entirely when no cameras are configured.

**3. Desk → Camera form** — *Test Connection* and *Live Frame* buttons on each
record. `Test Connection` reports the channel and size, and says explicitly when
it fell back to the sub-stream. The form also warns when a camera is inactive, or
when it has no password (expected in cloud mode, but it means the server itself
cannot fetch that camera).

Note what each layer proves. `/camera-test` and the Desk buttons exercise
whichever transport the site is configured for. In cloud production that is the
**agent**, so a green result there means the whole chain works. In dev with
`camera_agent_url` unset, it only proves the *server* can reach the cameras.

---

## 5. Things that might break

Grouped by where they bite. Each has a symptom you can actually recognise.

### 5.1 Configuration — silent or misleading failures

| # | Problem | Symptom | Fix |
|---|---|---|---|
| 1 | **`camera_agent_url` not set** on the cloud site | Every weigh hangs for ~10s then photos fail — the cloud is trying to reach `192.168.1.x` itself | `set-config camera_agent_url`. Highest-value line in the deployment. |
| 2 | **Camera name mismatch** between the `Camera` doctype and the agent's `config.json` | Camera missing from the modal dropdown; console warns `registry cameras the agent cannot reach` / `agent cameras not in the cloud registry` | Make the names identical. The client logs both directions of mismatch on load. |
| 3 | **Agent user lacks `POS Operator`** | Agent logs `cloud HTTP 403`; weight saves, photos silently absent | Grant exactly `POS Operator` |
| 4 | **§3.1 permissions not applied** | `PermissionError: No permission for Truck Weight` (or `Dropoff`) in the agent log | Apply §3.1 |
| 5 | **Cloud `Camera` record has a password set** in agent mode | Nothing breaks, but a stale credential is stored server-side | Leave it blank |

### 5.2 Network

| # | Problem | Symptom | Fix |
|---|---|---|---|
| 6 | **Switch has no DHCP** | PC's NIC self-assigns `169.254.x.x`; nothing reachable | Static IP, e.g. `192.168.1.50/24`, **gateway blank** — setting a gateway can hijack the default route and kill internet |
| 7 | **Trusting SADP** | SADP lists both cameras, yet nothing works | SADP discovers by *broadcast*; it works across subnets where routing does not. Prove with a real `curl --digest` to a snapshot URL. |
| 8 | **Wrong adapter configured** | Static IP set, still unreachable | Confirm which NIC is on the camera switch (`Get-NetAdapter`); a USB dongle often appears as `Ethernet 2`, not `Ethernet` |
| 9 | **Cameras re-addressed** | Ping fails on `.11`/`.12` | Check the IPs SADP actually reports |

### 5.3 Camera hardware quirks

| # | Problem | Symptom | Status |
|---|---|---|---|
| 10 | **`.12` returns HTTP 503 on channel 101** | Nothing — handled | **By firmware, permanent.** `capture_bytes` tries 101 then falls back to the configured sub-stream. Confirmed live: `.12` only ever serves 102. Photos from `.12` are therefore lower-res (768×432). |
| 11 | **Hikvision web UI locks channel 101** | Confusing partial failure on `.11` | Close the camera's browser UI before testing |
| 12 | **Camera clocks reset on every power cycle** | Burned-in OSD reads `01-02-2000` | **Handled by the agent** — see below. If the OSD date is ever wrong again, check `/health` → `clock_sync` and that `sync_camera_clocks` is `true`. |
| 13 | **Both cameras' OSD name is `Camera 01`** | Two photos on one Truck Weight, indistinguishable by eye | ⚠️ **Currently true.** Filenames do distinguish them (`cctv_truck-cam-01_…`). Rename `.12`'s overlay to `Camera 02`. |
| 14 | `.11` mounted rotated | Image is 90° off | Mounting, not software |

#### Why the agent sets the camera clocks

These units have **no battery-backed RTC** and ship with `timeMode = manual`, so
the clock resets to `2000-01-02` on every power cycle — the clock runs correctly
while powered, it just restarts from the wrong epoch. Setting it by hand holds
only until the next power blip, then silently reverts.

NTP can't fix it in this topology: the camera LAN has no gateway, so the
factory-configured `time.windows.com` is unreachable. Both cameras do list it,
but `timeMode = manual` ignores NTP entirely.

The agent therefore `PUT`s the PC's local time to `/ISAPI/System/time` on
startup and every `clock_sync_interval_hours` (default 6). It reads and preserves
each camera's existing `timeZone`. Since the agent autostarts on login, the
clocks self-correct after every power cycle with no on-site action.

Verified 2026-08-17: both cameras went from `2000-01-02T07:38` to the correct
`2026-08-17T13:52`, timezone preserved, and a fresh capture's OSD read
`08-17-2026 Mon 13:52:38`.

The alternative — a local NTP server on the weighbridge PC with the cameras set
to `timeMode = NTP` — is more conventional and would survive the agent being
absent. It needs `w32time` enabled as a *server* on Windows (registry change plus
a UDP 123 firewall rule). Set `sync_camera_clocks: false` if you go that way.

`Weight Photo.captured_at` uses server time and was never affected — this only
concerns the timestamp drawn into the image.

### 5.4 Data fidelity — know before promising "photo evidence"

| # | Problem | Detail |
|---|---|---|
| 15 | **Frappe re-encodes every JPEG** | `File.save()` calls `strip_exif_data()` on any `image/jpeg` (`frappe/core/doctype/file/file.py:676`), decoding and re-encoding via PIL. Stored bytes are **not** the camera's original — a 15,906-byte snapshot came back 25,672 bytes, same dimensions, not pixel-identical. Site-wide Frappe behaviour; affects the existing webcam photos identically. Changing it means overriding Frappe. |
| 16 | **`Weight Photo.parent_doc` is always NULL** | Frappe uses `parent_doc` as an internal kwarg, so the custom field of that name never persists. True for every pre-existing row too. Harmless — builtin `parent` holds the record name and `parenttype` the doctype — but do not rely on `parent_doc`. |
| 17 | **No retry queue durability** | Failed cloud uploads retry 5× with exponential backoff from 30s, but the queue is **in-memory and bounded** (`retry_queue_size`, default 50). An agent restart drops anything pending. Both the drop and the give-up are logged as errors. Watch for `Giving up on upload` in `smt-camera-agent.log`. |
| 18 | **Auto-capture fires on every weigh** | Including reweighs, so a Truck Weight can accumulate several photos per weight type. Intended, but the count grows. The review modal shows only the newest capture (§1.1), so the growth is invisible in the terminal — check the Truck Weight record itself. |

### 5.5 Browser / transport

| # | Problem | Symptom | Fix |
|---|---|---|---|
| 19 | **Private Network Access** | HTTPS page calling `http://127.0.0.1` blocked by the browser | The agent returns `Access-Control-Allow-Private-Network: true` on preflight. If a future Chrome tightens PNA further this is the first thing to check. |
| 20 | **CORS origin mismatch** | Preflight fails | `allowed_origin` in `config.json` must be the exact site origin |
| 21 | **`ignore_csrf` must not ship** | — | Dev-only setting on `smt.local`. The agent uses token auth and does not need it. Never set on production. |
| 22 | **Agent down** | Terminal warns "capture agent offline"; **weight still saves** | By design — capture is not on the weighing critical path. Verify by killing the agent mid-session and saving a weight. |

### 5.6 Dev-environment gotchas

| # | Problem | Symptom | Fix |
|---|---|---|---|
| 23 | **`smt.local` missing from the hosts file** | Browser can't reach the site; `localhost:8000` returns 404 | Add `127.0.0.1 smt.local` to `C:\Windows\System32\drivers\etc\hosts` (Windows) and `/etc/hosts` (WSL, if the agent runs there). Frappe routes by Host header and `serve_default_site` is off, so `localhost` cannot match a site. **A Windows reformat wipes this.** |
| 24 | **Restored dev DB encryption key mismatch** | `get_password` fails on records encrypted before the restore | Re-enter the password on affected records. Freshly created `Camera` passwords are fine. |
| 25 | **PyInstaller build on site** | No internet on the weighbridge PC | Build the `.exe` at the desk. First run trips SmartScreen and a Windows Firewall prompt — meet both before travelling. |

---

## 6. Verification status

**Verified on 2026-08-17** against the real cameras (`192.168.1.11`, `192.168.1.12`):

- Agent against mocked cameras + cloud: 28/28 — real Digest handshake,
  101→102 fallback, PNA/CORS headers, retry-queue behaviour, non-blocking failure
- Frappe layer: 40/40 — doctype, encrypted password round-trip, service
  functions, all five endpoints, base64 and `data:` URI handling, bad-input rejection
- Live cameras through Frappe: 22/22 — `test_connection`, `capture_bytes`
  channel selection, `live_frame`, real end-to-end capture and storage
- `receive_weight_photo` over HTTP with token auth as a **`POS Operator`-only**
  user → File + Weight Photo row
- **Full production chain**: real agent → real cameras → real Frappe site,
  `{ok: 2, fail: 0}`, both channels correct
- **Clock sync**: both cameras corrected from `2000-01-02T07:38` to
  `2026-08-17T13:52`, timezone preserved, and a fresh capture's OSD read
  `08-17-2026 Mon 13:52:38`
- **Filename convention**: verified parseable and chronologically sortable
  against real captures
- `/camera-test` and `/pos/truck` render HTTP 200 with no template errors

**Hardware findings confirmed against the real units:**

- `.12` genuinely returns **HTTP 503 on channel 101** and only serves 102 — the
  fallback is load-bearing, not defensive
- `.11` serves both: 101 at 2560×1440 (~285 KB), 102 at 640×360
- Neither camera has a working RTC (§5.3 item 12)

**Not verified — treat with suspicion:**

- **The browser UI end-to-end.** Page render, element presence and every backing
  endpoint are proven, but nobody has watched the review modal appear after a
  real weigh. This is the highest-value thing for you to exercise first.
- **Phase 2/3** — scrap and production terminals (§8).
- Agent **autostart after reboot** on the weighbridge PC.
- Behaviour under a real **network blip** mid-upload (the retry queue was only
  exercised against a simulated cloud failure).
- **`.12`'s OSD name is still `Camera 01`**, same as `.11` (§5.3 item 13). The
  filename distinguishes them; the image itself does not.

**Test artifacts:** early test captures may remain on `TW-260225-00008` in the
dev database. They are identifiable as `cctv_` files **without** a date segment.
Not present on production.

---

## 7. Rollback

Removing `camera_agent_url` from site config reverts the terminal to the
backend-fetch path. Killing the agent leaves weighing fully functional —
captures just fail with a warning. Setting a `Camera` record's `is_active = 0`
removes it from the terminals.

Capture is **not** on the critical path for weighing. Confirm that in practice
before trusting it: kill the agent mid-session and save a weight.

To revert the terminal flow to auto-printing (no photo review), move the
`printTruckWeight()` call back into `saveWeightByType()` and drop the
`showWeighReview()` call — see §1.1.

---

## 8. Extending to the other terminals (Phase 2 / 3)

**No backend work is needed.** `camera/service.py` and `api/v1/camera.py` are
already generic, and `Scrap Weight` already has a `Weight Photo` child table.
Phase 2 is the scrap (small-scale) terminal; Phase 3 is production sorting.

Per terminal:

**1.** Create `Camera` records with the matching `usage_type` (`Scrap` /
`Production`). Cameras are matched to terminals by that field, so the truck
terminal will not see them.

**2.** Include the client in that terminal's template, after `scale_reader.js`:

```html
<script src="/assets/scrap_metal_suite/js/camera_client.js"></script>
<script>
    window.SMT_CAMERA_AGENT_URL = "{{ camera_agent_url or '' }}";
</script>
```

**3.** Pass `camera_agent_url` from that page's `get_context()` — copy the three
lines from `www/pos/truck.py`.

**4.** Wire capture on save:

```js
const cam = new CameraClient({
    usageType: 'Scrap',
    agentUrl: window.SMT_CAMERA_AGENT_URL || null
});
await cam.loadCameras();

// after the Scrap Weight is created:
const result = await cam.captureAll({
    parentDoctype: 'Scrap Weight',
    parentDoc: scrapWeightName,
    weightType: 'Scrap',
    dropoff, session
});
```

`captureAll()` never throws — inspect `result.ok` / `result.fail` / `result.errors`.

**5.** If the agent is used, add the terminal's cameras to the agent's
`config.json`. The agent's `usage_type` is a single value per instance, so either
run one agent covering all cameras (simplest — omit the `usageType` filter in the
capture request) or one instance per station on different ports.

**Reusable pieces you get for free:** the header badge and menu
(`updateCameraBadge`, `refreshCameraStatus`, `showCameraStatusDialog`), the
post-weigh review modal (`showWeighReview` and its CSS), and
`CameraClient.testCamera()` / `.testAll()`. All are written against ids and
classes rather than truck-specific state, so they port with light editing.

**Known gap to design around:** the `Weight Photo` child table has no `camera`
field, so the camera is only recoverable from the filename. If you need to query
by camera, add the field — that is a Weight Photo doctype change, which this
module deliberately avoided.

---

## 9. Setting up the physical cameras at a new site

Read this if the hardware has been shipped to you and you are wiring it up from
scratch. Nothing here is optional — the network layout is the single most common
reason "the cameras don't work".

### 9.1 ⚠️ Credentials are deliberately not in this repo

This repository is **public**. No camera password, API key or secret appears
anywhere in it — every config example uses placeholders (`PASTE_...`,
`PASSWORD`). **Get the camera username and password from whoever sent you the
hardware, over a private channel.** Do not commit them; `config.json` is the only
place they belong, and it lives on the on-site PC.

### 9.2 What the hardware is

Two Hikvision IP cameras, distinguished by lens focal length:

| Unit | Lens | Snapshot behaviour |
|---|---|---|
| camera A | 4 mm (narrower) | serves **both** channel 101 (2560×1440) and 102 (640×360) |
| camera B | 2.8 mm (wider) | **channel 101 returns HTTP 503 by firmware** — only ever serves 102 (768×432) |

Camera B's 503 is permanent and expected. `capture_bytes()` tries 101 then falls
back, so photos from that unit are simply lower resolution. Do not treat it as a
fault (§5.3 item 10).

Neither unit has a working battery-backed RTC (§9.6).

### 9.3 Find the cameras

Install Hikvision **SADP**. It lists cameras and their current IPs.

> ⚠️ **SADP discovers by broadcast, so it sees cameras even when your PC cannot
> route to them.** A populated SADP list is *not* proof of connectivity. Only a
> real HTTP fetch counts (§9.5).

Note the IPs SADP reports. They were shipped on `192.168.1.11` and
`192.168.1.12`, but that may have changed.

### 9.4 Choose the subnet

The camera switch is unmanaged and has **no DHCP**, so nothing self-configures.
Two options:

**A. Keep the cameras on their existing subnet** (simplest). Give the PC's
Ethernet NIC a free static address on that subnet:

```powershell
# Admin PowerShell. Confirm the adapter name first:
netsh interface ip show interface
netsh interface ip set address name="Ethernet 2" static 192.168.1.50 255.255.255.0
```

Pick the adapter that is actually plugged into the camera switch — a USB-Ethernet
dongle often appears as `Ethernet 2`, not `Ethernet` (§5.2 item 8).

> **Leave the gateway blank.** Setting one can hijack the default route and cut
> the PC's internet, which also breaks the agent's uploads.

If the NIC shows a `169.254.x.x` address, it got no DHCP and the static address
was not applied.

**B. Re-address the cameras** to fit your existing network. Do it in SADP
(select camera → set IP/mask → confirm with the admin password), or over ISAPI.
Then update **both** the `Camera` records and the agent's `config.json` to match.

Either way the PC and the cameras must end up on the same subnet, and the
`Camera` record's `ip_address` must match reality.

### 9.5 Prove connectivity — do not skip this

```bash
ping 192.168.1.11

# the real test: an authenticated snapshot fetch
curl --digest -u admin:PASSWORD \
  "http://192.168.1.11/ISAPI/Streaming/channels/102/picture?snapShotImageType=JPEG" \
  -o test.jpg
```

A non-empty `test.jpg` means you are done with networking. A 401 means wrong
credentials; a timeout means routing, not authentication.

> **Close the camera's web UI before testing.** The 4 mm unit locks channel 101
> while its browser UI is open, which produces a confusing partial failure
> (§5.3 item 11).

Under WSL: once the Windows host has the static IP, WSL reaches the cameras
through it automatically — no mirrored-networking change needed.

### 9.6 Camera clocks

Both units reset to `2000-01-02` on **every power cycle** — no battery-backed
RTC, and `timeMode` ships as `manual`. NTP cannot help because that LAN has no
gateway to reach a time server.

**The agent handles this**: it sets each camera's clock on startup and every few
hours, preserving the configured timezone. Just run the agent and the clocks
correct themselves.

If you are testing *without* the agent, set them manually or the burned-in
timestamp on every photo will read year 2000:

```bash
curl --digest -u admin:PASSWORD -X PUT "http://192.168.1.11/ISAPI/System/time" \
  -H "Content-Type: application/xml" \
  -d '<?xml version="1.0" encoding="UTF-8"?><Time><timeMode>manual</timeMode><localTime>2026-08-17T13:52:00+07:00</localTime><timeZone>CST-7:00:00</timeZone></Time>'
```

`CST-7:00:00` is Hikvision's inverted notation for **UTC+7** (Thailand). Adjust
for your timezone, and make the `localTime` offset agree with it.

### 9.7 Register them in Frappe

Desk → **Camera** → New, one per unit, per §3.2. The `camera_name` **must match
the `name` in the agent's `config.json` exactly**, or the terminal cannot resolve
it (§5.1 item 2).

Then open **`/camera-test`** and press **Test All**. Both should go green, one
reporting channel 101 and the other 102. That page needs no POS session, no
dropoff and no weighing — it is the fastest way to confirm the hardware and the
software agree.

### 9.8 Also worth fixing

Both units ship with the same on-screen display name (`Camera 01`), so two photos
on one Truck Weight are indistinguishable by eye. The stored filename does
distinguish them, but renaming camera B's OSD to `Camera 02` in its web UI is a
minute's work and makes the evidence self-describing (§5.3 item 13).

### 9.9 Checklist for whoever ships the hardware

- [ ] Both cameras, PSU/PoE injector, and the unmanaged switch
- [ ] A USB-Ethernet adapter if the PC has no spare port
- [ ] **Camera username + password, sent privately — not in this repo**
- [ ] The IPs currently configured on each unit
- [ ] Which unit is 4 mm and which is 2.8 mm (they behave differently, §9.2)
- [ ] Cloud site URL, plus an API key/secret for a `POS Operator` agent user (§3.3)
- [ ] The two Windows-only design docs, if the architectural rationale is wanted
      (`CAMERA_INTEGRATION.md`, `CAMERA_CAPTURE_AGENT_DESIGN.md` — excluded from
      this repo by `.gitignore`)
