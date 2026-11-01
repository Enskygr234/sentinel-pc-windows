from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLineEdit, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...core import metrics as M
from .. import theme
from ..widgets import Card, LineChart, Worker, muted, page_header, scroll


class NumItem(QTableWidgetItem):
    def __init__(self, text: str, value: float):
        super().__init__(text)
        self.setData(Qt.UserRole, value)
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, other):  # noqa: D105
        return (self.data(Qt.UserRole) or 0) < (other.data(Qt.UserRole) or 0)


def table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    return t


class DiskPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.worker: Optional[Worker] = None
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(page_header("Diskler", "Disk bölümleri, doluluk, okuma/yazma hızı ve klasör boyutu analizi."))

        pc = Card("Disk bölümleri")
        self.parts = table(["Sürücü", "Dosya sistemi", "Toplam", "Kullanılan", "Boş", "Doluluk", ""])
        self.parts.setMinimumHeight(170)
        pc.body.addWidget(self.parts)
        refresh = QPushButton("Yenile")
        refresh.clicked.connect(self.refresh_partitions)
        pc.body.addWidget(refresh)
        lay.addWidget(pc)

        ic = Card("Disk okuma / yazma (son 2 dakika)")
        self.io_chart = LineChart(y_max=None, y_format=lambda v: M.human_bytes(v, True))
        ic.body.addWidget(self.io_chart)
        lay.addWidget(ic)

        fc = Card("Klasör boyutu analizi")
        row = QHBoxLayout()
        self.path = QLineEdit(os.path.expanduser("~"))
        browse = QPushButton("Gözat…")
        browse.clicked.connect(self._browse)
        self.scan_btn = QPushButton("Analiz et")
        self.scan_btn.setObjectName("Primary")
        self.scan_btn.clicked.connect(self.scan)
        self.stop_btn = QPushButton("Durdur")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(lambda: self.worker and self.worker.cancel())
        for w in (self.path, browse, self.scan_btn, self.stop_btn):
            row.addWidget(w, 1 if w is self.path else 0)
        fc.body.addLayout(row)
        self.scan_status = muted("Salt okunur tarama: hiçbir dosya değiştirilmez.")
        fc.body.addWidget(self.scan_status)
        self.folders = table(["Öğe", "Boyut", "Pay"])
        self.folders.setSortingEnabled(True)
        self.folders.setMinimumHeight(220)
        self.folders.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        fc.body.addWidget(self.folders)
        lay.addWidget(fc)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(content))
        self.refresh_partitions()

    def on_show(self) -> None:
        self.refresh_partitions()

    def refresh_partitions(self) -> None:
        parts = M.partitions()
        t = self.parts
        t.setRowCount(len(parts))
        for r, p in enumerate(parts):
            label = p.mountpoint if p.mountpoint == p.device or os.name == "nt" else f"{p.mountpoint} ({p.device})"
            t.setItem(r, 0, QTableWidgetItem(label))
            t.setItem(r, 1, QTableWidgetItem(p.fstype))
            t.setItem(r, 2, NumItem(M.human_bytes(p.total), p.total))
            t.setItem(r, 3, NumItem(M.human_bytes(p.used), p.used))
            t.setItem(r, 4, NumItem(M.human_bytes(p.free), p.free))
            t.setItem(r, 5, NumItem(f"%{p.percent:.1f}".replace(".", ","), p.percent))
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(int(p.percent * 10))
            bar.setMaximumHeight(10)
            if p.percent >= 90:
                bar.setStyleSheet(f"QProgressBar::chunk {{ background: {theme.RED}; border-radius: 5px; }}")
            t.setCellWidget(r, 6, bar)

    def update_snapshot(self, s) -> None:
        h = self.main.monitor.history
        self.io_chart.set_series([("Okuma", theme.PURPLE, h["read"]), ("Yazma", theme.AMBER, h["write"])])

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Klasör seç", self.path.text())
        if d:
            self.path.setText(os.path.normpath(d))

    def scan(self) -> None:
        root = self.path.text().strip().strip('"')
        if not os.path.isdir(root):
            self.scan_status.setText("Geçerli bir klasör seçin.")
            return
        self.worker = Worker(lambda cancel, progress: M.folder_sizes(root, cancel, progress), self)
        self.worker.progress.connect(self.scan_status.setText)
        self.worker.succeeded.connect(self._show)
        self.worker.failed.connect(lambda m: self.scan_status.setText("Hata: " + m))
        self.worker.finished.connect(self._finished)
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.scan_status.setText("Taranıyor…")
        self.worker.start()

    def _show(self, result) -> None:
        total, items = result
        t = self.folders
        t.setSortingEnabled(False)
        t.setRowCount(len(items))
        for r, (name, size, is_dir) in enumerate(items):
            t.setItem(r, 0, QTableWidgetItem(("📁 " if is_dir else "📄 ") + name))
            t.setItem(r, 1, NumItem(M.human_bytes(size), size))
            pct = size / total * 100 if total else 0
            t.setItem(r, 2, NumItem(f"%{pct:.1f}".replace(".", ","), pct))
        t.setSortingEnabled(True)
        cancelled = self.worker is not None and self.worker.cancel_event.is_set()
        self.scan_status.setText(("Durduruldu (kısmi sonuç). " if cancelled else "") +
                                 f"Toplam: {M.human_bytes(total)} • {len(items)} öğe")

    def _finished(self) -> None:
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.worker = None

    def shutdown(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.worker.wait(3000)
