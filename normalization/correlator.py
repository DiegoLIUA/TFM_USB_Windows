"""
Correlaciona artefactos de las 3 fuentes (registro, evtx, setupapi)
en sesiones USB coherentes y unicas.
"""

import logging
from typing import List, Dict, Any, Optional

from normalization.normalizer import normalize_timestamp

logger = logging.getLogger(__name__)


def _matches_device(device: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    """Comprueba si una entrada coincide con un dispositivo por serial o VID+PID."""
    serial = device.get("serial", "")
    vid = device.get("vendor_id", "")
    pid = device.get("product_id", "")
    e_serial = entry.get("serial", "")
    e_vid = entry.get("vendor_id", "")
    e_pid = entry.get("product_id", "")
    if serial and e_serial and serial.upper() == e_serial.upper():
        return True
    if vid and pid and e_vid == vid and e_pid == pid:
        return True
    return False


def _match_device_to_events(
    device: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filtra eventos que coinciden con un dispositivo."""
    return [evt for evt in events if _matches_device(device, evt)]


def _build_sessions(
    device_id: int,
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Agrupa eventos connect/disconnect en sesiones."""
    sorted_events = sorted(events, key=lambda e: e.get("timestamp") or "")
    sessions: List[Dict[str, Any]] = []
    current_session: Optional[Dict[str, Any]] = None

    for evt in sorted_events:
        ts = normalize_timestamp(evt.get("timestamp"))
        if evt.get("event_type") == "usb_connect":
            if current_session:
                sessions.append(current_session)
            current_session = {
                "device_id": device_id,
                "connected": ts,
                "disconnected": None,
                "drive_letter": None,
            }
        elif evt.get("event_type") == "usb_disconnect":
            if current_session:
                current_session["disconnected"] = ts
                sessions.append(current_session)
                current_session = None

    if current_session:
        sessions.append(current_session)
    return sessions


def _enrich_first_seen(
    device: Dict[str, Any],
    setupapi_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Actualiza first_seen con el timestamp mas antiguo de setupapi si existe."""
    for entry in setupapi_entries:
        if not _matches_device(device, entry):
            continue
        ts = normalize_timestamp(entry.get("timestamp"))
        if ts and (not device.get("first_seen") or ts < device["first_seen"]):
            device["first_seen"] = ts
    return device


def correlate_sources(
    devices: List[Dict[str, Any]],
    evtx_events: List[Dict[str, Any]],
    setupapi_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Correlaciona las 3 fuentes. Retorna dict con:
    - devices: lista enriquecida
    - events: lista de eventos con _serial para asignar device_id tras upsert
    - sources_map: mapping serial -> lista de fuentes
    """
    all_events: List[Dict[str, Any]] = []
    enriched_devices: List[Dict[str, Any]] = []
    sources_map: Dict[str, List[str]] = {}

    for device in devices:
        serial = device.get("serial", "")
        sources = ["registro"]

        matched_setupapi = [
            e for e in setupapi_entries if _matches_device(device, e)
        ]
        if matched_setupapi:
            device = _enrich_first_seen(device, matched_setupapi)
            sources.append("setupapi")

        matched_evtx = _match_device_to_events(device, evtx_events)
        if matched_evtx:
            sources.append("evtx")

        enriched_devices.append(device)
        sources_map[serial] = sources

        for evt in matched_evtx:
            evt_copy = dict(evt)
            evt_copy["_serial"] = serial
            all_events.append(evt_copy)

        for entry in matched_setupapi:
            all_events.append({
                "source": "setupapi",
                "event_type": "device_install",
                "timestamp": normalize_timestamp(entry.get("timestamp")),
                "raw": entry.get("hardware_id", "")[:500],
                "_serial": serial,
                "device_id": None,
                "session_id": None,
            })

    logger.info(
        "Correlacion completada: %d dispositivos, %d eventos",
        len(enriched_devices), len(all_events),
    )
    return {
        "devices": enriched_devices,
        "events": all_events,
        "sources_map": sources_map,
    }
