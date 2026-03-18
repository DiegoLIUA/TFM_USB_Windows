"""
Normaliza y correlaciona los eventos USB en sesiones coherentes.
Unifica formatos de fecha, limpia IDs y agrupa eventos por dispositivo.
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
]


def normalize_timestamp(raw: Optional[str]) -> Optional[str]:
    """Convierte distintos formatos de fecha a ISO 8601 (YYYY-MM-DD HH:MM:SS)."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    logger.debug("Formato de fecha no reconocido: %s", raw)
    return raw


def normalize_device(raw_device: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza un registro de dispositivo crudo al esquema canónico."""
    return {
        "vendor_id":    (raw_device.get("vendor_id") or "").upper().strip(),
        "product_id":   (raw_device.get("product_id") or "").upper().strip(),
        "serial":       (raw_device.get("serial") or "UNKNOWN").strip(),
        "friendly_name": (raw_device.get("friendly_name") or "Dispositivo USB").strip(),
        "first_seen":   normalize_timestamp(raw_device.get("first_seen")),
        "last_seen":    normalize_timestamp(raw_device.get("last_seen")),
    }


def deduplicate_devices(devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Elimina duplicados por número de serie, conservando la entrada más reciente."""
    seen: Dict[str, Dict[str, Any]] = {}
    for dev in devices:
        serial = dev.get("serial", "UNKNOWN")
        if serial not in seen:
            seen[serial] = dev
        else:
            existing_last = seen[serial].get("last_seen") or ""
            new_last = dev.get("last_seen") or ""
            if new_last > existing_last:
                seen[serial] = dev
    return list(seen.values())


def normalize_devices(raw_devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pipeline completo: normaliza y deduplica una lista de dispositivos crudos."""
    normalized = [normalize_device(d) for d in raw_devices]
    return deduplicate_devices(normalized)
