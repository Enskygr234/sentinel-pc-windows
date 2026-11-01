"""psutil ile gerçek donanım ölçümleri. Sahte veya tahmini değer üretilmez."""
from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import psutil


def human_bytes(n: float, per_second: bool = False) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(n)
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            text = f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}".replace(".", ",")
            return text + ("/s" if per_second else "")
        size /= 1024
    return f"{size:.1f} PB"


def format_uptime(seconds: float) -> str:
    s = int(max(0, seconds))
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, s = divmod(s, 60)
    parts = []
    if days:
        parts.append(f"{days} gün")
    parts.append(f"{hours:02d}:{minutes:02d}:{s:02d}")
    return " ".join(parts)


class RateTracker:
    """Artan sayaçlardan (bayt) saniye başına hız hesaplar."""

    def __init__(self):
        self._last: Optional[tuple[float, dict[str, float]]] = None

    def update(self, counters: dict[str, float], now: Optional[float] = None) -> dict[str, float]:
        now = time.monotonic() if now is None else now
        rates = {k: 0.0 for k in counters}
        if self._last is not None:
            t0, prev = self._last
            dt = now - t0
            if dt > 0:
                for k, v in counters.items():
                    delta = v - prev.get(k, v)
                    # Sayaç sıfırlanırsa (adaptör yeniden başladı) negatif hız gösterme
                    rates[k] = max(0.0, delta / dt)
        self._last = (now, dict(counters))
        return rates


@dataclass
class Snapshot:
    ts: float
    cpu_percent: float
    per_cpu: list[float]
    cpu_freq_mhz: Optional[float]
    cpu_freq_max_mhz: Optional[float]
    mem_total: int
    mem_used: int
    mem_available: int
    mem_percent: float
    swap_total: int
    swap_used: int
    swap_percent: float
    net_down: float
    net_up: float
    net_total_recv: int
    net_total_sent: int
    disk_read: float
    disk_write: float
    disk_percent: float  # sistem sürücüsü doluluk
    uptime: float
    process_count: int


class Monitor:
    """Hafif örnekleyici: her çağrıda tek bir anlık görüntü üretir ve kısa geçmiş tutar."""

    def __init__(self, history: int = 120):
        self.net_rate = RateTracker()
        self.disk_rate = RateTracker()
        self.history: dict[str, deque] = {
            k: deque(maxlen=history) for k in ("cpu", "ram", "down", "up", "read", "write")
        }
        self.per_cpu_history: list[deque] = []
        self._history_len = history
        self.boot_time = psutil.boot_time()
        self.system_drive = _system_drive()
        self._disk_percent = 0.0
        self._disk_checked = 0.0
        psutil.cpu_percent(None)
        psutil.cpu_percent(None, percpu=True)

    def sample(self) -> Snapshot:
        now = time.time()
        cpu = psutil.cpu_percent(None)
        per = psutil.cpu_percent(None, percpu=True)
        try:
            freq = psutil.cpu_freq()
        except (NotImplementedError, OSError, FileNotFoundError):
            freq = None
        vm = psutil.virtual_memory()
        try:
            sw = psutil.swap_memory()
            swap = (sw.total, sw.used, sw.percent)
        except (RuntimeError, OSError):
            swap = (0, 0, 0.0)
        net = psutil.net_io_counters()
        net_r = self.net_rate.update({"down": net.bytes_recv, "up": net.bytes_sent}) if net else {"down": 0, "up": 0}
        try:
            dio = psutil.disk_io_counters()
        except (RuntimeError, OSError):
            dio = None
        disk_r = self.disk_rate.update({"read": dio.read_bytes, "write": dio.write_bytes}) if dio else {"read": 0.0, "write": 0.0}
        if now - self._disk_checked > 10:
            try:
                self._disk_percent = psutil.disk_usage(self.system_drive).percent
            except OSError:
                self._disk_percent = 0.0
            self._disk_checked = now
        try:
            pcount = len(psutil.pids())
        except OSError:
            pcount = 0

        snap = Snapshot(
            ts=now, cpu_percent=cpu, per_cpu=per,
            cpu_freq_mhz=freq.current if freq and freq.current else None,
            cpu_freq_max_mhz=freq.max if freq and freq.max else None,
            mem_total=vm.total, mem_used=vm.total - vm.available, mem_available=vm.available,
            mem_percent=vm.percent, swap_total=swap[0], swap_used=swap[1], swap_percent=swap[2],
            net_down=net_r["down"], net_up=net_r["up"],
            net_total_recv=net.bytes_recv if net else 0, net_total_sent=net.bytes_sent if net else 0,
            disk_read=disk_r["read"], disk_write=disk_r["write"], disk_percent=self._disk_percent,
            uptime=now - self.boot_time, process_count=pcount,
        )
        h = self.history
        h["cpu"].append(snap.cpu_percent)
        h["ram"].append(snap.mem_percent)
        h["down"].append(snap.net_down)
        h["up"].append(snap.net_up)
        h["read"].append(snap.disk_read)
        h["write"].append(snap.disk_write)
        if len(self.per_cpu_history) != len(per):
            self.per_cpu_history = [deque(maxlen=self._history_len) for _ in per]
        for dq, v in zip(self.per_cpu_history, per):
            dq.append(v)
        return snap


