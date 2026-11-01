from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ...core.metrics import format_uptime, human_bytes
from .. import theme
from ..widgets import Card, Gauge, LineChart, StatTile, muted, page_header, scroll


class DashboardPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(page_header("Gösterge Paneli", "Canlı sistem durumu. Değerler her saniye gerçek donanımdan okunur."))

        gauges = Card()
        row = QHBoxLayout()
        self.g_cpu = Gauge("İşlemci")
        self.g_ram = Gauge("Bellek")
        self.g_disk = Gauge("Sistem diski")
        for g in (self.g_cpu, self.g_ram, self.g_disk):
            row.addWidget(g)
        gauges.body.addLayout(row)
        lay.addWidget(gauges)

        tiles = QGridLayout()
        tiles.setSpacing(12)
        self.t_down = StatTile("İndirme", "⬇️")
        self.t_up = StatTile("Yükleme", "⬆️")
        self.t_uptime = StatTile("Çalışma süresi", "⏱️")
        self.t_temp = StatTile("Sıcaklık", "🌡️")
        for i, t in enumerate((self.t_down, self.t_up, self.t_uptime, self.t_temp)):
            tiles.addWidget(t, 0, i)
        lay.addLayout(tiles)

        c1 = Card("İşlemci ve bellek (son 2 dakika)")
        self.chart = LineChart()
        c1.body.addWidget(self.chart)
        c2 = Card("Ağ trafiği (son 2 dakika)")
        self.net_chart = LineChart(y_max=None, y_format=lambda v: human_bytes(v, True))
        c2.body.addWidget(self.net_chart)
        charts = QHBoxLayout()
        charts.addWidget(c1, 1)
        charts.addWidget(c2, 1)
        lay.addLayout(charts, 1)
        self.note = muted("")
        lay.addWidget(self.note)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(content))
        self.t_temp.set("…", "Sensörler kontrol ediliyor")

    def update_snapshot(self, s) -> None:
        self.g_cpu.set(s.cpu_percent, sub=f"{len(s.per_cpu)} mantıksal işlemci")
        used_gb = s.mem_used / 1024 ** 3
        self.g_ram.set(s.mem_percent, sub=f"{used_gb:.1f} / {s.mem_total / 1024 ** 3:.1f} GB".replace(".", ","))
        self.g_disk.set(s.disk_percent, sub=self.main.monitor.system_drive)
        self.t_down.set(human_bytes(s.net_down, True), f"Toplam alınan: {human_bytes(s.net_total_recv)}")
        self.t_up.set(human_bytes(s.net_up, True), f"Toplam gönderilen: {human_bytes(s.net_total_sent)}")
        self.t_uptime.set(format_uptime(s.uptime), f"{s.process_count} çalışan işlem")
        h = self.main.monitor.history
        self.chart.set_series([("CPU", theme.PURPLE, h["cpu"]), ("RAM", theme.CYAN, h["ram"])])
        self.net_chart.set_series([("İndirme", theme.BLUE, h["down"]), ("Yükleme", theme.GREEN, h["up"])])

    def update_temperature(self, r) -> None:
        if r.supported and r.max_c is not None:
            self.t_temp.set(f"{r.max_c:.0f} °C", r.source.split(" (")[0])
        else:
            self.t_temp.set("Desteklenmiyor", "Ayrıntı: İşlemci sayfası")
