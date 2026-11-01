"""Sentinel arayüz bileşenleri: canlı çizgi grafik, dairesel gösterge, kartlar, arka plan işçisi."""
from __future__ import annotations

import threading
import traceback
from typing import Any, Callable, Iterable, Optional, Sequence

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from . import theme


class Card(QFrame):
    def __init__(self, title: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(8)
        if title:
            t = QLabel(title)
            t.setObjectName("CardTitle")
            self.body.addWidget(t)


def muted(text: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Muted")
    lbl.setWordWrap(True)
    return lbl


def page_header(title: str, subtitle: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    lay.addWidget(t)
    s = QLabel(subtitle)
    s.setObjectName("PageSubtitle")
    s.setWordWrap(True)
    lay.addWidget(s)
    return w


def scroll(content: QWidget) -> QScrollArea:
    a = QScrollArea()
    a.setWidgetResizable(True)
    a.setFrameShape(QFrame.NoFrame)
    a.setWidget(content)
    return a


class StatTile(Card):
    """Başlık + büyük değer + alt açıklama."""

    def __init__(self, title: str, icon: str = ""):
        super().__init__()
        row = QHBoxLayout()
        if icon:
            ic = QLabel(icon)
            ic.setStyleSheet("font-size: 20pt;")
            row.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.title = muted(title)
        self.value = QLabel("–")
        self.value.setObjectName("BigValue")
        self.sub = muted("")
        col.addWidget(self.title)
        col.addWidget(self.value)
        col.addWidget(self.sub)
        row.addLayout(col, 1)
        self.body.addLayout(row)

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value)
        self.sub.setText(sub)


class Gauge(QWidget):
    """Dairesel yüzde göstergesi (renk doluluğa göre değişir)."""

    def __init__(self, label: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.label = label
        self.value = 0.0
        self.text = "–"
        self.sub = ""
        self.setMinimumSize(QSize(150, 150))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set(self, percent: float, text: Optional[str] = None, sub: str = "") -> None:
        self.value = max(0.0, min(100.0, percent))
        self.text = text if text is not None else f"%{percent:.0f}"
        self.sub = sub
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(180, 180)

    def paintEvent(self, _e) -> None:  # noqa: N802
        side = min(self.width(), self.height()) - 18
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(theme.CARD2), 12)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 225 * 16, -270 * 16)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, QColor(theme.PURPLE))
        grad.setColorAt(1, QColor(theme.BLUE))
        brush = QBrush(grad) if self.value < 70 else QBrush(QColor(theme.level_color(self.value)))
        pen = QPen(brush, 12)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 225 * 16, int(-270 * 16 * self.value / 100))
        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setPointSizeF(max(12.0, side / 8.5))
        f.setBold(True)
        p.setFont(f)
        p.drawText(rect.adjusted(0, -side * 0.08, 0, -side * 0.08), Qt.AlignCenter, self.text)
        f2 = QFont(self.font())
        f2.setPointSizeF(max(8.5, side / 17))
        p.setFont(f2)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(rect.left(), rect.center().y() + side * 0.12, rect.width(), side * 0.15),
                   Qt.AlignHCenter | Qt.AlignTop, self.label)
        if self.sub:
            p.drawText(QRectF(rect.left(), rect.bottom() - side * 0.16, rect.width(), side * 0.16),
                       Qt.AlignHCenter | Qt.AlignBottom, self.sub)
        p.end()


