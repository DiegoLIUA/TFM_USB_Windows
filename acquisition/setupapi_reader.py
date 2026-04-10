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

# Patron: Device Install (Hardware ID = USB\VID_xxxx&PID_xxxx)
_RE_DEVICE = re.compile(
    r"Device Install.*?Hardware ID\s*=\s*(USB\\[^\]]+)", re.IGNORECASE
)
_RE_TIMESTAMP = re.compile(r">>>.*?(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})")
_RE_VID_PID = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", re.IGNORECASE)
_RE_SERIAL = re.compile(
    r"USB\\VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}\\(.+)", re.IGNORECASE
)


def _extract_vid_pid(hardware_id: str) -> Dict[str, str]:
    """Extrae VID y PID de un hardware_id como USB\\VID_xxxx&PID_xxxx\\serial."""
    match = _RE_VID_PID.search(hardware_id)
    if match:
        return {
            "vendor_id": match.group(1).upper(),
            "product_id": match.group(2).upper(),
        }
    return {"vendor_id": "", "product_id": ""}


def _extract_serial(hardware_id: str) -> str:
    """Extrae el serial del hardware_id."""
    match = _RE_SERIAL.search(hardware_id)
    if match:
        return match.group(1).split("&")[0].strip()
    return ""


def _parse_log(log_path: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    try:
        text = log_path.read_text(encoding="utf-16", errors="replace")
    except Exception as exc:
        logger.warning("No se pudo leer setupapi.dev.log: %s", exc)
        return entries

    current_ts = None
    for line in text.splitlines():
        ts_match = _RE_TIMESTAMP.search(line)
        if ts_match:
            current_ts = ts_match.group(1)

        dev_match = _RE_DEVICE.search(line)
        if dev_match:
            hw_id = dev_match.group(1)
            vid_pid = _extract_vid_pid(hw_id)
            serial = _extract_serial(hw_id)
            entries.append({
                "hardware_id": hw_id,
                "timestamp": current_ts,
                "source": "setupapi",
                "vendor_id": vid_pid["vendor_id"],
                "product_id": vid_pid["product_id"],
                "serial": serial,
            })

    logger.info("Entradas setupapi parseadas: %d", len(entries))
    return entries


def read_setupapi_devices() -> List[Dict[str, Any]]:
    """Lee y parsea el log de setupapi; devuelve lista vacia si no es accesible."""
    if not SETUPAPI_LOG.exists():
        logger.info("setupapi.dev.log no encontrado.")
        return []
    return _parse_log(SETUPAPI_LOG)
