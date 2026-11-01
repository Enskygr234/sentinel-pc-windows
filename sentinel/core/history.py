"""CPU/RAM geçmişini SQLite'ta saklar, CSV ve sistem raporu üretir."""
from __future__ import annotations

import csv
import os
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

RETENTION_DAYS = 7


def default_data_dir() -> str:
    env = os.environ.get("SENTINEL_DATA_DIR")
    if env:
        return env
    if getattr(sys, "frozen", False) and os.path.exists(os.path.join(os.path.dirname(sys.executable), "portable.txt")):
        return os.path.join(os.path.dirname(sys.executable), "data")
    if os.name == "nt":
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "SentinelPC")
    return os.path.join(os.path.expanduser("~"), ".local", "share", "SentinelPC")


@dataclass
class Sample:
    ts: float
    cpu: float
    ram: float
    down: float
    up: float
    read: float
    write: float


class Aggregator:
    """1 saniyelik ölçümleri toplayıp belirli aralıkta ortalama tek kayıt üretir (disk yazımını azaltır)."""

    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self._buf: list[tuple[float, ...]] = []
        self._start: Optional[float] = None

    def add(self, ts: float, values: tuple[float, ...]) -> Optional[Sample]:
        if self._start is None:
            self._start = ts
        self._buf.append(values)
        if ts - self._start >= self.interval:
            n = len(self._buf)
            avg = [sum(v[i] for v in self._buf) / n for i in range(len(values))]
            self._buf.clear()
            self._start = None
            return Sample(ts, *avg)
        return None


class HistoryStore:
    def __init__(self, path: Optional[str] = None):
        if path is None:
            folder = default_data_dir()
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "sentinel_history.db")
        self.path = path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS samples (ts REAL PRIMARY KEY, cpu REAL, ram REAL, "
            "down REAL, up REAL, read REAL, write REAL)")
        self.conn.commit()
        self._last_purge = 0.0

    def add(self, s: Sample) -> None:
        with self._lock:
            self.conn.execute("INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?)",
                              (s.ts, s.cpu, s.ram, s.down, s.up, s.read, s.write))
            self.conn.commit()
        if s.ts - self._last_purge > 3600:
            self.purge(s.ts)

    def purge(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        with self._lock:
            cur = self.conn.execute("DELETE FROM samples WHERE ts < ?", (now - RETENTION_DAYS * 86400,))
            self.conn.commit()
        self._last_purge = now
        return cur.rowcount

    def query(self, since: float, until: Optional[float] = None) -> list[Sample]:
        until = time.time() + 1 if until is None else until
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts, cpu, ram, down, up, read, write FROM samples WHERE ts BETWEEN ? AND ? ORDER BY ts",
                (since, until)).fetchall()
        return [Sample(*r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return int(self.conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0])

    def clear(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM samples")
            self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()


def downsample(samples: list[Sample], max_points: int = 300) -> list[Sample]:
    """Grafik için eşit aralıklı ortalama alarak nokta sayısını azaltır."""
    if len(samples) <= max_points:
        return samples
    step = len(samples) / max_points
    out = []
    for i in range(max_points):
        chunk = samples[int(i * step):int((i + 1) * step)] or [samples[int(i * step)]]
        n = len(chunk)
        out.append(Sample(chunk[-1].ts, *(sum(getattr(c, f) for c in chunk) / n
                                         for f in ("cpu", "ram", "down", "up", "read", "write"))))
    return out


def summarize(samples: Iterable[Sample]) -> dict[str, float]:
    s = list(samples)
    if not s:
        return {"count": 0}
    return {
        "count": len(s),
        "cpu_avg": sum(x.cpu for x in s) / len(s), "cpu_max": max(x.cpu for x in s),
        "ram_avg": sum(x.ram for x in s) / len(s), "ram_max": max(x.ram for x in s),
        "start": s[0].ts, "end": s[-1].ts,
    }


def export_csv(samples: Iterable[Sample], path: str) -> int:
    """Excel'de Türkçe doğru açılması için UTF-8 BOM ve ';' ayırıcı kullanılır."""
    n = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Zaman", "CPU %", "RAM %", "İndirme (B/s)", "Yükleme (B/s)", "Disk okuma (B/s)", "Disk yazma (B/s)"])
        for s in samples:
            w.writerow([datetime.fromtimestamp(s.ts).strftime("%Y-%m-%d %H:%M:%S"),
                        f"{s.cpu:.1f}".replace(".", ","), f"{s.ram:.1f}".replace(".", ","),
                        int(s.down), int(s.up), int(s.read), int(s.write)])
            n += 1
    return n


def build_report(info: dict[str, dict[str, str]], extra: dict[str, dict[str, str]], summary: dict) -> str:
    lines = ["SENTINEL PC – SİSTEM RAPORU", f"Oluşturulma: {datetime.now():%d.%m.%Y %H:%M:%S}", "=" * 60, ""]
    for section, values in list(info.items()) + list(extra.items()):
        lines.append(f"[{section}]")
        width = max((len(k) for k in values), default=0)
        for k, v in values.items():
            lines.append(f"  {k.ljust(width)} : {v}")
        lines.append("")
    if summary.get("count"):
        lines.append("[Kayıtlı geçmiş özeti]")
        lines.append(f"  Aralık      : {datetime.fromtimestamp(summary['start']):%d.%m.%Y %H:%M} – "
                     f"{datetime.fromtimestamp(summary['end']):%d.%m.%Y %H:%M}")
        lines.append(f"  Ölçüm sayısı: {summary['count']}")
        lines.append(f"  CPU ort/maks: %{summary['cpu_avg']:.1f} / %{summary['cpu_max']:.1f}")
        lines.append(f"  RAM ort/maks: %{summary['ram_avg']:.1f} / %{summary['ram_max']:.1f}")
    return "\n".join(lines)
