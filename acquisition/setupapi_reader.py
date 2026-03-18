"""
Parsea setupapi.dev.log para extraer registros de instalación de dispositivos USB.
Este log contiene entradas con timestamps de primera conexión de dispositivos.
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

SETUPAPI_LOG = Path(r"C:\Windows\INF\setupapi.dev.log")

# Patrón: Device Install (Hardware ID = USB\VID_xxxx&PID_xxxx)
_RE_DEVICE = re.compile(
    r"Device Install.*?Hardware ID\s*=\s*(USB\\[^\]]+)", re.IGNORECASE
)
_RE_TIMESTAMP = re.compile(r">>>.*?(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})")


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
            entries.append({
                "hardware_id": dev_match.group(1),
                "timestamp":   current_ts,
                "source":      "setupapi",
            })

    return entries


def read_setupapi_devices() -> List[Dict[str, Any]]:
    """Lee y parsea el log de setupapi; devuelve lista vacía si no es accesible."""
    if not SETUPAPI_LOG.exists():
        logger.info("setupapi.dev.log no encontrado.")
        return []
    return _parse_log(SETUPAPI_LOG)
