from __future__ import annotations

import os
import time
from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ...core import history as H
from ...core import sysinfo as S
from ...core.metrics import human_bytes, partitions
from .. import theme
from ..widgets import Card, LineChart, StatTile, muted, page_header, scroll

RANGES = [("Son 15 dakika", 900), ("Son 1 saat", 3600), ("Son 6 saat", 6 * 3600),
          ("Son 24 saat", 86400), ("Son 7 gün", 7 * 86400)]


class ReportsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._shown_at = 0.0
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(page_header(
            "Raporlar",
            f"CPU ve RAM geçmişi, uygulama açıkken 5 saniyelik ortalamalarla kaydedilir ve {H.RETENTION_DAYS} gün saklanır."))
        row = QHBoxLayout()
        self.range = QComboBox()
        for label, secs in RANGES:
            self.range.addItem(label, secs)
        self.range.setCurrentIndex(1)
        self.range.currentIndexChanged.connect(self.refresh)
        csv_btn = QPushButton("CSV olarak dışa aktar…")
        csv_btn.setObjectName("Primary")
        csv_btn.clicked.connect(self.export_csv)
        rep_btn = QPushButton("Sistem raporu kaydet…")
        rep_btn.clicked.connect(self.save_report)
        clear_btn = QPushButton("Geçmişi temizle")
        clear_btn.setObjectName("Danger")
        clear_btn.clicked.connect(self.clear)
        for w in (self.range, csv_btn, rep_btn, clear_btn):
            row.addWidget(w)
        row.addStretch(1)
        lay.addLayout(row)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.t_cpu = StatTile("CPU ortalama / en yüksek", "🧠")
        self.t_ram = StatTile("RAM ortalama / en yüksek", "💾")
        self.t_count = StatTile("Kayıt sayısı", "🗂️")
        for i, t in enumerate((self.t_cpu, self.t_ram, self.t_count)):
            grid.addWidget(t, 0, i)
        lay.addLayout(grid)
        c1 = Card("CPU geçmişi")
        self.cpu_chart = LineChart(points=2)
        c1.body.addWidget(self.cpu_chart)
        c2 = Card("RAM geçmişi")
        self.ram_chart = LineChart(points=2)
        c2.body.addWidget(self.ram_chart)
        lay.addWidget(c1, 1)
        lay.addWidget(c2, 1)
        self.note = muted(f"Veri dosyası: {self.main.store.path}")
        lay.addWidget(self.note)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(content))

    def _samples(self):
        return self.main.store.query(time.time() - self.range.currentData())

    def on_show(self) -> None:
        self.refresh()

    def update_snapshot(self, _s) -> None:
        if time.time() - self._shown_at > 10:
            self.refresh()

    def refresh(self) -> None:
        self._shown_at = time.time()
        samples = self._samples()
        summ = H.summarize(samples)
        if summ["count"]:
            self.t_cpu.set(f"%{summ['cpu_avg']:.0f} / %{summ['cpu_max']:.0f}")
            self.t_ram.set(f"%{summ['ram_avg']:.0f} / %{summ['ram_max']:.0f}")
            first = datetime.fromtimestamp(summ["start"]).strftime("%d.%m %H:%M")
            self.t_count.set(str(summ["count"]), f"ilk kayıt: {first}")
        else:
            self.t_cpu.set("–")
            self.t_ram.set("–")
            self.t_count.set("0", "İlk kayıt 5 saniye içinde oluşur")
        pts = H.downsample(samples, 300)
        labels = (datetime.fromtimestamp(pts[0].ts).strftime("%d.%m %H:%M"), "şimdi") if pts else ("", "")
        self.cpu_chart.set_series([("CPU", theme.PURPLE, [p.cpu for p in pts])], labels)
        self.ram_chart.set_series([("RAM", theme.CYAN, [p.ram for p in pts])], labels)

    def export_csv(self) -> None:
        samples = self._samples()
        if not samples:
            QMessageBox.information(self, "Veri yok", "Seçilen aralıkta kayıt yok.")
            return
        default = os.path.join(os.path.expanduser("~"), f"sentinel_gecmis_{datetime.now():%Y%m%d_%H%M}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "CSV kaydet", default, "CSV dosyası (*.csv)")
        if not path:
            return
        try:
            n = H.export_csv(samples, path)
        except OSError as e:
            QMessageBox.critical(self, "Hata", f"Kaydedilemedi:\n{e}")
            return
        self.main.statusBar().showMessage(f"{n} kayıt dışa aktarıldı: {path}", 6000)

    def report_text(self) -> str:
        sysinfo_page = self.main.pages["sysinfo"]
        info = sysinfo_page.info or {"Genel": S.basic_info()}
        s = self.main.last
        live = {}
        if s is not None:
            live = {
                "CPU kullanımı": f"%{s.cpu_percent:.1f}",
                "RAM kullanımı": f"%{s.mem_percent:.1f} ({human_bytes(s.mem_used)} / {human_bytes(s.mem_total)})",
                "Çalışan işlem": str(s.process_count),
            }
        temp = self.main.temp
        if temp is not None:
            live["Sıcaklık"] = (", ".join(f"{n}: {t:.1f} °C" for n, t in temp.sensors)
                                if temp.supported else "Desteklenmiyor")
        disks = {p.mountpoint: f"{human_bytes(p.used)} / {human_bytes(p.total)} (%{p.percent:.0f}) {p.fstype}"
                 for p in partitions()}
        summ = H.summarize(self.main.store.query(time.time() - 86400))
        return H.build_report(info, {"Anlık durum": live, "Diskler": disks}, summ)

    def save_report(self) -> None:
        default = os.path.join(os.path.expanduser("~"), f"sentinel_rapor_{datetime.now():%Y%m%d_%H%M}.txt")
        path, _ = QFileDialog.getSaveFileName(self, "Raporu kaydet", default, "Metin dosyası (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig") as fh:
                fh.write(self.report_text())
        except OSError as e:
            QMessageBox.critical(self, "Hata", f"Kaydedilemedi:\n{e}")
            return
        self.main.statusBar().showMessage(f"Rapor kaydedildi: {path}", 6000)

    def clear(self) -> None:
        if QMessageBox.question(self, "Geçmişi temizle", "Kayıtlı tüm CPU/RAM geçmişi silinsin mi?") != QMessageBox.Yes:
            return
        self.main.store.clear()
        self.refresh()
