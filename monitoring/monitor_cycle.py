"""
Logica de un ciclo de monitorizacion: captura senales del sistema,
detecta USBs recien conectados y aplica bloqueo por horario si procede.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Set, Tuple

from acquisition.live_state import get_live_usb_state
from acquisition.power_reader import read_power_signals
from acquisition.session_reader import read_session_signals
from acquisition.activity_reader import sample_activity
from store.signals_store import insert_signals
from store.database import get_trusted_serials, get_device_by_serial
from store.anomaly_store import get_config, insert_alert
from security.schedule import is_anomalous_schedule, get_schedule
from analytics.prevention import block_for_schedule, is_session_unlocked

logger = logging.getLogger(__name__)


# Cada cuantos ciclos releer los logs historicos (power/session). Estas
# senales cambian despacio, asi que no merece la pena lanzar PowerShell cada
# ciclo: solo la actividad/idle se muestrea siempre (es volatil y barata).
HISTORIC_EVERY = 10


def capture_signals(include_historic: bool = True) -> int:
    """
    Captura y persiste senales del sistema. Devuelve cuantas eran nuevas.
    - activity (app en primer plano + idle): siempre, es barata y volatil.
    - power/session (Event Logs via PowerShell): solo si include_historic,
      porque cambian despacio y la consulta es costosa.
    """
    signals: List[Dict[str, Any]] = list(sample_activity())
    if include_historic:
        signals.extend(read_power_signals(max_events=30))
        signals.extend(read_session_signals(max_events=30))
    new_count = insert_signals(signals)
    if new_count:
        logger.info("Monitor: %d senales nuevas capturadas%s.",
                    new_count, " (incl. historicas)" if include_historic else "")
    return new_count


def _device_key(d: Dict[str, Any]) -> str:
    """Identificador estable de un dispositivo USB presente (serial o VID_PID)."""
    serial = (d.get("serial") or "").strip()
    if serial:
        return serial
    return f"{d.get('vendor_id', '')}_{d.get('product_id', '')}"


def detect_new_usb(
    known_serials: Set[str],
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Compara el estado en vivo con los seriales conocidos.
    Devuelve (seriales_nuevos, estado_en_vivo).
    """
    live = get_live_usb_state()
    current = set(live.get("connected_serials", set()))
    new = sorted(current - known_serials)
    return new, live


def _alert(serial: str, motivo: str, components: Dict[str, float],
           nombre: str = None) -> None:
    """Registra una alerta de insercion con el motivo y desglose indicados."""
    dev = get_device_by_serial(serial)
    device_id = dev["id"] if dev else None
    nombre = nombre or (dev.get("friendly_name") if dev else None) or serial
    insert_alert({
        "device_id":  device_id,
        "session_id": None,
        "severity":   "alta",
        "score":      1.0,
        "reason":     f"«{nombre}»: {motivo}",
        "components": json.dumps(components),
    })


def _evaluate(serial: str):
    """
    Aplica la politica de seguridad a un dispositivo. Devuelve (motivo, comp)
    donde motivo es la causa (vacio si esta permitido) y comp el desglose de
    componentes acorde a la causa. Politica: en horario habitual solo pasan los
    dispositivos de confianza; fuera de horario, ninguno pasa.
    """
    fuera = is_anomalous_schedule(datetime.now())
    confiable = serial in get_trusted_serials()
    causas = []
    comp = {"hour_rarity": 0.0, "device_rarity": 0.0, "mahalanobis": 0.0}
    if not confiable:
        causas.append("dispositivo no confiable")
        comp["device_rarity"] = 1.0
    if fuera:
        causas.append("inserción fuera del horario habitual")
        comp["hour_rarity"] = 1.0
    if not causas:
        return "", comp  # confiable y dentro de horario: permitido
    return " y ".join(causas), comp