def _system_drive() -> str:
    if os.name == "nt":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


# ---------------- Statik bilgiler ----------------
@dataclass
class CpuStatic:
    physical_cores: Optional[int]
    logical_cores: int
    freq_min: Optional[float]
    freq_max: Optional[float]


def cpu_static() -> CpuStatic:
    try:
        f = psutil.cpu_freq()
    except (NotImplementedError, OSError, FileNotFoundError):
        f = None
    return CpuStatic(
        physical_cores=psutil.cpu_count(logical=False),
        logical_cores=psutil.cpu_count(logical=True) or 0,
        freq_min=f.min if f and f.min else None,
        freq_max=f.max if f and f.max else None,
    )


@dataclass
class PartitionInfo:
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float
    opts: str = ""


def partitions() -> list[PartitionInfo]:
    out: list[PartitionInfo] = []
    for p in psutil.disk_partitions(all=False):
        if os.name == "nt" and ("cdrom" in p.opts or not p.fstype):
            continue  # boş optik sürücüler okunamaz
        try:
            u = psutil.disk_usage(p.mountpoint)
        except (PermissionError, OSError):
            continue
        out.append(PartitionInfo(p.device, p.mountpoint, p.fstype, u.total, u.used, u.free, u.percent, p.opts))
    return out


@dataclass
class AdapterInfo:
    name: str
    is_up: bool
    speed_mbps: int
    mtu: int
    ipv4: list[str] = field(default_factory=list)
    ipv6: list[str] = field(default_factory=list)
    mac: str = ""
    bytes_recv: int = 0
    bytes_sent: int = 0


def adapters() -> list[AdapterInfo]:
    import socket
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    io = psutil.net_io_counters(pernic=True)
    link_family = getattr(psutil, "AF_LINK", None)
    out = []
    for name in sorted(set(stats) | set(addrs)):
        st = stats.get(name)
        info = AdapterInfo(name, bool(st and st.isup), st.speed if st else 0, st.mtu if st else 0)
        for a in addrs.get(name, []):
            if a.family == socket.AF_INET:
                info.ipv4.append(a.address)
            elif a.family == socket.AF_INET6:
                info.ipv6.append(a.address.split("%")[0])
            elif link_family is not None and a.family == link_family:
                info.mac = a.address
        if name in io:
            info.bytes_recv = io[name].bytes_recv
            info.bytes_sent = io[name].bytes_sent
        out.append(info)
    out.sort(key=lambda a: (not a.is_up, -(a.bytes_recv + a.bytes_sent)))
    return out


# ---------------- İşlemler ----------------
@dataclass
class ProcInfo:
    pid: int
    name: str
    user: str
    cpu: float
    memory: int
    status: str


_ATTRS = ["pid", "name", "username", "cpu_percent", "memory_info", "status"]

STATUS_TR = {
    "running": "Çalışıyor", "sleeping": "Uykuda", "disk-sleep": "Disk bekliyor", "stopped": "Durduruldu",
    "tracing-stop": "İzleniyor", "zombie": "Zombi", "dead": "Sonlandı", "wake-kill": "Sonlanıyor",
    "waking": "Uyanıyor", "idle": "Boşta", "locked": "Kilitli", "waiting": "Bekliyor", "parked": "Park edildi",
}


