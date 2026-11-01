from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from ...core.metrics import human_bytes
from .. import theme
from ..widgets import Card, Gauge, LineChart, StatTile, muted, page_header, scroll


class RamPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(page_header("Bellek (RAM)", "Fiziksel bellek ve sayfa dosyası (swap) kullanımı."))
        top = QHBoxLayout()
        gcard = Card()
        self.gauge = Gauge("RAM kullanımı")
        gcard.body.addWidget(self.gauge)
        top.addWidget(gcard, 1)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.t_total = StatTile("Toplam RAM", "💾")
        self.t_used = StatTile("Kullanılan", "🟣")
        self.t_free = StatTile("Boş (kullanılabilir)", "🟢")
        self.t_swap = StatTile("Sayfa dosyası / swap", "🔄")
        for i, t in enumerate((self.t_total, self.t_used, self.t_free, self.t_swap)):
            grid.addWidget(t, i // 2, i % 2)
        top.addLayout(grid, 2)
        lay.addLayout(top)
        bar_card = Card("Doluluk")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        bar_card.body.addWidget(self.bar)
        bar_card.body.addWidget(muted("\"Boş\" değeri, Windows'un uygulamalara hemen verebileceği belleği "
                                      "(önbellek dahil, kullanılabilir bellek) gösterir."))
        lay.addWidget(bar_card)
        c = Card("RAM grafiği (son 2 dakika)")
        self.chart = LineChart()
        c.body.addWidget(self.chart)
        lay.addWidget(c, 1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(content))

    def update_snapshot(self, s) -> None:
        self.gauge.set(s.mem_percent, sub=f"{human_bytes(s.mem_used)} kullanımda")
        self.t_total.set(human_bytes(s.mem_total))
        self.t_used.set(human_bytes(s.mem_used), f"%{s.mem_percent:.1f}".replace(".", ","))
        self.t_free.set(human_bytes(s.mem_available), f"%{100 - s.mem_percent:.1f}".replace(".", ","))
        if s.swap_total:
            self.t_swap.set(human_bytes(s.swap_used), f"{human_bytes(s.swap_total)} içinden • %{s.swap_percent:.0f}")
        else:
            self.t_swap.set("Yok", "Sayfa dosyası/swap yapılandırılmamış")
        self.bar.setValue(int(s.mem_percent * 10))
        self.chart.set_series([("RAM", theme.CYAN, self.main.monitor.history["ram"])])
