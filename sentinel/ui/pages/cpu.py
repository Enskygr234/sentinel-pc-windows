from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...core import metrics as M
from ...core.sysinfo import cpu_model
from .. import theme
from ..widgets import Card, CoreBars, LineChart, StatTile, muted, page_header, scroll


class CpuPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        st = M.cpu_static()
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(page_header("İşlemci", cpu_model()))

        grid = QGridLayout()
        grid.setSpacing(12)
        self.t_usage = StatTile("Kullanım", "📈")
        self.t_cores = StatTile("Çekirdek / Thread", "🧩")
        self.t_freq = StatTile("Frekans", "⚡")
        self.t_temp = StatTile("Sıcaklık", "🌡️")
        cores = st.physical_cores if st.physical_cores else "?"
        self.t_cores.set(f"{cores} / {st.logical_cores}", "fiziksel çekirdek / mantıksal işlemci")
        for i, t in enumerate((self.t_usage, self.t_cores, self.t_freq, self.t_temp)):
            grid.addWidget(t, 0, i)
        lay.addLayout(grid)

        c = Card("Toplam kullanım (son 2 dakika)")
        self.chart = LineChart()
        c.body.addWidget(self.chart)
        lay.addWidget(c, 1)
        cc = Card("Çekirdek başına kullanım")
        self.bars = CoreBars()
        self.bars.setMinimumHeight(110 if st.logical_cores <= 16 else 200)
        cc.body.addWidget(self.bars)
        lay.addWidget(cc)

        tc = Card("Sıcaklık sensörleri")
        self.temp_detail = muted("Kontrol ediliyor…")
        tc.body.addWidget(self.temp_detail)
        lay.addWidget(tc)
        self.freq_note = muted(
            "Not: Windows bazı işlemcilerde anlık frekans yerine temel frekansı bildirir; gösterilen değer "
            "işletim sisteminin raporladığı değerdir.")
        lay.addWidget(self.freq_note)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(content))
        self.t_temp.set("…", "")

    def update_snapshot(self, s) -> None:
        self.t_usage.set(f"%{s.cpu_percent:.0f}", f"{s.process_count} işlem")
        if s.cpu_freq_mhz:
            mx = f" / maks {s.cpu_freq_max_mhz / 1000:.2f} GHz".replace(".", ",") if s.cpu_freq_max_mhz else ""
            self.t_freq.set(f"{s.cpu_freq_mhz / 1000:.2f} GHz".replace(".", ","), "Bildirilen" + mx)
        else:
            self.t_freq.set("Okunamıyor", "İşletim sistemi frekans bildirmiyor")
        self.chart.set_series([("CPU", theme.PURPLE, self.main.monitor.history["cpu"])])
        self.bars.set_values(s.per_cpu)

    def update_temperature(self, r) -> None:
        if r.supported:
            self.t_temp.set(f"{r.max_c:.0f} °C", "en yüksek sensör")
            self.temp_detail.setText(f"Kaynak: {r.source}\n" + "\n".join(f"• {n}: {t:.1f} °C" for n, t in r.sensors))
        else:
            self.t_temp.set("Desteklenmiyor", "sensör okunamadı")
            self.temp_detail.setText(r.reason)
