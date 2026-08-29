#!/usr/bin/env python3
# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

"""
SMT Camera Capture Agent - runs on the on-site weighbridge PC.

Why this exists
---------------
The cloud Frappe server cannot reach the camera LAN (192.168.1.x), and the
browser cannot fetch a Hikvision snapshot directly (Digest auth, no CORS,
mixed content). So a native process on the LAN does the fetch and POSTs the
result to the cloud - the same shape as the scale: read the hardware locally,
send only the result.

    Browser (truck terminal) --HTTP localhost--> this agent
                                                    | Digest GET (LAN)
                                                    v
                                              Hikvision cameras
                                                    | JPEG
                                                    v
                                    cloud receive_weight_photo() (token auth)

Endpoints (bound to 127.0.0.1 only)
-----------------------------------
    GET  /health                 -> {ok, cameras, cloud, clock_sync}
    GET  /frame?camera=NAME      -> image/jpeg (live preview, sub-stream)
    POST /capture                -> {ok, fail, photo_count, results, errors}

Run:
    python smt_camera_agent.py [--config config.json]

Build:
    pyinstaller --onefile --name smt-camera-agent smt_camera_agent.py
"""

import argparse
import base64
import datetime
import json
import logging
import os
import re
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from urllib.parse import parse_qs, urlparse

import requests
from requests.auth import HTTPDigestAuth

APP_NAME = "smt-camera-agent"
VERSION = "0.2.0"

MAIN_CHANNEL = "101"
DEFAULT_SUB_CHANNEL = "102"

# Hikvision inverted notation: CST-7 == UTC+7 (Thailand)
DEFAULT_TIME_ZONE = "CST-7:00:00"

PREVIEW_TIMEOUT = 4
CAPTURE_TIMEOUT = 10
UPLOAD_TIMEOUT = 30

RECEIVE_ENDPOINT = "/api/method/scrap_metal_suite.api.v1.camera.receive_weight_photo"

log = logging.getLogger(APP_NAME)


# =============================================================================
# CONFIG
# =============================================================================

