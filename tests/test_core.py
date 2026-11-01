import os
import subprocess
import sys
import threading
import time

import psutil
import pytest

from sentinel.core import history as H
from sentinel.core import metrics as M
from sentinel.core import sysinfo as S
from sentinel.core import temperature as T


def test_human_bytes_and_uptime():
    assert M.human_bytes(512) == "512 B"
    assert M.human_bytes(1536, per_second=True) == "1,5 KB/s"
    assert M.human_bytes(3 * 1024 ** 3) == "3,0 GB"
    assert M.format_uptime(59) == "00:00:59"
    assert M.format_uptime(90061) == "1 gün 01:01:01"


def test_rate_tracker():
    r = M.RateTracker()
    assert r.update({"down": 1000}, now=0.0) == {"down": 0.0}
    assert r.update({"down": 3000}, now=2.0) == {"down": 1000.0}
    # Sayaç sıfırlanırsa negatif hız olmamalı
    assert r.update({"down": 10}, now=3.0) == {"down": 0.0}


def test_monitor_returns_real_values():
    m = M.Monitor(history=10)
    time.sleep(0.2)
    s1 = m.sample()
    time.sleep(0.3)
    s2 = m.sample()
    vm = psutil.virtual_memory()
    assert 0.0 <= s2.cpu_percent <= 100.0
    assert len(s2.per_cpu) == psutil.cpu_count()
    assert s2.mem_total == vm.total
    assert 0 < s2.mem_percent < 100
    assert s2.uptime > 0
    assert s2.process_count > 0
    assert s2.net_down >= 0 and s2.net_up >= 0
    assert len(m.history["cpu"]) == 2
    assert s1.ts < s2.ts


def test_cpu_static_and_partitions_and_adapters():
    c = M.cpu_static()
    assert c.logical_cores == psutil.cpu_count()
    parts = M.partitions()
    assert parts, "en az bir disk bölümü olmalı"
    for p in parts:
        assert p.total >= p.used >= 0 and 0 <= p.percent <= 100
    ad = M.adapters()
    assert any(a.name for a in ad)


def test_list_processes_contains_self():
    procs = M.list_processes()
    me = [p for p in procs if p.pid == os.getpid()]
    assert me and me[0].memory > 0


def test_protected_processes():
    assert M.is_protected(0, "x")
    assert M.is_protected(os.getpid(), "python")
    assert M.is_protected(1234, "LSASS.EXE")
    assert not M.is_protected(1234, "notepad.exe")
    with pytest.raises(M.ProcessActionError):
        M.terminate_process(os.getpid())


def test_terminate_child_process():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        msg = M.terminate_process(child.pid)
        assert "sonlandırıldı" in msg
        assert child.wait(timeout=5) is not None
    finally:
        if child.poll() is None:
            child.kill()
    assert M.terminate_process(child.pid) == "İşlem zaten sonlanmış."


def test_folder_sizes(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.bin").write_bytes(b"0" * 5000)
    (tmp_path / "y.bin").write_bytes(b"0" * 100)
    total, items = M.folder_sizes(str(tmp_path))
    assert total == 5100
    assert items[0] == ("a", 5000, True)
    ev = threading.Event()
    ev.set()
    M.folder_sizes(str(tmp_path), cancel=ev)  # iptal edilmiş tarama hata vermemeli
    with pytest.raises(FileNotFoundError):
        M.folder_sizes(str(tmp_path / "yok"))


def test_sysinfo_basic():
    info = S.basic_info()
    for key in ("İşletim sistemi", "İşlemci", "Sistem mimarisi", "Toplam RAM"):
        assert info[key]
    full = S.full_info()
    assert "Anakart" in full and "BIOS" in full
    assert any(k.startswith("Ekran kartı") for k in full)


def test_temperature_never_fakes():
    r = T.read_temperatures()
    if r.supported:
        assert r.sensors and all(-40 < t < 150 for _, t in r.sensors)
    else:
        assert r.reason and not r.sensors and r.max_c is None


def test_aggregator():
    a = H.Aggregator(interval=5)
    assert a.add(0, (10, 20, 0, 0, 0, 0)) is None
    assert a.add(3, (30, 40, 0, 0, 0, 0)) is None
    s = a.add(5, (50, 60, 3, 3, 3, 3))
    assert s is not None and s.cpu == pytest.approx(30) and s.ram == pytest.approx(40)
    assert a.add(6, (1, 1, 1, 1, 1, 1)) is None


def test_history_store_csv_report(tmp_path):
    store = H.HistoryStore(str(tmp_path / "h.db"))
    now = time.time()
    for i in range(10):
        store.add(H.Sample(now - 100 + i * 10, 10 + i, 50, 1, 2, 3, 4))
    old = H.Sample(now - 8 * 86400, 1, 1, 1, 1, 1, 1)
    store.add(old)
    assert store.count() == 11
    assert store.purge(now) == 1
    rows = store.query(now - 3600)
    assert len(rows) == 10
    summ = H.summarize(rows)
    assert summ["cpu_max"] == 19 and summ["ram_avg"] == 50
    assert len(H.downsample(rows, 5)) == 5
    path = tmp_path / "out.csv"
    assert H.export_csv(rows, str(path)) == 10
    content = path.read_text(encoding="utf-8-sig")
    assert content.splitlines()[0].startswith("Zaman;CPU %")
    rep = H.build_report({"Genel": {"A": "B"}}, {"Ek": {"C": "D"}}, summ)
    assert "SİSTEM RAPORU" in rep and "A : B" in rep and "CPU ort/maks" in rep
    store.clear()
    assert store.count() == 0
    store.close()