def list_processes() -> list[ProcInfo]:
    """Çalışan işlemler. CPU yüzdesi mantıksal çekirdek sayısına bölünür (Görev Yöneticisi gibi)."""
    ncpu = psutil.cpu_count() or 1
    out: list[ProcInfo] = []
    for p in psutil.process_iter(_ATTRS):
        try:
            info = p.info
            if info["pid"] == 0 and os.name == "nt":
                continue  # "System Idle Process" gerçek bir işlem değildir (boşta kalan CPU payı)
            mem = info.get("memory_info")
            out.append(ProcInfo(
                pid=info["pid"],
                name=info.get("name") or "?",
                user=(info.get("username") or "").split("\\")[-1],
                cpu=(info.get("cpu_percent") or 0.0) / ncpu,
                memory=mem.rss if mem else 0,
                status=STATUS_TR.get(info.get("status") or "", info.get("status") or ""),
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return out


CRITICAL_PROCESSES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe",
    "winlogon.exe", "services.exe", "lsass.exe", "lsaiso.exe", "memory compression",
    "secure system", "fontdrvhost.exe", "dwm.exe",
}


def is_protected(pid: int, name: str) -> bool:
    return pid in (0, 4, os.getpid()) or name.lower() in CRITICAL_PROCESSES


class ProcessActionError(Exception):
    pass


def terminate_process(pid: int, timeout: float = 3.0, force: bool = False) -> str:
    """İşlemi sonlandırır. Yalnızca kullanıcı onayı sonrası çağrılmalıdır."""
    try:
        p = psutil.Process(pid)
        name = p.name()
    except psutil.NoSuchProcess:
        return "İşlem zaten sonlanmış."
    except psutil.AccessDenied as e:
        raise ProcessActionError("Bu işleme erişim izni yok.") from e
    if is_protected(pid, name):
        raise ProcessActionError(f"{name} kritik bir sistem işlemidir; sonlandırılması engellendi.")
    try:
        p.kill() if force else p.terminate()
        p.wait(timeout=timeout)
        return f"{name} (PID {pid}) sonlandırıldı."
    except psutil.NoSuchProcess:
        return f"{name} (PID {pid}) sonlandırıldı."
    except psutil.TimeoutExpired as e:
        raise ProcessActionError(f"{name} yanıt vermedi; zorla sonlandırmayı deneyebilirsiniz.") from e
    except psutil.AccessDenied as e:
        raise ProcessActionError(
            f"{name} sonlandırılamadı: erişim reddedildi (başka kullanıcıya veya sisteme ait olabilir).") from e


# ---------------- Klasör boyutu ----------------
def folder_sizes(root: str, cancel=None, progress=None) -> tuple[int, list[tuple[str, int, bool]]]:
    """Klasörün toplam boyutu ve doğrudan alt öğelerinin boyutları (salt okunur)."""
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Klasör bulunamadı: {root}")
    results: dict[str, list] = {}
    total = 0
    count = 0
    try:
        top = list(os.scandir(root))
    except OSError as e:
        raise PermissionError(str(e)) from e
    for entry in top:
        if cancel is not None and cancel.is_set():
            break
        try:
            if entry.is_symlink():
                continue
            if entry.is_file(follow_symlinks=False):
                size = entry.stat(follow_symlinks=False).st_size
                results[entry.name] = [size, False]
                total += size
                continue
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        size = 0
        stack = [entry.path]
        while stack:
            if cancel is not None and cancel.is_set():
                break
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        try:
                            if e.is_symlink():
                                continue
                            if e.is_dir(follow_symlinks=False):
                                stack.append(e.path)
                            elif e.is_file(follow_symlinks=False):
                                size += e.stat(follow_symlinks=False).st_size
                                count += 1
                                if progress and count % 2000 == 0:
                                    progress(f"{count} dosya tarandı…")
                        except OSError:
                            continue
            except OSError:
                continue
        results[entry.name] = [size, True]
        total += size
    items = sorted(((n, v[0], v[1]) for n, v in results.items()), key=lambda x: x[1], reverse=True)
    return total, items
