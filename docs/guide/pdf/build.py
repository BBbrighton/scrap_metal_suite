#!/usr/bin/env python3
"""Render a user guide to PDF via Windows Chrome.

Why Chrome and not WeasyPrint: WSL has no Thai-capable font installed
(`fc-list :lang=th` returns nothing), and WeasyPrint here embeds no font at
all — verified by inspecting its output, which carried no `/FontFile` and an
empty glyph array even for Latin. Windows ships Leelawadee UI and Tahoma, and
Chrome is reachable from WSL, so it renders and embeds correctly.

Usage:
    python3 build.py ../user/30-settlement.md            # -> out/30-settlement.pdf
    python3 build.py ../user/30-settlement.md --keep-html
"""
import argparse
import html as _html
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

CHROME_CANDIDATES = (
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
)


def find_browser():
    for path in CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    sys.exit("No Windows Chrome or Edge found. Checked:\n  " + "\n  ".join(CHROME_CANDIDATES))


def winpath(path):
    """Chrome needs Windows-style paths; it cannot read /home/... directly.

    `wslpath -w` fails on a path that does not exist yet, which the output PDF
    never does, so translate the directory and re-attach the basename.
    """
    directory, base = os.path.split(os.path.abspath(path))
    win_dir = subprocess.run(["wslpath", "-w", directory], capture_output=True,
                             text=True, check=True).stdout.strip()
    return win_dir.rstrip("\\") + "\\" + base


def render_markdown(text):
    import markdown2
    # `fenced-code-blocks` for the ``` blocks, `tables` for the pipe tables the
    # guides lean on heavily, `break-on-newline` because the bilingual layout
    # puts Thai and English on consecutive lines that must not be joined.
    return markdown2.markdown(text, extras=[
        "fenced-code-blocks", "tables", "break-on-newline",
        "header-ids", "strike", "cuddled-lists",
    ])


def strip_mermaid(text):
    """Replace mermaid fences with a note — Chrome cannot render them.

    Dropping them silently would lose content the guide refers to, so say
    what was there instead.
    """
    def repl(m):
        return ("> *(แผนผังลำดับงาน — ดูฉบับออนไลน์ / flow diagram omitted in print;"
                " see the online guide)*\n")
    return re.sub(r"```mermaid\n.*?\n```", repl, text, flags=re.S)


def build(md_path, keep_html=False):
    md_path = os.path.abspath(md_path)
    if not os.path.exists(md_path):
        sys.exit(f"not found: {md_path}")

    slug = os.path.splitext(os.path.basename(md_path))[0]
    os.makedirs(OUT, exist_ok=True)
    html_path = os.path.join(OUT, slug + ".html")
    pdf_path = os.path.join(OUT, slug + ".pdf")

    text = strip_mermaid(open(md_path, encoding="utf-8").read())
    body = render_markdown(text)
    css = open(os.path.join(HERE, "guide.css"), encoding="utf-8").read()

    title = _html.escape(text.lstrip().splitlines()[0].lstrip("# ").strip())
    open(html_path, "w", encoding="utf-8").write(
        f"<!doctype html><html lang=\"th\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title><style>{css}</style></head><body>{body}</body></html>"
    )

    browser = find_browser()
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    subprocess.run([
        browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={winpath(pdf_path)}", winpath(html_path),
    ], capture_output=True, timeout=180)

    # Chrome returns before the file is flushed; poll rather than assume.
    for _ in range(40):
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            break
        time.sleep(0.25)
    else:
        sys.exit(f"Chrome produced no PDF at {pdf_path}")

    data = open(pdf_path, "rb").read()
    if b"/FontFile" not in data:
        sys.exit(f"{pdf_path} has no embedded font — Thai would print blank. Aborting.")

    if not keep_html:
        os.remove(html_path)

    pages = data.count(b"/Type /Page") or data.count(b"/Type/Page")
    print(f"  {os.path.relpath(pdf_path, HERE)}  {len(data)//1024} KB  ~{pages} pages  font embedded OK")
    return pdf_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown", nargs="+")
    ap.add_argument("--keep-html", action="store_true")
    args = ap.parse_args()
    for m in args.markdown:
        build(m, args.keep_html)