def _base_dir():
    """Directory holding the exe (frozen) or this script - config.json lives here."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_config(path=None):
    path = path or os.path.join(_base_dir(), "config.json")

    if not os.path.exists(path):
        raise SystemExit(
            "Config not found: {0}\n"
            "Copy config.example.json to config.json and fill it in.".format(path)
        )

    with open(path, "r", encoding="utf-8") as fh:
        config = json.load(fh)

    for key in ("cloud_url", "api_key", "api_secret"):
        if not config.get(key):
            raise SystemExit("Config is missing required key: {0}".format(key))

    if not config.get("cameras"):
        raise SystemExit("Config has no cameras")

    config["cloud_url"] = config["cloud_url"].rstrip("/")
    config.setdefault("port", 8787)
    config.setdefault("usage_type", "Truck")
    config.setdefault("allowed_origin", config["cloud_url"])
    config.setdefault("log_file", os.path.join(_base_dir(), APP_NAME + ".log"))
    config.setdefault("retry_queue_size", 50)
    config.setdefault("sync_camera_clocks", True)
    config.setdefault("clock_sync_interval_hours", 1)
    config.setdefault("time_zone", DEFAULT_TIME_ZONE)

    for cam in config["cameras"]:
        cam.setdefault("port", 80)
        cam.setdefault("channel", DEFAULT_SUB_CHANNEL)
        cam.setdefault("username", "admin")
        cam["channel"] = str(cam["channel"])

    return config


def setup_logging(log_file):
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    log.addHandler(stream)

    try:
        rotating = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        rotating.setFormatter(fmt)
        log.addHandler(rotating)
    except OSError as e:
        log.warning("Could not open log file %s: %s", log_file, e)


# =============================================================================
# CAMERA FETCH (mirrors camera/service.py)
# =============================================================================

class CameraRegistry:
    def __init__(self, cameras, usage_type):
        self.usage_type = usage_type
        self._by_name = {c["name"]: c for c in cameras}

    def names(self):
        return list(self._by_name.keys())

    def get(self, name):
        return self._by_name.get(name)

    def all(self):
        return list(self._by_name.values())


def snapshot_url(cam, channel):
    return (
        "http://{ip}:{port}/ISAPI/Streaming/channels/{ch}/picture"
        "?snapShotImageType=JPEG".format(ip=cam["ip"], port=cam.get("port", 80), ch=channel)
    )


def try_fetch(cam, channel, timeout):
    """Non-throwing Digest fetch. Returns bytes or None."""
    try:
        response = requests.get(
            snapshot_url(cam, channel),
            auth=HTTPDigestAuth(cam.get("username", "admin"), cam.get("password", "")),
            timeout=timeout,
        )
        if response.status_code == 200 and response.content:
            return response.content

        log.warning("Camera %s channel %s returned HTTP %s", cam["name"], channel, response.status_code)
    except requests.exceptions.RequestException as e:
        log.warning("Camera %s channel %s unreachable: %s", cam["name"], channel, e)

    return None


def fetch_preview(cam):
    """Preview uses the configured sub-stream only - it must stay fast."""
    return try_fetch(cam, cam.get("channel", DEFAULT_SUB_CHANNEL), PREVIEW_TIMEOUT)


# Read once per camera and kept - the timeZone is a config value that only
# changes if someone edits it in the camera UI, and a clock set now happens
# on the capture path where a spare round trip is worth avoiding.
_TZ_CACHE = {}


def camera_time_zone(cam):
    """Read the camera's configured timeZone so a clock set doesn't clobber it.

    Cached per camera. Only successful reads are cached, so a camera that was
    unreachable on the first attempt is retried rather than pinned to the
    fallback zone forever.

    Returns the timeZone string (e.g. "CST-7:00:00") or None.
    """
    cached = _TZ_CACHE.get(cam["ip"])
    if cached:
        return cached

    try:
        response = requests.get(
            "http://{ip}:{port}/ISAPI/System/time".format(ip=cam["ip"], port=cam.get("port", 80)),
            auth=HTTPDigestAuth(cam.get("username", "admin"), cam.get("password", "")),
            timeout=PREVIEW_TIMEOUT,
        )
        if response.status_code == 200:
            match = re.search(r"<timeZone>(.*?)</timeZone>", response.text)
            if match:
                zone = match.group(1).strip()
                _TZ_CACHE[cam["ip"]] = zone
                return zone
    except requests.exceptions.RequestException:
        pass

    return None


def set_camera_time(cam, fallback_zone=DEFAULT_TIME_ZONE):
    """Set a camera's clock to this PC's current local time.

    These units have no battery-backed RTC and ship with timeMode=manual, so the
    clock resets to 2000-01-02 on every power cycle. The burned-in OSD timestamp
    is what an auditor reads off an evidentiary photo, so it must be right. NTP
    can't help: the camera LAN has no gateway, so the configured public NTP
    server is unreachable.

    The agent is the natural place to fix this - it runs on the same PC, on the
    same LAN, and starts on every boot.

    Returns:
        tuple[bool, str]: (ok, detail)
    """
    zone = camera_time_zone(cam) or fallback_zone

    # Local time WITH the PC's UTC offset, e.g. 2026-08-17T13:45:00+07:00
    now_local = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Time><timeMode>manual</timeMode>"
        "<localTime>{now}</localTime>"
        "<timeZone>{zone}</timeZone></Time>"
    ).format(now=now_local, zone=zone)

    try:
        response = requests.put(
            "http://{ip}:{port}/ISAPI/System/time".format(ip=cam["ip"], port=cam.get("port", 80)),
            auth=HTTPDigestAuth(cam.get("username", "admin"), cam.get("password", "")),
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=CAPTURE_TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        return False, str(e)

    if response.status_code == 200:
        return True, now_local

    return False, "HTTP {0}: {1}".format(response.status_code, response.text[:120].replace("\n", " "))


class ClockSync:
    """Keeps the camera clocks correct, at startup and periodically."""

    def __init__(self, registry, interval_seconds, fallback_zone):
        self.registry = registry
        self.interval = interval_seconds
        self.fallback_zone = fallback_zone
        self.last_result = {}
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def sync_all(self):
        for cam in self.registry.all():
            ok, detail = set_camera_time(cam, self.fallback_zone)
            self.last_result[cam["name"]] = {"ok": ok, "detail": detail}
            if ok:
                log.info("Clock set on %s -> %s", cam["name"], detail)
            else:
                log.warning("Could not set clock on %s: %s", cam["name"], detail)

    def ensure_fresh(self, cam):
        """Set one camera's clock immediately before a capture.

        The periodic loop alone is not enough. These units lose their clock on
        every power cycle, so a camera that reboots between passes stamps every
        photo 2000-01-02 until the next pass comes round - and the burned-in
        timestamp is the part a person reads off the photo when a weighing is
        disputed. One extra request, on an event that happens a few hundred
        times a month, buys a stamp that is always right.

        Never raises: a clock that cannot be set must not cost us the photo.
        """
        try:
            ok, detail = set_camera_time(cam, self.fallback_zone)
        except Exception as e:  # noqa: BLE001 - the capture matters more
            log.error("Clock sync errored on %s before capture: %s", cam["name"], e)
            self.last_result[cam["name"]] = {"ok": False, "detail": str(e)}
            return False

        self.last_result[cam["name"]] = {"ok": ok, "detail": detail}
        if not ok:
            # ERROR, not WARNING: this one silently produces bad evidence.
            log.error("Clock not set on %s before capture: %s", cam["name"], detail)
        return ok

    def _loop(self):
        while True:
            self.sync_all()
            time.sleep(self.interval)


def fetch_capture(cam):
    """Saved capture prefers the main stream, falling back to the sub-stream.

    Some units answer HTTP 503 on 101 by firmware and only ever serve 102, so
    the fallback keeps a reachable camera from reporting a false offline.

    Returns:
        tuple[bytes|None, str|None]: (content, channel used)
    """
    sub = cam.get("channel", DEFAULT_SUB_CHANNEL)

    tried = []
    for channel in (MAIN_CHANNEL, sub):
        if channel in tried:
            continue
        tried.append(channel)

        content = try_fetch(cam, channel, CAPTURE_TIMEOUT)
        if content:
            return content, channel

    return None, None


# =============================================================================
# CLOUD UPLOAD (+ bounded retry queue)
# =============================================================================

class CloudUploader:
    """Uploads JPEGs to the cloud, retrying transient failures in the background.

    The queue is bounded and in-memory: an agent restart drops anything still
    pending. That is deliberate for v1 - it turns a silent loss into a bounded,
    logged one. A weigh is never blocked by an upload.
    """

    def __init__(self, config):
        self.cloud_url = config["cloud_url"]
        self.endpoint = self.cloud_url + RECEIVE_ENDPOINT
        self.headers = {
            "Authorization": "token {0}:{1}".format(config["api_key"], config["api_secret"]),
            "Content-Type": "application/json",
        }

        self._queue = deque(maxlen=config["retry_queue_size"])
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._retry_loop, daemon=True)
        self._worker.start()

    def upload(self, payload):
        """Try once inline. On failure queue it and report the error.

        Returns:
            tuple[bool, str|None]: (delivered, error)
        """
        ok, error = self._post(payload)
        if ok:
            return True, None

        with self._lock:
            dropped = len(self._queue) == self._queue.maxlen
            self._queue.append({"payload": payload, "attempts": 1, "next_at": time.time() + 30})

        if dropped:
            log.error("Retry queue full - oldest pending upload discarded")

        return False, error

    def _post(self, payload):
        try:
            response = requests.post(
                self.endpoint, headers=self.headers, json=payload, timeout=UPLOAD_TIMEOUT
            )
        except requests.exceptions.RequestException as e:
            return False, "cloud unreachable: {0}".format(e)

        if response.status_code == 200:
            return True, None

        # Frappe returns the traceback in _server_messages / exception
        detail = response.text[:300].replace("\n", " ")
        return False, "cloud HTTP {0}: {1}".format(response.status_code, detail)

    def _retry_loop(self):
        while True:
            time.sleep(5)

            with self._lock:
                if not self._queue:
                    continue
                item = self._queue[0]
                if item["next_at"] > time.time():
                    continue
                self._queue.popleft()

            ok, error = self._post(item["payload"])
            if ok:
                log.info("Queued upload delivered after %s attempt(s)", item["attempts"] + 1)
                continue

            item["attempts"] += 1
            if item["attempts"] >= 5:
                log.error("Giving up on upload after %s attempts: %s", item["attempts"], error)
                continue

            # Exponential backoff: 30s, 60s, 120s, 240s
            item["next_at"] = time.time() + 30 * (2 ** (item["attempts"] - 1))
            with self._lock:
                self._queue.append(item)

    def pending(self):
        with self._lock:
            return len(self._queue)

    def check_cloud(self):
        try:
            response = requests.get(self.cloud_url + "/api/method/ping", timeout=5)
            return "reachable" if response.status_code < 500 else "error"
        except requests.exceptions.RequestException:
            return "unreachable"


# =============================================================================
# CAPTURE ORCHESTRATION
# =============================================================================

def do_capture(registry, uploader, body, clock=None):
    """Fetch from one or all cameras and upload each JPEG to the cloud."""
    parent_doctype = body.get("parentDoctype")
    parent_doc = body.get("parentDoc")

    if not parent_doctype or not parent_doc:
        return {"ok": 0, "fail": 0, "photo_count": 0, "results": [],
                "errors": ["parentDoctype and parentDoc are required"]}

    if body.get("camera"):
        cam = registry.get(body["camera"])
        if not cam:
            return {"ok": 0, "fail": 1, "photo_count": 0, "results": [],
                    "errors": ["unknown camera: {0}".format(body["camera"])]}
        cameras = [cam]
    else:
        cameras = registry.all()

    summary = {"ok": 0, "fail": 0, "photo_count": 0, "results": [], "errors": []}

    for cam in cameras:
        # Correct the clock before the shutter, not after - see ClockSync.ensure_fresh.
        # Guarded even though ensure_fresh swallows its own errors: this is the
        # evidence path, and no clock problem is worth losing the photo over.
        if clock is not None:
            try:
                clock.ensure_fresh(cam)
            except Exception as e:  # noqa: BLE001
                log.error("Clock sync raised on %s, capturing anyway: %s", cam["name"], e)

        content, channel = fetch_capture(cam)
        if not content:
            summary["fail"] += 1
            summary["errors"].append("{0}: no image on 101 or {1}".format(
                cam["name"], cam.get("channel")))
            continue

        payload = {
            "parent_doctype": parent_doctype,
            "parent_doc": parent_doc,
            "weight_type": body.get("weightType"),
            "image_b64": base64.b64encode(content).decode("ascii"),
            "camera": cam["name"],
            "dropoff": body.get("dropoff"),
            "session": body.get("session"),
        }

        delivered, error = uploader.upload(payload)
        if delivered:
            summary["ok"] += 1
            summary["photo_count"] += 1
            summary["results"].append({
                "camera": cam["name"], "channel": channel, "bytes": len(content)
            })
            log.info("Captured %s (ch %s, %s bytes) -> %s %s",
                     cam["name"], channel, len(content), parent_doctype, parent_doc)
        else:
            summary["fail"] += 1
            summary["errors"].append("{0}: {1} (queued for retry)".format(cam["name"], error))
            log.error("Upload failed for %s: %s", cam["name"], error)

    return summary


# =============================================================================
# HTTP SERVER
# =============================================================================

class AgentHandler(BaseHTTPRequestHandler):
    server_version = "{0}/{1}".format(APP_NAME, VERSION)

    # Injected by make_server()
    config = None
    registry = None
    uploader = None
    clock = None

    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)

    # ---- helpers ----------------------------------------------------------

    def _cors(self):
        origin = self.config.get("allowed_origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # Lets an HTTPS page call http://127.0.0.1 under Private Network Access
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_jpeg(self, content):
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    # ---- routes -----------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            return self._send_json({
                "ok": True,
                "version": VERSION,
                "usage_type": self.registry.usage_type,
                "cameras": [
                    {"name": c["name"], "ip": c["ip"], "channel": c.get("channel")}
                    for c in self.registry.all()
                ],
                "cloud": self.uploader.check_cloud(),
                "pending_uploads": self.uploader.pending(),
                "clock_sync": self.clock.last_result if self.clock else "disabled",
            })

        if parsed.path == "/frame":
            params = parse_qs(parsed.query)
            name = (params.get("camera") or [None])[0]

            if not name:
                return self._send_json({"error": "camera parameter is required"}, 400)

            cam = self.registry.get(name)
            if not cam:
                return self._send_json({"error": "unknown camera: {0}".format(name)}, 404)

            content = fetch_preview(cam)
            if not content:
                return self._send_json({"error": "camera unreachable"}, 502)

            return self._send_jpeg(content)

        return self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/capture":
            return self._send_json({"error": "not found"}, 404)

        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError) as e:
            return self._send_json({"error": "bad request body: {0}".format(e)}, 400)

        try:
            result = do_capture(self.registry, self.uploader, body, self.clock)
        except Exception as e:
            log.exception("Capture failed")
            return self._send_json({"ok": 0, "fail": 1, "errors": [str(e)]}, 500)

        return self._send_json(result)


def make_server(config):
    registry = CameraRegistry(config["cameras"], config["usage_type"])
    uploader = CloudUploader(config)

    clock = None
    if config.get("sync_camera_clocks"):
        clock = ClockSync(
            registry,
            int(config["clock_sync_interval_hours"]) * 3600,
            config.get("time_zone", DEFAULT_TIME_ZONE),
        )
        clock.start()

    handler = type("BoundAgentHandler", (AgentHandler,), {
        "config": config,
        "registry": registry,
        "uploader": uploader,
        "clock": clock,
    })

    # 127.0.0.1 only - never exposed to the LAN
    return ThreadingHTTPServer(("127.0.0.1", config["port"]), handler)


def main():
    parser = argparse.ArgumentParser(description="SMT Camera Capture Agent")
    parser.add_argument("--config", help="path to config.json")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config["log_file"])

    log.info("%s v%s starting", APP_NAME, VERSION)
    log.info("Cameras: %s", ", ".join(c["name"] for c in config["cameras"]))
    log.info("Cloud:   %s", config["cloud_url"])

    server = make_server(config)
    log.info("Listening on http://127.0.0.1:%s", config["port"])

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
