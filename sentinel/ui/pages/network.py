from __future__ import annotations

import time

from PySide6.QtWidgets import QGridLayout, QTableWidgetItem, QVBoxLayout, QWidget

from ...core import metrics as M
from .. import theme
from ..widgets import Card, LineChart, StatTile, page_header, scroll
from .disk import NumItem, table


class NetworkPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._adapters_at = 0.0
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(page_header("Ağ", "Anlık indirme/yükleme hızı, toplam trafik ve ağ adaptörleri."))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.t_down = StatTile("İndirme hızı", "⬇️")
        self.t_up = StatTile("Yükleme hızı", "⬆️")
        self.t_recv = StatTile("Toplam alınan", "📥")
        self.t_sent = StatTile("Toplam gönderilen", "📤")
        for i, t in enumerate((self.t_down, self.t_up, self.t_recv, self.t_sent)):
            grid.addWidget(t, 0, i)
        lay.addLayout(grid)
        c = Card("Trafik (son 2 dakika)")
        self.chart = LineChart(y_max=None, y_format=lambda v: M.human_bytes(v, True))
        c.body.addWidget(self.chart)
        lay.addWidget(c, 1)
        ac = Card("Ağ adaptörleri")
        self.table = table(["Adaptör", "Durum", "Hız", "IPv4", "MAC", "Alınan", "Gönderilen"])
        self.table.setMinimumHeight(200)
        ac.body.addWidget(self.table)
        lay.addWidget(ac)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(content))

    def on_show(self) -> None:
        self.refresh_adapters()

    def refresh_adapters(self) -> None:
        self._adapters_at = time.time()
        ads = M.adapters()
        t = self.table
        t.setRowCount(len(ads))
        for r, a in enumerate(ads):
            t.setItem(r, 0, QTableWidgetItem(a.name))
            t.setItem(r, 1, QTableWidgetItem("🟢 Bağlı" if a.is_up else "⚪ Bağlı değil"))
            t.setItem(r, 2, QTableWidgetItem(f"{a.speed_mbps} Mbps" if a.speed_mbps else "–"))
            t.setItem(r, 3, QTableWidgetItem(", ".join(a.ipv4) or "–"))
            t.setItem(r, 4, QTableWidgetItem(a.mac or "–"))
            t.setItem(r, 5, NumItem(M.human_bytes(a.bytes_recv), a.bytes_recv))
            t.setItem(r, 6, NumItem(M.human_bytes(a.bytes_sent), a.bytes_sent))

    def update_snapshot(self, s) -> None:
        self.t_down.set(M.human_bytes(s.net_down, True))
        self.t_up.set(M.human_bytes(s.net_up, True))
        self.t_recv.set(M.human_bytes(s.net_total_recv), "açılıştan beri")
        self.t_sent.set(M.human_bytes(s.net_total_sent), "açılıştan beri")
        h = self.main.monitor.history
        self.chart.set_series([("İndirme", theme.BLUE, h["down"]), ("Yükleme", theme.GREEN, h["up"])])
        if time.time() - self._adapters_at > 5:
            self.refresh_adapters()
