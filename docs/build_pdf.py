#!/usr/bin/env python3
"""Convert USER_GUIDE_V2 markdown files to PDF with clickable TOC."""
import subprocess
import tempfile
import os
import unicodedata
from pathlib import Path

import markdown


def github_slugify(value, separator):
    """GitHub-style slugify: keep Unicode (Thai tone marks etc.), strip punctuation,
    replace each space with separator (preserves double-hyphens where '&' was)."""
    value = value.lower()
    value = "".join(
        c for c in value if unicodedata.category(c)[0] != "P"
    )
    value = value.strip()
    return value.replace(" ", separator)

DOCS = Path(__file__).parent
OUT_DIR = Path("/mnt/c/Users/Ratch/Downloads")

FILES = [
    ("USER_GUIDE_V2.md", "Scrap_Metal_Suite_User_Guide_EN_v1.1.0.pdf", "en"),
    ("USER_GUIDE_V2_TH.md", "Scrap_Metal_Suite_User_Guide_TH_v1.1.0.pdf", "th"),
]

CSS = """
@page { size: A4; margin: 20mm 18mm 22mm 18mm; }
body {
    font-family: 'Noto Sans Thai', 'DejaVu Sans', sans-serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #1a1a1a;
}
h1 { font-size: 22pt; color: #0f172a; border-bottom: 2px solid #1976d2; padding-bottom: 6px; margin-top: 24px; }
h2 { font-size: 16pt; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-top: 28px; page-break-after: avoid; }
h3 { font-size: 13pt; color: #1e293b; margin-top: 18px; page-break-after: avoid; }
h4 { font-size: 11.5pt; color: #334155; margin-top: 14px; }
p  { margin: 8px 0; }
code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 0.88em; color: #0369a1; }
pre { background: #0f172a; color: #e2e8f0; padding: 10px 12px; border-radius: 4px; font-size: 8.5pt; overflow-x: auto; page-break-inside: avoid; }
pre code { background: transparent; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 10pt; page-break-inside: avoid; }
th, td { border: 1px solid #cbd5e1; padding: 6px 10px; text-align: left; vertical-align: top; }
th { background: #e3f2fd; font-weight: 600; }
a { color: #1976d2; text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid #cbd5e1; margin: 18px 0; }
ul, ol { margin: 6px 0 6px 20px; }
li { margin: 3px 0; }
blockquote { border-left: 3px solid #1976d2; padding: 4px 12px; margin: 10px 0; background: #f8fafc; color: #475569; }
"""


def convert(md_path, pdf_name, lang):
    md_text = md_path.read_text(encoding="utf-8")

    md = markdown.Markdown(
        extensions=["toc", "tables", "fenced_code", "sane_lists"],
        extension_configs={
            "toc": {"slugify": github_slugify, "permalink": False},
        },
    )
    html_body = md.convert(md_text)

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>{md_path.stem}</title>
<style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    html_tmp = OUT_DIR / (md_path.stem + "_tmp.html")
    html_tmp.write_text(html, encoding="utf-8")

    out_pdf = OUT_DIR / pdf_name

    win_html = subprocess.check_output(
        ["wslpath", "-w", str(html_tmp)], text=True
    ).strip()
    win_pdf = subprocess.check_output(
        ["wslpath", "-w", str(out_pdf)], text=True
    ).strip()

    chrome = "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={win_pdf}",
        f"file:///{win_html.replace(chr(92), '/')}",
    ]
    print(f"Converting {md_path.name} -> {out_pdf}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    html_tmp.unlink(missing_ok=True)
    if result.returncode != 0 or not out_pdf.exists():
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        raise RuntimeError(f"Chrome failed for {md_path.name}")
    print(f"  OK: {out_pdf} ({out_pdf.stat().st_size // 1024} KB)")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for md_name, pdf_name, lang in FILES:
        convert(DOCS / md_name, pdf_name, lang)


if __name__ == "__main__":
    main()
