"""
Lectura de Event Logs .evtx relacionados con USB.
Extrae eventos con IDs 20001 (dispositivo conectado) y 20003 (dispositivo desconectado)
del log de DriverFrameworks-UserMode, mas el log de Plug and Play.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

EVTX_DRIVER_LOG = Path(
    r"C:\Windows\System32\winevt\Logs"
    r"\Microsoft-Windows-DriverFrameworks-UserMode%4Operational.evtx"
)
EVTX_PNP_LOG = Path(
    r"C:\Windows\System32\winevt\Logs"
    r"\Microsoft-Windows-Kernel-PnP%4Configuration.evtx"
)

_RELEVANT_EVENT_IDS = {"2003", "2004", "2010", "20001", "20003"}
_CONNECT_IDS = {"2003", "20001"}
_RE_EVENT_ID = re.compile(r"<EventID[^>]*>(\d+)</EventID>")
_RE_DEVICE_ID = re.compile(
    r"USB\\VID_([0-9A-Fa-f]{4})&(?:amp;)?PID_([0-9A-Fa-f]{4})\\([^<&\"\s]+)"
)


def _extract_event_id(xml_data: str) -> str:
    """Extrae el EventID del XML del evento."""
    match = _RE_EVENT_ID.search(xml_data)
    return match.group(1) if match else ""


def _extract_usb_ids(xml_data: str) -> Dict[str, str]:
    """Extrae VID, PID y serial del XML del evento, si estan presentes."""
    match = _RE_DEVICE_ID.search(xml_data)
    if match:
        return {
            "vendor_id": match.group(1).upper(),
            "product_id": match.group(2).upper(),
            "serial": match.group(3).split("&")[0],
        }
    return {}


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
            xml_data = record.get("data", "")
            event_id = _extract_event_id(xml_data)
            if event_id not in _RELEVANT_EVENT_IDS:
                continue
            usb_ids = _extract_usb_ids(xml_data)
            event_type = "usb_connect" if event_id in _CONNECT_IDS else "usb_disconnect"
            events.append({
                "source": "evtx",
                "event_type": event_type,
                "event_id": event_id,
                "timestamp": record.get("timestamp", ""),
                "raw": xml_data[:500],
                "vendor_id": usb_ids.get("vendor_id", ""),
                "product_id": usb_ids.get("product_id", ""),
                "serial": usb_ids.get("serial", ""),
                "device_id": None,
                "session_id": None,
            })
    except Exception as exc:
        logger.warning("Error parseando %s: %s", evtx_path, exc)

    logger.info("Eventos USB extraidos de %s: %d", evtx_path.name, len(events))
    return events


def read_usb_events() -> List[Dict[str, Any]]:
    """Lee eventos USB desde los logs de DriverFrameworks y PnP."""
    all_events: List[Dict[str, Any]] = []
    for log_path in (EVTX_DRIVER_LOG, EVTX_PNP_LOG):
        if log_path.exists():
            all_events.extend(_parse_evtx_file(log_path))
        else:
            logger.info("Archivo evtx no encontrado: %s", log_path)
    return all_events