class LineChart(QWidget):
    """Hafif canlı çizgi grafik (QPainter). Seriler: (ad, renk, değer listesi)."""

    def __init__(self, y_max: Optional[float] = 100.0, y_format: Callable[[float], str] = lambda v: f"%{v:.0f}",
                 points: int = 120, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.y_max_fixed = y_max
        self.y_format = y_format
        self.points = points
        self.series: list[tuple[str, str, Sequence[float]]] = []
        self.x_labels: tuple[str, str] = ("", "şimdi")
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_series(self, series: list[tuple[str, str, Iterable[float]]], x_labels: Optional[tuple[str, str]] = None) -> None:
        self.series = [(n, c, list(v)) for n, c, v in series]
        if x_labels:
            self.x_labels = x_labels
        if self.isVisible():
            self.update()

    def _ymax(self) -> float:
        if self.y_max_fixed is not None:
            return self.y_max_fixed
        peak = max((max(v) for _, _, v in self.series if v), default=0.0)
        nice = 1024.0  # en az 1 KB/s ölçek; zirvenin üstündeki ilk 2'nin kuvveti
        while nice < peak * 1.1:
            nice *= 2
        return nice

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left, right, top, bottom = 62, 10, 22, 22
        w, h = self.width() - left - right, self.height() - top - bottom
        if w <= 10 or h <= 10:
            return
        ymax = self._ymax() or 1
        small = QFont(self.font())
        small.setPointSizeF(8)
        p.setFont(small)
        # Izgara
        for i in range(5):
            y = top + h * i / 4
            p.setPen(QPen(QColor(theme.BORDER), 1, Qt.DashLine if i not in (0, 4) else Qt.SolidLine))
            p.drawLine(QPointF(left, y), QPointF(left + w, y))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, y - 8, left - 8, 16), Qt.AlignRight | Qt.AlignVCenter, self.y_format(ymax * (4 - i) / 4))
        p.drawText(QRectF(left, top + h + 4, 120, 16), Qt.AlignLeft, self.x_labels[0])
        p.drawText(QRectF(left + w - 120, top + h + 4, 120, 16), Qt.AlignRight, self.x_labels[1])
        # Seriler
        for idx, (name, color, values) in enumerate(self.series):
            if len(values) < 2:
                continue
            n = max(self.points, len(values))
            step = w / (n - 1)
            x0 = left + w - (len(values) - 1) * step
            path = QPainterPath()
            for i, v in enumerate(values):
                pt = QPointF(x0 + i * step, top + h - h * min(max(v, 0), ymax) / ymax)
                path.moveTo(pt) if i == 0 else path.lineTo(pt)
            if idx == 0:
                fill = QPainterPath(path)
                fill.lineTo(QPointF(x0 + (len(values) - 1) * step, top + h))
                fill.lineTo(QPointF(x0, top + h))
                fill.closeSubpath()
                g = QLinearGradient(0, top, 0, top + h)
                c1 = QColor(color)
                c1.setAlpha(90)
                c2 = QColor(color)
                c2.setAlpha(0)
                g.setColorAt(0, c1)
                g.setColorAt(1, c2)
                p.fillPath(fill, QBrush(g))
            p.setPen(QPen(QColor(color), 2))
            p.drawPath(path)
        # Gösterge
        x = left + 6
        for name, color, values in self.series:
            last = self.y_format(values[-1]) if values else "–"
            label = f"{name}: {last}"
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(x, 4, 10, 10), 3, 3)
            p.setPen(QColor(theme.TEXT))
            fm = p.fontMetrics()
            p.drawText(QPointF(x + 14, 13), label)
            x += 24 + fm.horizontalAdvance(label)
        p.end()


class CoreBars(QWidget):
    """Çekirdek başına kullanım çubukları."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.values: list[float] = []
        self.setMinimumHeight(120)

    def set_values(self, values: list[float]) -> None:
        self.values = list(values)
        if self.isVisible():
            self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        if not self.values:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self.values)
        cols = min(n, 16)
        rows = (n + cols - 1) // cols
        cell_w = self.width() / cols
        cell_h = (self.height() - 4) / rows
        small = QFont(self.font())
        small.setPointSizeF(7.5)
        p.setFont(small)
        for i, v in enumerate(self.values):
            r, c = divmod(i, cols)
            x = c * cell_w + 4
            y = r * cell_h + 2
            bw, bh = cell_w - 8, cell_h - 18
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.CARD2))
            p.drawRoundedRect(QRectF(x, y, bw, bh), 5, 5)
            fh = bh * max(0.0, min(v, 100.0)) / 100
            g = QLinearGradient(0, y + bh - fh, 0, y + bh)
            g.setColorAt(0, QColor(theme.BLUE))
            g.setColorAt(1, QColor(theme.PURPLE))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(x, y + bh - fh, bw, fh), 5, 5)
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(x - 4, y + bh + 1, bw + 8, 16), Qt.AlignHCenter, f"{i}: %{v:.0f}")
        p.end()


class Worker(QThread):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[threading.Event, Callable[[str], None]], Any], parent=None):
        super().__init__(parent)
        self._fn = fn
        self.cancel_event = threading.Event()

    def run(self) -> None:
        try:
            result = self._fn(self.cancel_event, self.progress.emit)
        except FileNotFoundError as e:
            self.failed.emit(str(e))
        except PermissionError as e:
            self.failed.emit(f"Erişim reddedildi: {e}")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.failed.emit(f"Beklenmeyen hata: {e}")
        else:
            self.succeeded.emit(result)

    def cancel(self) -> None:
        self.cancel_event.set()
