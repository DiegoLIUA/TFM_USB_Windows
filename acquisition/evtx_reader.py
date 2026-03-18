"""
Lectura de Event Logs .evtx relacionados con USB.
IDs de eventos relevantes: 2003 (Microsoft-Windows-DriverFrameworks-UserMode),
20001/20003 (Plug and Play).
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

EVTX_USB_LOG = Path(
    r"C:\Windows\System32\winevt\Logs\Microsoft-Windows-DriverFrameworks-UserMode%4Operational.evtx"
)


def _parse_evtx_file(evtx_path: Path) -> List[Dict[str, Any]]:
    """Parsea un archivo .evtx y devuelve eventos USB relevantes."""
    try:
        from evtx import PyEvtxParser
    except ImportError:
        logger.warning("python-evtx no disponible. Saltando lectura de Event Logs.")
        return []

    events: List[Dict[str, Any]] = []
    try:
        parser = PyEvtxParser(str(evtx_path))
        for record in parser.records_json():
            events.append({
                "source":     "evtx",
                "event_type": "usb_event",
                "timestamp":  record.get("timestamp", ""),
                "raw":        record.get("data", "")[:500],
                "device_id":  None,
                "session_id": None,
            })
    except Exception as exc:
        logger.warning("Error parseando %s: %s", evtx_path, exc)

    return events


def read_usb_events() -> List[Dict[str, Any]]:
    """Lee eventos USB desde el log operacional de DriverFrameworks."""
    if not EVTX_USB_LOG.exists():
        logger.info("Archivo evtx no encontrado: %s", EVTX_USB_LOG)
        return []
    return _parse_evtx_file(EVTX_USB_LOG)
