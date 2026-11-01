"""Sistem bilgileri. Windows'ta kayıt defteri (yönetici izni gerektirmez), gerekirse CIM sorguları.

Bir bilgi okunamazsa "Bilinmiyor"/açık bir neden döndürülür; tahmin yapılmaz.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from typing import Optional

UNKNOWN = "Bilinmiyor"


def _reg(path: str, name: str) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
            value, _ = winreg.QueryValueEx(k, name)
            return str(value).strip() if value is not None else None
    except OSError:
        return None


def _read(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            v = fh.read().strip()
            return v or None
    except OSError:
        return None


def _powershell_json(command: str, timeout: float = 12.0) -> Optional[list]:
    """CIM sorgusunu PowerShell ile çalıştırır (pencere açmadan, yönetici izni olmadan)."""
    if os.name != "nt":
        return None
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
             f"[Console]::OutputEncoding=[Text.Encoding]::UTF8; {command} | ConvertTo-Json -Depth 3 -Compress"],
            capture_output=True, timeout=timeout, creationflags=flags,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        data = json.loads(out.stdout.decode("utf-8", errors="replace"))
        return data if isinstance(data, list) else [data]
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def windows_version() -> str:
    if os.name != "nt":
        return f"{platform.system()} {platform.release()} ({platform.version()})"
    base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    product = _reg(base, "ProductName") or "Windows"
    build = _reg(base, "CurrentBuildNumber") or _reg(base, "CurrentBuild") or ""
    ubr = _reg(base, "UBR")
    display = _reg(base, "DisplayVersion") or _reg(base, "ReleaseId") or ""
    try:
        if int(build) >= 22000:
            # Windows 11 kayıt defterinde hâlâ "Windows 10" yazabilir
            product = product.replace("Windows 10", "Windows 11")
    except ValueError:
        pass
    full_build = f"{build}.{ubr}" if build and ubr else build
    return f"{product} {display} (Derleme {full_build})".replace("  ", " ").strip()


def cpu_model() -> str:
    if os.name == "nt":
        v = _reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
        if v:
            return " ".join(v.split())
    else:
        txt = _read("/proc/cpuinfo")
        if txt:
            for line in txt.splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    return platform.processor() or UNKNOWN


def board_and_bios() -> dict[str, str]:
    info = {"board_maker": None, "board_model": None, "system_maker": None, "system_model": None,
            "bios_vendor": None, "bios_version": None, "bios_date": None}
    if os.name == "nt":
        k = r"HARDWARE\DESCRIPTION\System\BIOS"
        info.update(
            board_maker=_reg(k, "BaseBoardManufacturer"), board_model=_reg(k, "BaseBoardProduct"),
            system_maker=_reg(k, "SystemManufacturer"), system_model=_reg(k, "SystemProductName"),
            bios_vendor=_reg(k, "BIOSVendor"), bios_version=_reg(k, "BIOSVersion"),
            bios_date=_reg(k, "BIOSReleaseDate"),
        )
        if not info["board_model"] or not info["bios_version"]:
            data = _powershell_json(
                "$b=Get-CimInstance Win32_BaseBoard; $s=Get-CimInstance Win32_BIOS; "
                "[pscustomobject]@{bm=$b.Manufacturer;bp=$b.Product;bv=$s.Manufacturer;"
                "bver=$s.SMBIOSBIOSVersion;bd=$s.ReleaseDate}")
            if data:
                d = data[0]
                info["board_maker"] = info["board_maker"] or d.get("bm")
                info["board_model"] = info["board_model"] or d.get("bp")
                info["bios_vendor"] = info["bios_vendor"] or d.get("bv")
                info["bios_version"] = info["bios_version"] or d.get("bver")
    else:
        base = "/sys/class/dmi/id/"
        info.update(
            board_maker=_read(base + "board_vendor"), board_model=_read(base + "board_name"),
            system_maker=_read(base + "sys_vendor"), system_model=_read(base + "product_name"),
            bios_vendor=_read(base + "bios_vendor"), bios_version=_read(base + "bios_version"),
            bios_date=_read(base + "bios_date"),
        )
    return {k: (v if v else UNKNOWN) for k, v in info.items()}


def gpus() -> list[dict[str, str]]:
    """Ekran kartları: ad, sürücü sürümü, bellek (biliniyorsa)."""
    result: list[dict[str, str]] = []
    if os.name == "nt":
        data = _powershell_json(
            "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM,"
            "VideoProcessor,CurrentHorizontalResolution,CurrentVerticalResolution")
        for d in data or []:
            ram = d.get("AdapterRAM")
            # AdapterRAM 32 bittir; 4 GB üstünü doğru göstermez — bu durumda açıkça belirtilir.
            if isinstance(ram, (int, float)) and ram > 0:
                mem = f"{ram / 1024 ** 3:.1f} GB".replace(".", ",")
                if ram >= 4 * 1024 ** 3 - 1024 ** 2:
                    mem = "≥ 4 GB (Windows bu alanı 4 GB ile sınırlar)"
            else:
                mem = UNKNOWN
            w, h = d.get("CurrentHorizontalResolution"), d.get("CurrentVerticalResolution")
            result.append({
                "name": d.get("Name") or UNKNOWN,
                "driver": d.get("DriverVersion") or UNKNOWN,
                "memory": mem,
                "resolution": f"{w}×{h}" if w and h else UNKNOWN,
            })
        if not result:
            k = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000"
            name = _reg(k, "DriverDesc")
            if name:
                result.append({"name": name, "driver": _reg(k, "DriverVersion") or UNKNOWN,
                               "memory": UNKNOWN, "resolution": UNKNOWN})
    else:
        drm = "/sys/class/drm"
        try:
            for card in sorted(os.listdir(drm)):
                if card.startswith("card") and "-" not in card:
                    vendor = _read(f"{drm}/{card}/device/vendor")
                    device = _read(f"{drm}/{card}/device/device")
                    if vendor:
                        result.append({"name": f"PCI {vendor}:{device}", "driver": _read(f"{drm}/{card}/device/driver/module/version") or UNKNOWN,
                                       "memory": UNKNOWN, "resolution": UNKNOWN})
        except OSError:
            pass
    return result


def basic_info() -> dict[str, str]:
    """Hızlı (milisaniyeler) okunan bilgiler."""
    import psutil
    from datetime import datetime
    arch_map = {"AMD64": "x64 (64 bit)", "x86_64": "x64 (64 bit)", "ARM64": "ARM64", "aarch64": "ARM64",
                "x86": "x86 (32 bit)", "i686": "x86 (32 bit)"}
    machine = platform.machine()
    return {
        "Bilgisayar adı": platform.node() or UNKNOWN,
        "İşletim sistemi": windows_version(),
        "Sistem mimarisi": arch_map.get(machine, machine or UNKNOWN),
        "İşlemci": cpu_model(),
        "Fiziksel çekirdek": str(psutil.cpu_count(logical=False) or UNKNOWN),
        "Mantıksal işlemci (thread)": str(psutil.cpu_count(logical=True) or UNKNOWN),
        "Toplam RAM": f"{psutil.virtual_memory().total / 1024 ** 3:.1f} GB".replace(".", ","),
        "Son açılış": datetime.fromtimestamp(psutil.boot_time()).strftime("%d.%m.%Y %H:%M"),
        "Python / psutil": f"{platform.python_version()} / {psutil.__version__}",
    }


def full_info() -> dict[str, dict[str, str]]:
    """Tüm bilgiler (Windows'ta CIM sorgusu birkaç saniye sürebilir; arka planda çağırın)."""
    bb = board_and_bios()
    sections = {
        "Genel": basic_info(),
        "Anakart": {
            "Üretici": bb["board_maker"], "Model": bb["board_model"],
            "Sistem üreticisi": bb["system_maker"], "Sistem modeli": bb["system_model"],
        },
        "BIOS": {"Üretici": bb["bios_vendor"], "Sürüm": bb["bios_version"], "Tarih": bb["bios_date"]},
    }
    cards = gpus()
    if cards:
        for i, g in enumerate(cards, 1):
            sections[f"Ekran kartı {i}"] = {
                "Ad": g["name"], "Sürücü sürümü": g["driver"], "Bellek": g["memory"], "Çözünürlük": g["resolution"],
            }
    else:
        sections["Ekran kartı"] = {"Ad": UNKNOWN}
    return sections


def is_admin() -> bool:
    if os.name == "nt":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:  # noqa: BLE001
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def python_bits() -> str:
    return "64 bit" if sys.maxsize > 2 ** 32 else "32 bit"
