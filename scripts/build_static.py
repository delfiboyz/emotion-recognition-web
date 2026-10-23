"""Bangun versi statis (tanpa server Python) untuk GitHub Pages.

    python scripts/build_static.py [folder_output]   # default: _site

Halaman dirender dari templates/index.html dengan mode "static", sehingga
analisis emosi berjalan di browser (face-api) dan riwayat disimpan di
localStorage. Semua path dibuat relatif agar jalan di sub-path
(https://<user>.github.io/<repo>/).
"""

import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


def url_for(endpoint, filename):
    assert endpoint == "static", endpoint
    return f"static/{filename}"


def build(out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "static", out / "static")
    # Service worker harus berada di root situs agar scope-nya mencakup halaman.
    shutil.move(out / "static" / "sw.js", out / "sw.js")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    html = env.get_template("index.html").render(url_for=url_for, app_mode="static")
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / ".nojekyll").write_text("")
    return out


if __name__ == "__main__":
    target = build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "_site")
    print(f"Situs statis dibuat di {target}")
