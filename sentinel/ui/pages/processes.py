from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...core import metrics as M
from ..widgets import Card, Worker, muted, page_header
from .disk import NumItem, table

REFRESH_SECONDS = 2.0


class ProcessesPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.worker: Optional[Worker] = None
        self._last = 0.0
        self.procs: list[M.ProcInfo] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("İşlem Yöneticisi",
                                  "Çalışan işlemler. Liste yalnızca bu sayfa açıkken 2 saniyede bir yenilenir."))
        card = Card()
        row = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("🔍  İşlem adı veya PID ile filtrele…")
        self.filter.textChanged.connect(self.render)
        self.end_btn = QPushButton("İşlemi sonlandır")
        self.end_btn.setObjectName("Danger")
        self.end_btn.setEnabled(False)
        self.end_btn.clicked.connect(self.end_selected)
        row.addWidget(self.filter, 1)
        row.addWidget(self.end_btn)
        card.body.addLayout(row)
        self.table = table(["Ad", "PID", "CPU %", "Bellek", "Kullanıcı", "Durum"])
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.sortByColumn(2, Qt.DescendingOrder)
        self.table.itemSelectionChanged.connect(lambda: self.end_btn.setEnabled(bool(self.selected())))
        card.body.addWidget(self.table, 1)
        self.status = muted("")
        card.body.addWidget(self.status)
        lay.addWidget(card, 1)

    # ---------- veri ----------
    def on_show(self) -> None:
        self._last = 0
        self._load()

    def update_snapshot(self, _s) -> None:
        if time.time() - self._last >= REFRESH_SECONDS:
            self._load()

    def _load(self) -> None:
        if self.worker is not None:
            return
        self._last = time.time()
        self.worker = Worker(lambda _c, _p: M.list_processes(), self)
        self.worker.succeeded.connect(self._loaded)
        self.worker.failed.connect(lambda m: self.status.setText("Hata: " + m))
        self.worker.finished.connect(self._done)
        self.worker.start()

    def _loaded(self, procs) -> None:
        self.procs = procs
        self.render()

    def _done(self) -> None:
        self.worker = None

    def render(self) -> None:
        q = self.filter.text().strip().lower()
        procs = [p for p in self.procs if not q or q in p.name.lower() or q == str(p.pid)]
        sel = self.selected()
        t = self.table
        t.setUpdatesEnabled(False)
        t.setSortingEnabled(False)
        t.setRowCount(len(procs))
        for r, p in enumerate(procs):
            name = QTableWidgetItem(p.name)
            name.setData(Qt.UserRole, p.pid)
            t.setItem(r, 0, name)
            t.setItem(r, 1, NumItem(str(p.pid), p.pid))
            t.setItem(r, 2, NumItem(f"{p.cpu:.1f}".replace(".", ","), p.cpu))
            t.setItem(r, 3, NumItem(M.human_bytes(p.memory), p.memory))
            t.setItem(r, 4, QTableWidgetItem(p.user or "–"))
            t.setItem(r, 5, QTableWidgetItem(p.status))
        t.setSortingEnabled(True)
        if sel:
            for r in range(t.rowCount()):
                if t.item(r, 0).data(Qt.UserRole) == sel[0]:
                    t.selectRow(r)
                    break
        t.setUpdatesEnabled(True)
        total_mem = sum(p.memory for p in self.procs)
        self.status.setText(f"{len(procs)} / {len(self.procs)} işlem gösteriliyor • toplam bellek {M.human_bytes(total_mem)}")

    def selected(self) -> Optional[tuple[int, str]]:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return (item.data(Qt.UserRole), item.text()) if item else None

    # ---------- sonlandırma (yalnızca onayla) ----------
    def end_selected(self) -> None:
        sel = self.selected()
        if not sel:
            return
        pid, name = sel
        if M.is_protected(pid, name):
            QMessageBox.warning(self, "Engellendi", f"{name} (PID {pid}) kritik bir sistem işlemi veya Sentinel'in kendisi; sonlandırılamaz.")
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("İşlemi sonlandır")
        box.setText(f"{name} (PID {pid}) sonlandırılsın mı?\n\nKaydedilmemiş veriler kaybolabilir.")
        yes = box.addButton("Sonlandır", QMessageBox.DestructiveRole)
        box.addButton("Vazgeç", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return
        try:
            msg = M.terminate_process(pid)
        except M.ProcessActionError as e:
            if "zorla" in str(e):
                if QMessageBox.question(self, "Yanıt yok", f"{e}\n\nZorla sonlandırılsın mı?") == QMessageBox.Yes:
                    try:
                        msg = M.terminate_process(pid, force=True)
                    except M.ProcessActionError as e2:
                        QMessageBox.critical(self, "Sonlandırılamadı", str(e2))
                        return
                else:
                    return
            else:
                QMessageBox.critical(self, "Sonlandırılamadı", str(e))
                return
        self.main.statusBar().showMessage(msg, 5000)
        self._last = 0
        self._load()

    def shutdown(self) -> None:
        if self.worker:
            self.worker.wait(3000)
