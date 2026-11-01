"""Sıcaklık okuma. Yalnızca gerçek sensör verisi döndürülür; okunamazsa nedeni açıkça bildirilir."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TempReading:
    supported: bool
    source: str = ""
    sensors: list[tuple[str, float]] = field(default_factory=list)  # (etiket, °C)
    reason: str = ""

    @property
    def max_c(self) -> Optional[float]:
        return max((t for _, t in self.sensors), default=None)


NOT_SUPPORTED_WINDOWS = (
    "Bu bilgisayarda işlemci sıcaklığı standart Windows arabirimleriyle okunamıyor. "
    "Windows, CPU sıcaklığını yönetici izni olmadan sunmaz ve birçok anakart ACPI termal bölgesi "
    "yayımlamaz. Sentinel PC sahte değer göstermez; üretici aracı (ör. anakart/CPU yazılımı) gerekebilir."
)


def read_temperatures() -> TempReading:
    import psutil

    if hasattr(psutil, "sensors_temperatures"):
        try:
            data = psutil.sensors_temperatures()
        except (OSError, RuntimeError, NotImplementedError):
            data = {}
        sensors = []
        for chip, entries in (data or {}).items():
            for e in entries:
                if e.current is not None and -40 < e.current < 150:
                    sensors.append((f"{chip} {e.label}".strip(), float(e.current)))
        if sensors:
            return TempReading(True, "psutil", sensors)

    if os.name == "nt":
        return _windows_acpi()
    return TempReading(False, reason="Bu sistemde sıcaklık sensörü bulunamadı.")


def _windows_acpi() -> TempReading:
    """MSAcpi_ThermalZoneTemperature (root/wmi). Çoğu sistemde yönetici izni ister; izin istenmez."""
    from .sysinfo import _powershell_json

    data = _powershell_json(
        "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop "
        "| Select-Object InstanceName,CurrentTemperature", timeout=8)
    sensors = []
    for d in data or []:
        raw = d.get("CurrentTemperature")
        if isinstance(raw, (int, float)) and raw > 0:
            c = raw / 10.0 - 273.15  # onda bir Kelvin
            if -40 < c < 150:
                name = str(d.get("InstanceName") or "Termal bölge").split("\\")[-1]
                sensors.append((f"ACPI {name}", round(c, 1)))
    if sensors:
        return TempReading(True, "ACPI termal bölge (anakart sensörü; CPU çekirdek sıcaklığı olmayabilir)", sensors)
    return TempReading(False, reason=NOT_SUPPORTED_WINDOWS)
