"""Sentinel ana penceresi: tek zamanlayıcıyla örnekleme, yalnızca görünen sayfayı güncelleme."""
from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__
from ..core.history import Aggregator, HistoryStore
from ..core.metrics import Monitor, Snapshot, human_bytes
from ..core.temperature import TempReading
from .widgets import Worker

NAV = [
    ("dashboard", "📊  Gösterge Paneli"),
    ("cpu", "🧠  İşlemci"),
    ("ram", "💾  Bellek (RAM)"),
    ("disk", "🗄️  Diskler"),
    ("network", "🌐  Ağ"),
    ("processes", "⚙️  İşlemler"),
    ("sysinfo", "🖥️  Sistem Bilgisi"),
    ("reports", "📑  Raporlar"),
]


class MainWindow(QMainWindow):
    snapshot_ready = Signal(object)

    def __init__(self, store: Optional[HistoryStore] = None, interval_ms: int = 1000):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1240, 800)
        self.setMinimumSize(980, 640)
        self.monitor = Monitor(history=120)
        self.store = store or HistoryStore()
        self.aggregator = Aggregator(interval=5.0)
        self.last: Optional[Snapshot] = None
        self.temp: Optional[TempReading] = None
        self._temp_worker: Optional[Worker] = None
        self._temp_checked = 0.0

        from .pages.cpu import CpuPage
        from .pages.dashboard import DashboardPage
        from .pages.disk import DiskPage
        from .pages.network import NetworkPage
        from .pages.processes import ProcessesPage
        from .pages.reports import ReportsPage
        from .pages.sysinfo import SysInfoPage
        from .pages.ram import RamPage

        self.pages: dict[str, QWidget] = {
            "dashboard": DashboardPage(self), "cpu": CpuPage(self), "ram": RamPage(self),
            "disk": DiskPage(self), "network": NetworkPage(self), "processes": ProcessesPage(self),
            "sysinfo": SysInfoPage(self), "reports": ReportsPage(self),
        }

        root = QWidget()
        root.setObjectName("Root")
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        side_w = QWidget()
        side_w.setObjectName("Sidebar")
        side_w.setFixedWidth(220)
        side = QVBoxLayout(side_w)
        side.setContentsMargins(12, 16, 12, 12)
        side.setSpacing(4)
        logo = QLabel("◉ Sentinel PC")
        logo.setObjectName("Logo")
        sub = QLabel("Gerçek zamanlı sistem monitörü")
        sub.setObjectName("LogoSub")
        side.addWidget(logo)
        side.addWidget(sub)
        self.group = QButtonGroup(self)
        self.buttons: dict[str, QPushButton] = {}
        for i, (key, label) in enumerate(NAV):
            b = QPushButton(label)
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.navigate(k))
            self.group.addButton(b)
            self.buttons[key] = b
            side.addWidget(b)
            act = QAction(self)
            act.setShortcut(QKeySequence(f"Ctrl+{i + 1}"))
            act.triggered.connect(lambda _=False, k=key: self.navigate(k))
            self.addAction(act)
        side.addStretch(1)
        self.side_status = QLabel("")
        self.side_status.setObjectName("LogoSub")
        self.side_status.setWordWrap(True)
        side.addWidget(self.side_status)
        side.addWidget(QLabel(f"Sürüm {__version__}", objectName="LogoSub"))

        self.stack = QStackedWidget()
        for p in self.pages.values():
            self.stack.addWidget(p)
        lay.addWidget(side_w)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())

        self.current = ""
        self._anim: Optional[QPropertyAnimation] = None
        self.navigate("dashboard", animate=False)

        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        QTimer.singleShot(150, self.tick)
        self.refresh_temperature()

    # ---------- örnekleme ----------
    def tick(self) -> None:
        try:
            snap = self.monitor.sample()
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(f"Ölçüm hatası: {e}", 5000)
            return
        self.last = snap
        agg = self.aggregator.add(snap.ts, (snap.cpu_percent, snap.mem_percent, snap.net_down,
                                            snap.net_up, snap.disk_read, snap.disk_write))
        if agg is not None:
            try:
                self.store.add(agg)
            except Exception as e:  # noqa: BLE001
                self.statusBar().showMessage(f"Geçmiş kaydedilemedi: {e}", 5000)
        if time.time() - self._temp_checked > 15 and (self.temp is None or self.temp.supported):
            self.refresh_temperature()
        page = self.pages.get(self.current)
        if page is not None and hasattr(page, "update_snapshot") and not self.isMinimized():
            page.update_snapshot(snap)
        self.side_status.setText(
            f"CPU %{snap.cpu_percent:.0f}  •  RAM %{snap.mem_percent:.0f}\n"
            f"↓ {human_bytes(snap.net_down, True)}  ↑ {human_bytes(snap.net_up, True)}")
        self.snapshot_ready.emit(snap)

    def refresh_temperature(self) -> None:
        if self._temp_worker is not None:
            return
        from ..core.temperature import read_temperatures
        self._temp_checked = time.time()
        self._temp_worker = Worker(lambda _c, _p: read_temperatures(), self)
        self._temp_worker.succeeded.connect(self._temp_done)
        self._temp_worker.finished.connect(self._temp_finished)
        self._temp_worker.start()

    def _temp_done(self, reading: TempReading) -> None:
        self.temp = reading
        for p in self.pages.values():
            if hasattr(p, "update_temperature"):
                p.update_temperature(reading)

    def _temp_finished(self) -> None:
        self._temp_worker = None

    # ---------- navigasyon ----------
    def navigate(self, key: str, animate: bool = True) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.buttons[key].setChecked(True)
        if key == self.current:
            return
        old = self.pages.get(self.current)
        if old is not None and hasattr(old, "on_hide"):
            old.on_hide()
        self.stack.setCurrentWidget(page)
        self.current = key
        if animate:
            eff = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(200)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda w=page: w.setGraphicsEffect(None))
            anim.start()
            self._anim = anim
        if hasattr(page, "on_show"):
            page.on_show()
        if self.last is not None and hasattr(page, "update_snapshot"):
            page.update_snapshot(self.last)
        self.statusBar().showMessage(dict(NAV)[key].split("  ", 1)[1])

    def shutdown(self) -> None:
        self.timer.stop()
        for p in self.pages.values():
            if hasattr(p, "shutdown"):
                p.shutdown()
        if self._temp_worker is not None:
            self._temp_worker.wait(10000)

    def closeEvent(self, e) -> None:  # noqa: N802
        self.shutdown()
        super().closeEvent(e)
