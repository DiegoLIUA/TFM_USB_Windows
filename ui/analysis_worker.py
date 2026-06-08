"""
Hilo de analisis: orquesta adquisicion, correlacion, persistencia y deteccion.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


def _enrich_live(dev: Dict[str, Any], live: Dict[str, Any]) -> None:
    """Anade estado en vivo (conectado, capacidad, letra de unidad)."""
    serial = (dev.get("serial") or "").upper()
    vid = (dev.get("vendor_id") or "").upper()
    pid = (dev.get("product_id") or "").upper()
    vp = f"{vid}_{pid}"
    dev["connected"] = (serial in live["connected_serials"]
                        or vp in live["connected_vidpid"])
    # Capacidad y letra: por serial (disco USB clasico) o, como respaldo, por
    # VID_PID desde el dispositivo presente (discos externos UAS, cuyo serial
    # no es estable). Asi la capacidad del SSD por adaptador tambien se muestra.
    cap = live["capacity"].get(serial, "")
    dl = live["drive_letter"].get(serial, "")
    if not cap or not dl:
        for pres in live.get("present_devices", []):
            if f"{pres['vendor_id']}_{pres['product_id']}" == vp:
                cap = cap or pres.get("capacity") or ""
                break
    dev["capacity"] = cap or dev.get("capacity") or ""
    dev["drive_letter"] = dl


def _is_real_serial(serial: str) -> bool:
    """
    Decide si una cadena es un serial USB real y no un numero de instancia
    compartido (p. ej. '5', '6', que Windows asigna por enumeracion y colisiona
    entre dispositivos). Se acepta como serial real si:
      - tiene >= 6 caracteres y no es puramente numerico (lo habitual: mezcla
        letras y digitos, posiblemente con separadores), o
      - tiene >= 8 caracteres alfanumericos (cubre seriales largos solo de
        digitos, que sí son legitimos).
    """
    s = (serial or "").strip()
    if len(s) >= 6 and not s.isdigit():
        return True
    return s.isalnum() and len(s) >= 8


def _live_serial(dev: Dict[str, Any]) -> str:
    """Serial estable para un dispositivo en vivo; sintetico si no es real."""
    serial = (dev.get("serial") or "").strip().upper()
    if serial and serial != "UNKNOWN" and _is_real_serial(serial):
        return serial
    return f"VIDPID_{dev.get('vendor_id', '')}_{dev.get('product_id', '')}"


def _resolve_sources(dev: Dict[str, Any], db_sources: str) -> str:
    """
    Determina las fuentes a mostrar. Si el dispositivo solo se conoce en vivo
    (serial sintetico), muestra 'tiempo real'. Si esta conectado ahora, lo anade.
    """
    serial = (dev.get("serial") or "")
    if serial.startswith("VIDPID_"):
        return "tiempo real"
    parts = [p.strip() for p in (db_sources or "").split(",") if p.strip()]
    if dev.get("connected") and "tiempo real" not in parts:
        parts.append("tiempo real")
    return ", ".join(parts) or "registro"


def _merge_live_devices(devices, live, now):
    """
    Fusiona los dispositivos presentes en vivo con los del registro.
    Anade los que no existen ya (por serial o por VID_PID) con su tipo real.
    Devuelve la lista de dispositivos en vivo a persistir.
    """
    known_serials = {(d.get("serial") or "").upper() for d in devices}
    known_vidpid = {f"{(d.get('vendor_id') or '').upper()}_"
                    f"{(d.get('product_id') or '').upper()}" for d in devices}
    nuevos = []
    for pres in live.get("present_devices", []):
        vp = f"{pres['vendor_id']}_{pres['product_id']}"
        serial = _live_serial(pres)
        if serial in known_serials or vp in known_vidpid:
            continue
        nuevos.append({
            "vendor_id":    pres["vendor_id"],
            "product_id":   pres["product_id"],
            "serial":       serial,
            "friendly_name": pres["friendly_name"],
            "device_type":  pres["device_type"],
            "first_seen":   now,
            "last_seen":    now,
            "capacity":     pres.get("capacity") or "",
        })
        known_serials.add(serial)
        known_vidpid.add(vp)
    return nuevos


class AnalysisWorker(QThread):
    """Hilo secundario para no bloquear la UI durante el analisis."""
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def run(self) -> None:
        try:
            from acquisition.registry_reader import read_usb_devices
            from acquisition.evtx_reader import read_usb_events
            from acquisition.setupapi_reader import read_setupapi_devices
            from acquisition.live_state import get_live_usb_state
            from normalization.normalizer import normalize_devices
            from normalization.correlator import correlate_sources
            from store.database import (
                initialize_database, upsert_device, get_all_devices,
                insert_event, get_device_sources,
            )
            from analytics.pipeline import (
                persist_sessions, load_or_train_detector, score_and_alert,
            )
            from analytics.prevention import maybe_block_devices

            raw = read_usb_devices()
            evtx_events = read_usb_events()
            setupapi_entries = read_setupapi_devices()
            live = get_live_usb_state()

            clean = normalize_devices(raw)
            initialize_database()
            result = correlate_sources(clean, evtx_events, setupapi_entries)

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for dev in result["devices"]:
                _enrich_live(dev, live)
                if dev["connected"]:
                    dev["last_seen"] = now

            # Anadir dispositivos USB presentes en vivo que no estan en el
            # registro (raton bluetooth, camara, pantalla, etc.)
            for nuevo in _merge_live_devices(result["devices"], live, now):
                result["devices"].append(nuevo)

            serial_to_id = {}
            for dev in result["devices"]:
                serial_to_id[dev.get("serial", "")] = upsert_device(dev)

            for evt in result["events"]:
                serial = evt.pop("_serial", "")
                evt["device_id"] = serial_to_id.get(serial)
                insert_event(evt)

            saved_sessions = persist_sessions(
                result.get("sessions", []), serial_to_id,
            )
            detector = load_or_train_detector()
            alerts = score_and_alert(detector, saved_sessions, serial_to_id)
            blocked = maybe_block_devices(alerts, result["devices"])

            devices = get_all_devices()
            for dev in devices:
                _enrich_live(dev, live)
                dev["sources"] = _resolve_sources(
                    dev, get_device_sources(dev["id"]))

            self.finished.emit({
                "devices": devices,
                "alerts":  alerts,
                "blocked": blocked,
            })
        except Exception as exc:
            logger.exception("Error durante el analisis")
            self.error.emit(str(exc))
