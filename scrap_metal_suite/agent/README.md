# SMT Camera Capture Agent

A small local service for the on-site weighbridge PC. It Digest-fetches JPEG
snapshots from the LAN cameras and uploads them to the cloud Frappe site, so
the truck terminal can attach CCTV photos to a Truck Weight.

It exists because the cloud server cannot reach `192.168.1.x`, and the browser
cannot fetch a Hikvision snapshot itself (Digest auth, no CORS, mixed content).
Same shape as the scale: read the hardware locally, send only the result.

---

## 1. Cloud prerequisites (do these first)

### 1.1 Create the agent's user

Create a dedicated user, e.g. `camera-agent@smt.x-desk.tech`, and give it the
**`POS Operator`** role.

> **This role is required, and it is the only one required.** The endpoint the
> agent calls — `api/v1/camera.receive_weight_photo` — runs `check_pos_operator()`
> like every other POS endpoint. A user that can "create File and Weight Photo"
> but lacks `POS Operator` is rejected. Do **not** grant System Manager.

Generate an **API key + secret** for that user (User form → Settings → API Access)
and paste both into `config.json`.

### 1.2 Pre-create the Camera records

In Desk → **Camera** → New, one record per camera, with `usage_type = Truck`
and `is_active` checked.

> **The `camera_name` must match the `name` in `config.json` exactly.** The
> terminal resolves a name against the agent, so a mismatch means the preview
> can't find the camera. The agent logs both directions of mismatch at startup
> and the browser console warns on load — check there first if a camera is
> missing from the dropdown.

Leave the cloud record's **password blank**. In agent mode the cloud never
connects to the camera; `ip_address` / `username` / `password` on the Camera
doctype are labels only. The real credentials stay in this `config.json`, on
the PC, on the LAN.

### 1.3 Point the terminal at the agent

```bash
bench --site smt.x-desk.tech set-config camera_agent_url "http://127.0.0.1:8787"
```

Without this the terminal silently falls back to the backend-fetch path — the
cloud tries to reach the LAN and every weigh hangs on a timeout. This is the
highest-value line in the whole deployment.

To roll back, remove the key and `bench restart`.

---

## 2. Configure

Copy `config.example.json` to `config.json` **beside the executable** and fill it in:

| Key | Meaning |
|---|---|
| `port` | Local port to bind (default `8787`) |
| `cloud_url` | Base URL of the Frappe site |
| `api_key` / `api_secret` | The Camera Agent user's API credentials |
| `allowed_origin` | CORS origin allowed to call the agent — the site URL |
| `usage_type` | Which terminal these cameras serve (`Truck`) |
| `retry_queue_size` | Max pending uploads held for retry (default 50) |
| `sync_camera_clocks` | Keep the camera clocks correct (default `true`) — see §10 |
| `clock_sync_interval_hours` | How often to re-sync (default 6) |
| `time_zone` | Fallback Hikvision zone if the camera doesn't report one. `CST-7:00:00` is UTC+7 (Thailand) — note the inverted sign |
| `cameras[]` | `name`, `ip`, `port`, `channel`, `username`, `password` |

`channel` should be `102` (sub-stream). Saved captures still try `101` first and
fall back to `102` automatically, so a camera whose firmware answers 503 on the
main stream still works.

---

## 3. Run from source (desk testing)

```bash
pip install requests
python smt_camera_agent.py --config config.json
```

Verify:

```bash
curl http://127.0.0.1:8787/health
curl "http://127.0.0.1:8787/frame?camera=TRUCK-CAM-01" --output frame.jpg
```

`/health` lists the cameras and reports whether the cloud is reachable.

---

## 4. Build the .exe

```bash
pip install pyinstaller requests
pyinstaller --onefile --name smt-camera-agent smt_camera_agent.py
```

The binary lands in `dist/smt-camera-agent.exe`. Copy it and a filled
`config.json` to the same folder on the weighbridge PC.

**Build and test this at the desk, not on site.** Assume the weighbridge PC has
no internet — do not plan to `pip install` there. The first run will trip
SmartScreen and a Windows Firewall prompt; meet both before you travel.

---

## 5. Autostart

Either works — pick one:

