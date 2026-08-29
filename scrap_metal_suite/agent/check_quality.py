"""Report what each camera is actually producing.

Change a setting in the camera UI, run this, see whether it moved. Guessing
from the preview window does not work - a 4 MP frame and a 0.3 MP frame look
identical scaled into a browser pane.

Reads the same config.json the agent uses. Needs only `requests`, which the
agent already depends on - deliberately no Pillow, so this runs on the
weighbridge PC without installing anything further.

    python check_quality.py
    python check_quality.py --save        # also write the JPEGs out to look at
"""

import argparse
import datetime
import json
import os
import struct
import sys

import requests
from requests.auth import HTTPDigestAuth

# The standard JPEG luma quantization table. A camera's own table divided by
# this one gives the quality setting it encoded at.
STD_LUMA = [
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
]


def parse_jpeg(data):
    """Pull dimensions and the luma quantization table straight out of the bytes.

    Returns (width, height, luma_table) with any part None if not found.
    """
    width = height = None
    luma = None
    i = 2  # skip SOI

    while i < len(data) - 1:
        if data[i] != 0xFF:
            i += 1
            continue

        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xDA:  # start of scan - image data follows, stop
            break

        if i + 4 > len(data):
            break
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        segment = data[i + 4:i + 2 + length]

        if marker in (0xC0, 0xC1, 0xC2, 0xC3) and len(segment) >= 5:
            height, width = struct.unpack(">HH", segment[1:5])
        elif marker == 0xDB:  # define quantization table
            pos = 0
            while pos < len(segment):
                pq = segment[pos] >> 4       # 0 = 8-bit values, 1 = 16-bit
                tq = segment[pos] & 0x0F     # 0 = luma
                pos += 1
                count = 64 * (2 if pq else 1)
                table = segment[pos:pos + count]
                if tq == 0 and luma is None and len(table) >= 64:
                    if pq:
                        luma = list(struct.unpack(">64H", table[:128]))
                    else:
                        luma = list(table[:64])
                pos += count

        i += 2 + length

    return width, height, luma


def jpeg_quality(luma):
    """Recover the encoder's quality setting from its quantization table."""
    if not luma:
        return None
    ratios = sorted(luma[n] / STD_LUMA[n] for n in range(64))
    r = ratios[32]  # median
    scale = r * 100
    if scale <= 0:
        return None
    return (200 - scale) / 2 if scale <= 100 else 5000 / scale


def grab(cam, channel, timeout=10):
    url = "http://{ip}:{port}/ISAPI/Streaming/channels/{ch}/picture?snapShotImageType=JPEG".format(
        ip=cam["ip"], port=cam.get("port", 80), ch=channel
    )
    try:
        r = requests.get(
            url,
            auth=HTTPDigestAuth(cam.get("username", "admin"), cam.get("password", "")),
            timeout=timeout,
        )
    except requests.exceptions.RequestException as e:
        return None, str(e)
    if r.status_code != 200:
        return None, "HTTP {0}".format(r.status_code)
    if not r.content.startswith(b"\xff\xd8"):
        return None, "not a JPEG"
    return r.content, None


def main():
    ap = argparse.ArgumentParser(description="Report actual camera image quality")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--save", action="store_true", help="write the JPEGs out too")
    args = ap.parse_args()

    if not os.path.exists(args.config):
        sys.exit("config.json not found next to this script - pass --config PATH")

    config = json.load(open(args.config, encoding="utf-8"))
    cameras = config.get("cameras", [])
    if not cameras:
        sys.exit("no cameras in config.json")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print()
    print("  {0:<16} {1:<4} {2:<13} {3:>7} {4:>8} {5:>9}".format(
        "camera", "ch", "resolution", "MP", "size", "quality"))
    print("  " + "-" * 66)

    for cam in cameras:
        for channel in ("101", "102"):
            data, err = grab(cam, channel)
            if err:
                print("  {0:<16} {1:<4} {2}".format(cam["name"], channel, err))
                continue

            w, h, luma = parse_jpeg(data)
            q = jpeg_quality(luma)
            mp = (w * h) / 1e6 if w and h else 0
            print("  {0:<16} {1:<4} {2:<13} {3:>7.1f} {4:>7.0f}K {5:>9}".format(
                cam["name"], channel,
                "{0}x{1}".format(w, h) if w else "?",
                mp, len(data) / 1024,
                "{0:.0f}".format(q) if q else "?",
            ))

            if args.save:
                name = "{0}_{1}_ch{2}.jpg".format(stamp, cam["name"], channel)
                with open(name, "wb") as f:
                    f.write(data)

    print()
    print("  What to aim for on the main stream (ch 101):")
    print("    resolution  the camera's maximum - 2560x1440 on a 4 MP unit")
    print("    quality     90 or above (factory default is 75)")
    print()
    if args.save:
        print("  JPEGs written to this folder - open the ch101 one and zoom to the plate.")
        print()


if __name__ == "__main__":
    main()
