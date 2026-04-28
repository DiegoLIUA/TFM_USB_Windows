"""
Parsea setupapi.dev.log para extraer registros de instalacion de dispositivos USB.
Este log contiene entradas con timestamps de primera conexion de dispositivos.
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

SETUPAPI_LOG = Path(r"C:\Windows\INF\setupapi.dev.log")

# Patron de sección: >>> [Device Install ... - USB\VID_xxxx&PID_xxxx\serial]
_RE_SECTION = re.compile(
    r"Device Install.*?USB\\VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})\\([^\]]+)",
    re.IGNORECASE,
)
# Patron de timestamp: >>> Section start 2026/04/28 12:43:48.946
_RE_TIMESTAMP = re.compile(r"Section start\s+(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})")


def _parse_log(log_path: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    text = None
    for encoding in ("utf-8", "utf-16", "cp1252"):
        try:
            text = log_path.read_text(encoding=encoding, errors="strict")
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if text is None:
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.warning("No se pudo leer setupapi.dev.log: %s", exc)
            return entries

    pending_device = None
    for line in text.splitlines():
        section_match = _RE_SECTION.search(line)
        if section_match:
            pending_device = {
                "vendor_id": section_match.group(1).upper(),
                "product_id": section_match.group(2).upper(),
                "serial": section_match.group(3).split("&")[0].strip(),
                "hardware_id": line.strip(),
            }
            continue

        if pending_device:
            ts_match = _RE_TIMESTAMP.search(line)
            if ts_match:
                entries.append({
                    "hardware_id": pending_device["hardware_id"],
                    "timestamp": ts_match.group(1),
                    "source": "setupapi",
                    "vendor_id": pending_device["vendor_id"],
                    "product_id": pending_device["product_id"],
                    "serial": pending_device["serial"],
                })
                pending_device = None

    logger.info("Entradas setupapi parseadas: %d", len(entries))
    return entries


def read_setupapi_devices() -> List[Dict[str, Any]]:
    """Lee y parsea el log de setupapi; devuelve lista vacia si no es accesible."""
    if not SETUPAPI_LOG.exists():
        logger.info("setupapi.dev.log no encontrado.")
        return []
    return _parse_log(SETUPAPI_LOG)
