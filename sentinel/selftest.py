"""Kendi kendini doğrulama: SentinelPC.exe --self-test=rapor.json (çıkış kodu 0 = başarılı).

Geçici veri klasörü kullanır; kullanıcı verisine ve çalışan işlemlere dokunmaz.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import traceback


def run_self_test(app, out_path: str = "") -> int:
    from PySide6.QtCore import QCoreApplication

    tmp = tempfile.mkdtemp(prefix="sentinel_selftest_")
    os.environ["SENTINEL_DATA_DIR"] = tmp
    results: list[dict] = []
    win = None
    store = None

    def check(name, fn):
        try:
            detail = fn()
            results.append({"test": name, "ok": True, **({"detail": detail} if detail else {})})
        except Exception as e:  # noqa: BLE001
            results.append({"test": name, "ok": False, "error": f"{type(e).__name__}: {e}",
                            "trace": traceback.format_exc()})

    def pump(ms):
        end = time.time() + ms / 1000
        while time.time() < end:
            QCoreApplication.processEvents()
            time.sleep(0.01)

    def wait_for(cond, timeout=20.0):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            pump(50)
        return False

    try:
        from .core import history as H
        from .core import metrics as M
        from .ui.main_window import NAV, MainWindow

        store = H.HistoryStore(os.path.join(tmp, "h.db"))
        win = MainWindow(store, interval_ms=250)
        win.aggregator.interval = 1.0
        win.show()
        check("pencere açıldı", lambda: _assert(win.isVisible(), "görünür değil"))

        def live_data():
            _assert(wait_for(lambda: len(win.monitor.history["cpu"]) >= 4, 10), "ölçüm gelmedi")
            s = win.last
            _assert(s.mem_total > 0 and 0 < s.mem_percent < 100, "RAM verisi")
            _assert(0 <= s.cpu_percent <= 100 and len(s.per_cpu) >= 1, "CPU verisi")
            _assert(s.uptime > 0 and s.process_count > 0, "çalışma süresi/işlem")
            return f"CPU %{s.cpu_percent:.0f}, RAM %{s.mem_percent:.0f}, {len(s.per_cpu)} çekirdek, {s.process_count} işlem"
        check("canlı donanım verisi", live_data)

        def pages():
            for key, _ in NAV:
                win.navigate(key)
                pump(300)
                _assert(win.stack.currentWidget() is win.pages[key], key)
        check("tüm sayfalar açılıyor", pages)

        def processes():
            win.navigate("processes")
            p = win.pages["processes"]
            _assert(wait_for(lambda: p.table.rowCount() > 0, 15), "işlem listesi boş")
            pids = {p.table.item(r, 1).data(256) for r in range(p.table.rowCount())}
            _assert(os.getpid() in pids, "kendi işlemi listede yok")
            p.filter.setText(str(os.getpid()))
            _assert(p.table.rowCount() == 1, "filtre")
            p.filter.clear()
            return f"{len(pids)} işlem"
        check("işlem yöneticisi", processes)

        def protected():
            try:
                M.terminate_process(os.getpid())
            except M.ProcessActionError:
                return "kendi işlemini sonlandırma engellendi"
            raise AssertionError("koruma çalışmadı")
        check("işlem koruması", protected)

        def sysinfo():
            win.navigate("sysinfo")
            page = win.pages["sysinfo"]
            _assert(wait_for(lambda: page.info is not None, 40), "sistem bilgisi yüklenmedi")
            g = page.info["Genel"]
            _assert(g["İşletim sistemi"] and g["İşlemci"], "temel bilgi")
            return f"{g['İşletim sistemi']} | {g['İşlemci']} | GPU: " + ", ".join(
                v.get("Ad", "?") for k, v in page.info.items() if k.startswith("Ekran kartı"))
        check("sistem bilgisi", sysinfo)

        def temperature():
            _assert(wait_for(lambda: win.temp is not None, 30), "sıcaklık kontrolü tamamlanmadı")
            t = win.temp
            if t.supported:
                _assert(all(-40 < v < 150 for _, v in t.sensors), "geçersiz sıcaklık")
                return f"desteklenir: {t.max_c:.1f} °C ({t.source})"
            _assert(t.reason and not t.sensors, "desteklenmeyen sensör açıkça belirtilmeli")
            return "desteklenmiyor (açıkça bildirildi)"
        check("sıcaklık (sahte veri yok)", temperature)

        def disk():
            win.navigate("disk")
            d = win.pages["disk"]
            _assert(d.parts.rowCount() >= 1, "disk bölümü yok")
            folder = os.path.join(tmp, "klasor")
            os.makedirs(os.path.join(folder, "alt"))
            with open(os.path.join(folder, "alt", "a.bin"), "wb") as fh:
                fh.write(b"0" * 4096)
            d.path.setText(folder)
            d.scan()
            _assert(wait_for(lambda: d.worker is None, 15), "tarama bitmedi")
            _assert(d.folders.rowCount() == 1, "klasör analizi sonucu")
            return f"{d.parts.rowCount()} bölüm"
        check("disk ve klasör analizi", disk)

        def network():
            win.navigate("network")
            pump(300)
            _assert(win.pages["network"].table.rowCount() >= 1, "adaptör yok")
        check("ağ adaptörleri", network)

        def reports():
            _assert(wait_for(lambda: store.count() >= 1, 10), "geçmiş kaydı oluşmadı")
            win.navigate("reports")
            r = win.pages["reports"]
            r.refresh()
            csv_path = os.path.join(tmp, "g.csv")
            n = H.export_csv(r._samples(), csv_path)
            _assert(n >= 1 and os.path.getsize(csv_path) > 0, "CSV")
            text = r.report_text()
            _assert("SİSTEM RAPORU" in text and "Anlık durum" in text, "rapor")
            return f"{store.count()} kayıt, CSV {n} satır"
        check("raporlama ve CSV", reports)
    except Exception as e:  # noqa: BLE001
        results.append({"test": "başlatma", "ok": False, "error": str(e), "trace": traceback.format_exc()})
    finally:
        if win is not None:
            win.shutdown()
            win.hide()
            win.deleteLater()
        QCoreApplication.processEvents()
        if store is not None:
            store.close()
        shutil.rmtree(tmp, ignore_errors=True)

    ok = all(r["ok"] for r in results)
    report = json.dumps({"ok": ok, "passed": sum(r["ok"] for r in results), "total": len(results),
                         "results": results}, ensure_ascii=False, indent=2)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(report)
    else:
        try:
            print(report)
        except Exception:  # noqa: BLE001
            pass
    return 0 if ok else 1


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)
