from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...core import sysinfo as S
from ..widgets import Card, Worker, muted, page_header, scroll


class SysInfoPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.info: Optional[dict] = None
        self.worker: Optional[Worker] = None
        content = QWidget()
        self.lay = QVBoxLayout(content)
        self.lay.setContentsMargins(28, 24, 28, 24)
        self.lay.setSpacing(14)
        self.lay.addWidget(page_header("Sistem Bilgisi", "İşletim sistemi, işlemci, anakart, BIOS ve ekran kartı bilgileri."))
        row = QHBoxLayout()
        self.copy_btn = QPushButton("Panoya kopyala")
        self.copy_btn.clicked.connect(self.copy)
        self.reload_btn = QPushButton("Yenile")
        self.reload_btn.clicked.connect(self.load)
        row.addWidget(self.copy_btn)
        row.addWidget(self.reload_btn)
        row.addStretch(1)
        self.status = muted("")
        row.addWidget(self.status)
        self.lay.addLayout(row)
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        self.lay.addLayout(self.grid)
        self.lay.addWidget(muted(
            f"Yönetici izni: {'var' if S.is_admin() else 'yok (gerekmiyor)'} • Bilgiler Windows kayıt defteri ve "
            "CIM (WMI) üzerinden salt okunur olarak alınır."))
        self.lay.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(content))

    def on_show(self) -> None:
        if self.info is None:
            self.load()

    def load(self) -> None:
        if self.worker is not None:
            return
        self.status.setText("Bilgiler okunuyor…")
        self.reload_btn.setEnabled(False)
        self.worker = Worker(lambda _c, _p: S.full_info(), self)
        self.worker.succeeded.connect(self._show)
        self.worker.failed.connect(lambda m: self.status.setText("Hata: " + m))
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _finished(self) -> None:
        self.worker = None
        self.reload_btn.setEnabled(True)

    def _show(self, info: dict) -> None:
        self.info = info
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for i, (section, values) in enumerate(info.items()):
            card = Card(section)
            form = QFormLayout()
            form.setHorizontalSpacing(18)
            for k, v in values.items():
                val = QLabel(str(v))
                val.setWordWrap(True)
                val.setTextInteractionFlags(Qt.TextSelectableByMouse)
                form.addRow(muted(k), val)
            card.body.addLayout(form)
            self.grid.addWidget(card, i // 2, i % 2)
        self.status.setText("Güncel")

    def as_text(self) -> str:
        if not self.info:
            return ""
        lines = []
        for section, values in self.info.items():
            lines.append(f"[{section}]")
            lines += [f"{k}: {v}" for k, v in values.items()]
            lines.append("")
        return "\n".join(lines)

    def copy(self) -> None:
        if self.info:
            QApplication.clipboard().setText(self.as_text())
            self.main.statusBar().showMessage("Sistem bilgileri panoya kopyalandı.", 4000)

    def shutdown(self) -> None:
        if self.worker:
            self.worker.wait(15000)
