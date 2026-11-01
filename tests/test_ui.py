"""Arayüz duman testi: uygulamayı ekransız açar, gerçek verilerle tüm sayfaları dener."""
import json
import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_full_self_test(tmp_path):
    from PySide6.QtWidgets import QApplication

    from sentinel.selftest import run_self_test
    from sentinel.ui.theme import QSS

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(QSS)
    out = tmp_path / "report.json"
    code = run_self_test(app, str(out))
    report = json.loads(out.read_text(encoding="utf-8"))
    for r in report["results"]:
        print(("✓ " if r["ok"] else "✗ ") + r["test"], r.get("detail", ""), r.get("error", ""))
    failures = [f"{r['test']}: {r.get('error')}\n{r.get('trace', '')}" for r in report["results"] if not r["ok"]]
    assert code == 0, "\n\n".join(failures)
    assert report["total"] >= 10