def _react_to_devices(
    devices_info: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Aplica la politica de seguridad a una lista de dispositivos recien
    conectados. Cada elemento es un dict con al menos 'serial' y, si se conoce,
    'friendly_name', 'id', 'vendor_id', 'product_id', 'capacity'.
    En monitorizacion alerta; en estricto alerta y bloquea. Solo actua sobre
    dispositivos que no son de confianza o que se conectan fuera de horario.
    Devuelve los bloqueos aplicados.
    """
    mode = (get_config("anomaly.mode", "aprendizaje") or "").lower()
    if mode not in ("monitorizacion", "estricto"):
        return []
    sch = get_schedule()
    if not sch["days"]:
        return []  # sin horario definido no se aplica la politica

    blocks: List[Dict[str, Any]] = []
    for dev in devices_info:
        serial = dev.get("serial") or "USB_DESCONOCIDO"
        if is_session_unlocked(serial):
            continue  # ya desbloqueado en esta sesion
        motivo, comp = _evaluate(serial)
        if not motivo:
            continue  # confiable y dentro de horario: permitido
        _alert(serial, motivo, comp, dev.get("friendly_name"))
        if mode == "estricto":
            blocks.append(block_for_schedule(dev))
    if blocks:
        logger.info("Monitor: %d dispositivo(s) bloqueado(s) por politica.",
                    len(blocks))
    return blocks


def run_fast_usb_check(known_drives: Set[str]) -> Dict[str, Any]:
    """
    Comprobacion rapida (sin PowerShell, ~0 ms) de unidades de almacenamiento
    recien montadas. Permite reaccionar a la insercion de un USB en menos de un
    segundo, sin esperar al ciclo completo. Cubre tanto extraibles (pendrives)
    como discos externos fijos (SSD/HDD por adaptador UAS, que el sistema
    presenta como FIXED). Genera alerta y, en estricto, bloquea. Las unidades
    presentes al iniciar el monitor (incluido el disco del sistema) forman parte
    de known_drives y por tanto no disparan reaccion.
    Devuelve dict con unidades nuevas, bloqueos y el estado actual.
    """
    from acquisition.fast_usb import get_storage_drives
    current = set(get_storage_drives().keys())
    new = sorted(current - known_drives)
    removed = sorted(known_drives - current)

    # Cada unidad nueva se resuelve a su dispositivo una sola vez (evita lanzar
    # PowerShell dos veces: para la sesion y para la politica).
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resueltos = {letra: _resolve_drive_device(letra) for letra in new}
    for letra, dev in resueltos.items():
        _open_storage_session(letra, ahora, dev)
    for letra in removed:
        _close_storage_session(letra, ahora)

    blocks: List[Dict[str, Any]] = []
    if new:
        blocks = _react_to_new_drives(resueltos)
    return {"new_drives": new, "blocks": blocks, "current_drives": current}


def _resolve_drive_device(letra: str) -> Dict[str, Any]:
    """
    Identifica el dispositivo de almacenamiento montado en una letra de unidad.
    Consulta el estado en vivo (que mapea serial -> letra) y cruza con el
    registro para devolver el dispositivo concreto. Solo debe invocarse al
    detectar una unidad nueva (no en cada tick), pues usa PowerShell. Si no
    logra resolverlo por letra, recurre al almacenamiento mas reciente en BD.
    Devuelve un dict con id, serial, friendly_name, vendor_id, product_id,
    capacity (campos None/"" si no se conoce).
    """
    from store.database import get_all_devices, get_device_by_serial
    # 1) Intento exacto por letra usando el estado en vivo.
    try:
        from acquisition.live_state import get_live_usb_state
        live = get_live_usb_state()
        serial = next((s for s, dl in live.get("drive_letter", {}).items()
                       if dl == letra), None)
        if serial:
            dev = get_device_by_serial(serial)
            if dev:
                return dev
            # Conocido en vivo pero aun no en BD: tomar sus datos reales de la
            # enumeracion presente (nombre, VID/PID, capacidad) cruzando por
            # serial; asi la alerta y el bloqueo muestran el dispositivo real.
            pres = next((p for p in live.get("present_devices", [])
                         if (p.get("serial") or "").upper() == serial), {})
            return {"id": None, "serial": serial,
                    "friendly_name": pres.get("friendly_name")
                    or "Dispositivo USB",
                    "vendor_id": pres.get("vendor_id") or "",
                    "product_id": pres.get("product_id") or "",
                    "capacity": pres.get("capacity")
                    or live.get("capacity", {}).get(serial, "")}
    except Exception as exc:  # noqa: BLE001 (resolucion best-effort)
        logger.debug("No se pudo resolver la unidad %s en vivo: %s", letra, exc)
    # 2) Respaldo: almacenamiento mas reciente en BD (orden last_seen DESC).
    almacenamiento = [d for d in get_all_devices()
                      if d.get("device_type") == "almacenamiento"]
    return almacenamiento[0] if almacenamiento else {}


def _open_storage_session(letra: str, ahora: str,
                          dev: Dict[str, Any] = None) -> None:
    """Abre una sesion para el dispositivo de almacenamiento de esa unidad."""
    from store.database import open_drive_session
    if dev is None:
        dev = _resolve_drive_device(letra)
    open_drive_session(dev.get("id"), letra, ahora)


def _close_storage_session(letra: str, ahora: str) -> None:
    """Cierra la sesion abierta de una unidad que se acaba de retirar."""
    from store.database import close_drive_session
    close_drive_session(letra, ahora)


def _react_to_new_drives(
    resueltos: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Aplica la politica de seguridad a las unidades de almacenamiento nuevas.
    Recibe el mapa letra -> dispositivo ya resuelto (para no reconsultar).
    """
    devices_info = []
    for dev in resueltos.values():
        devices_info.append({
            "id": dev.get("id"),
            "serial": dev.get("serial") or "USB_DESCONOCIDO",
            "friendly_name": dev.get("friendly_name") or "Dispositivo USB",
            "vendor_id": dev.get("vendor_id") or "",
            "product_id": dev.get("product_id") or "",
            "capacity": dev.get("capacity") or "",
        })
    return _react_to_devices(devices_info)


def run_cycle(known_serials: Set[str], cycle_index: int = 0,
              known_usb_keys: Set[str] = None) -> Dict[str, Any]:
    """
    Ejecuta un ciclo de monitorizacion.
    Las senales historicas (power/session) solo se releen cada HISTORIC_EVERY
    ciclos. Aplica la politica de seguridad a TODOS los dispositivos USB nuevos
    (no solo almacenamiento), identificados via present_devices del estado en
    vivo. Devuelve senales, USBs nuevos, bloqueos y claves USB actuales.
    """
    include_historic = (cycle_index % HISTORIC_EVERY == 0)
    new_signals = capture_signals(include_historic=include_historic)
    _new_storage, live = detect_new_usb(known_serials)

    known_usb_keys = known_usb_keys or set()
    present = live.get("present_devices", [])
    current_keys = {_device_key(d) for d in present}
    new_devices = [d for d in present
                   if _device_key(d) not in known_usb_keys]

    blocks = _react_to_devices([{
        "id": None,
        "serial": _device_key(d),
        "friendly_name": d.get("friendly_name") or "Dispositivo USB",
        "vendor_id": d.get("vendor_id") or "",
        "product_id": d.get("product_id") or "",
        "capacity": d.get("capacity") or "",
    } for d in new_devices]) if new_devices else []

    return {
        "new_signals":      new_signals,
        "new_usb":          [d.get("friendly_name") for d in new_devices],
        "blocks":           blocks,
        "connected_serials": set(live.get("connected_serials", set())),
        "current_usb_keys": current_keys,
        "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
