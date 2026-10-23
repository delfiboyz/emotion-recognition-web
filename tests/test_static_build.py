import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_static import build  # noqa: E402


def test_static_build_uses_relative_paths(tmp_path):
    out = build(tmp_path / "site")
    html = (out / "index.html").read_text()
    assert '<meta name="app-mode" content="static">' in html
    assert 'src="static/js/app.js"' in html
    # Path absolut akan rusak di sub-path GitHub Pages (/<repo>/).
    assert '"/static/' not in html
    assert (out / "sw.js").exists() and not (out / "static" / "sw.js").exists()
    assert (out / ".nojekyll").exists()
    models = out / "static" / "vendor" / "face-api" / "models"
    for name in ("tiny_face_detector", "ssd_mobilenetv1", "face_expression", "age_gender"):
        assert (models / f"{name}_model-weights_manifest.json").exists()
        assert (models / f"{name}_model.bin").exists()