- **Startup folder:** `Win+R` → `shell:startup` → put a shortcut to the exe there.
- **Task Scheduler:** new task, trigger "At log on", action = the exe, and tick
  "Run only when user is logged on".

**Reboot the PC and confirm the agent comes back by itself before leaving site.**

---

## 6. Network

Cameras are on static IPs on `192.168.1.x` and that switch has **no DHCP**. Set
the PC's Ethernet NIC to a static `192.168.1.50/24`.

SADP discovers cameras by broadcast even when routing cannot reach them, so a
populated SADP list is **not** proof of connectivity. Prove it with a real
request:

```bash
curl --digest -u admin:PASSWORD "http://192.168.1.11/ISAPI/Streaming/channels/102/picture?snapShotImageType=JPEG" -o test.jpg
```

Close the Hikvision web UI before testing — camera `.11` locks channel 101 while
its UI is open.

---

## 7. Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | `{ok, version, cameras, cloud, pending_uploads}` |
| `GET` | `/frame?camera=NAME` | `image/jpeg` live preview (sub-stream) |
| `POST` | `/capture` | Fetch + upload; `{ok, fail, photo_count, results, errors}` |

`POST /capture` body — omit `camera` to capture every configured camera:

```json
{
  "camera": "TRUCK-CAM-01",
  "parentDoctype": "Truck Weight",
  "parentDoc": "TW-260815-00001",
  "weightType": "Truck Gross",
  "dropoff": "DO-2026-00001",
  "session": "POS-SES-00001"
}
```

---

## 8. Security

- Binds **`127.0.0.1` only** — never reachable from the LAN.
- CORS is restricted to `allowed_origin`, and it returns
  `Access-Control-Allow-Private-Network: true` so the HTTPS terminal page may
  call `http://127.0.0.1`.
- Camera credentials never leave the PC.
- Agent → cloud runs over HTTPS with a limited user's API token.

Treat `config.json` as a secret: it holds both the camera passwords and the
cloud API secret.

---

## 9. Failure behaviour

Capture is **not on the critical path for weighing**. If the agent is down or a
camera is unreachable, the weight still saves and the terminal shows a warning.
Verify this in practice: kill the agent mid-session and save a weight.

Failed cloud uploads are queued and retried (5 attempts, exponential backoff
from 30s). The queue is in-memory and bounded by `retry_queue_size` — an agent
restart drops anything still pending, and both the drop and the give-up are
logged as errors. If the yard needs photos to be evidentially complete, watch
`smt-camera-agent.log` for `Giving up on upload` and re-capture from the Truck
Weight record.

Logs rotate at 1 MB, 3 backups, next to the executable.

---

## 10. Camera clocks

These cameras have **no battery-backed RTC** and ship with `timeMode = manual`,
so their clocks reset to `2000-01-02` on **every power cycle**. Setting the time
by hand in the camera's web UI holds only until the next power blip, then
silently reverts — and the wrong date is burned into the image overlay, which is
exactly what an auditor reads off a disputed weigh ticket.

NTP can't solve it here: the camera LAN has no gateway, so the factory-configured
`time.windows.com` is unreachable. (The NTP server *is* listed on both cameras,
but `timeMode = manual` ignores it.)

So the agent does it. On startup, and every `clock_sync_interval_hours`
thereafter, it `PUT`s the PC's current local time to
`/ISAPI/System/time` on each camera. It reads each camera's existing `timeZone`
first and preserves it, falling back to the `time_zone` config value only if the
camera doesn't report one.

Because the agent autostarts on login (§5), the clocks self-correct after every
power cycle with nothing to do on site.

Check it with `/health`:

```json
"clock_sync": {
  "TRUCK-CAM-01": { "ok": true, "detail": "2026-08-17T13:52:23+07:00" },
  "TRUCK-CAM-02": { "ok": true, "detail": "2026-08-17T13:52:23+07:00" }
}
```

Set `"sync_camera_clocks": false` to turn it off — e.g. if you later put a real
NTP server on the LAN and set the cameras to `timeMode = NTP`, which would be
the more conventional fix.

**Note:** the DB-side timestamp was never affected. `Weight Photo.captured_at`
uses server time and has always been correct; this only fixes the timestamp
drawn into the image.
