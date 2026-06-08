"""
Prevencion: bloqueo temporal opcional de dispositivos en modo estricto.
Por defecto el bloqueo es solo logico (registrado en BD). El bloqueo fisico
via Disable-PnpDevice requiere admin y se controla por config.
"""

import json
import logging
import re
import subprocess
from typing import List, Dict, Any, Optional

from store.anomaly_store import get_config, set_config

logger = logging.getLogger(__name__)

# Seriales desbloqueados en la sesion actual (en memoria, no se persiste).
# El monitor no vuelve a alertar ni bloquear estos dispositivos hasta que se
# cierre la aplicacion. Se restablece al reiniciar el proceso.
_session_unlocked: set = set()


def mark_unlocked(serial: str) -> None:
    """Marca un serial como desbloqueado para el resto de la sesion."""
    if serial:
        _session_unlocked.add(serial)
        logger.info("Dispositivo desbloqueado en esta sesion: %s", serial)


def is_session_unlocked(serial: str) -> bool:
    """True si el serial fue desbloqueado en esta sesion."""
    return serial in _session_unlocked


def clear_session_unlocked() -> None:
    """Limpia la lista de desbloqueados (p. ej. al reiniciar el monitor)."""
    _session_unlocked.clear()


# InstanceId valido: USB\VID_xxxx&PID_xxxx\serial (serial alfanumerico).
# Los descriptores USB son controlables por un atacante, asi que se valida
# de forma estricta antes de pasarlos a PowerShell (evita inyeccion).
_INSTANCE_RE = re.compile(
    r"^USB\\VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}\\[A-Za-z0-9_\-]{1,64}$"
)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_HEXID_RE = re.compile(r"^[0-9A-Fa-f]{4}$")


def _validate_instance_id(instance_id: str) -> Optional[str]:
    """Devuelve el instance_id si es seguro, o None si no supera la validacion."""
    if instance_id and _INSTANCE_RE.match(instance_id):
        return instance_id
    if instance_id:
        logger.warning("InstanceId rechazado por validacion: %r", instance_id[:80])
    return None


def _is_strict_mode() -> bool:
    return (get_config("anomaly.mode", "aprendizaje") or "").lower() == "estricto"


def _physical_block_enabled() -> bool:
    return (get_config("prevention.physical_block", "false") or "").lower() == "true"


def _run_pnp_cmdlet(cmdlet: str, instance_id: str) -> bool:
    """
    Ejecuta Disable/Enable-PnpDevice de forma segura: valida el InstanceId
    contra una regex estricta y lo pasa por variable de entorno (no se
    interpola en el comando, lo que evita inyeccion y problemas con el caracter
    '&' del identificador VID&PID). Requiere admin.
    """
    import os
    safe_id = _validate_instance_id(instance_id)
    if not safe_id:
        return False
    # El InstanceId llega via $env:PNP_TARGET; PowerShell no lo evalua como
    # codigo, por lo que el '&' de 'VID_xxxx&PID_yyyy' no rompe el comando.
    script = f"{cmdlet} -InstanceId $env:PNP_TARGET -Confirm:$false"
    env = dict(os.environ, PNP_TARGET=safe_id)
    cmd = ["powershell", "-NoProfile", "-Command", script]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=10, env=env)
        ok = proc.returncode == 0
        if not ok:
            logger.warning("%s fallo: %s", cmdlet, proc.stderr[:200])
        return ok
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("No se pudo invocar %s: %s", cmdlet, exc)
        return False


def _disable_pnp_device(instance_id: str) -> bool:
    """Intenta deshabilitar el dispositivo via PowerShell. Requiere admin."""
    return _run_pnp_cmdlet("Disable-PnpDevice", instance_id)


def maybe_block_devices(
    alerts: List[Dict[str, Any]],
    devices: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    En modo estricto, registra (y opcionalmente aplica) bloqueo
    para dispositivos con alertas de severidad alta.
    Devuelve lista de bloqueos aplicados (logicos o fisicos).
    """
    if not _is_strict_mode() or not alerts:
        return []

    high = [a for a in alerts if (a.get("severity") or "").lower() == "alta"]
    if not high:
        return []

    by_id = {d.get("id"): d for d in devices if d.get("id")}
    physical = _physical_block_enabled()
    blocked: List[Dict[str, Any]] = []
    for a in high:
        dev = by_id.get(a.get("device_id"))
        if not dev:
            continue
        record = {
            "device_id":  dev.get("id"),
            "serial":     dev.get("serial"),
            "score":      a.get("score"),
            "severity":   a.get("severity"),
            "physical":   False,
        }
        if physical:
            instance = _build_instance_id(dev)
            if instance and _disable_pnp_device(instance):
                record["physical"] = True
        _persist_block(record)
        blocked.append(record)

    logger.info("Bloqueos aplicados: %d (fisico=%s).", len(blocked), physical)
    return blocked


def block_for_schedule(device: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bloquea un dispositivo insertado fuera de horario.
    Deshabilita el USB (Disable-PnpDevice) y registra el bloqueo pendiente
    de desbloqueo TOTP. Devuelve el registro del bloqueo.
    """
    instance = _build_instance_id(device)
    physical = False
    if instance and _disable_pnp_device(instance):
        physical = True
    record = {
        "device_id":   device.get("id"),
        "serial":      device.get("serial"),
        "friendly_name": device.get("friendly_name") or device.get("serial"),
        "reason":      "insercion fuera de horario habitual",
        "physical":    physical,
        "instance":    instance,
        "unlocked":    False,
    }
    _persist_block(record)
    logger.warning("Dispositivo bloqueado por horario: %s (fisico=%s)",
                   device.get("serial"), physical)
    return record


def unlock_device(instance_id: str) -> bool:
    """Reactiva un dispositivo previamente deshabilitado. Requiere admin."""
    if not instance_id:
        return True
    return _run_pnp_cmdlet("Enable-PnpDevice", instance_id)


def _build_instance_id(device: Dict[str, Any]) -> str:
    """
    Construye un InstanceId USB\\VID_xxxx&PID_xxxx\\serial.
    Los descriptores USB son controlables por un atacante, por lo que cada
    componente se valida; si alguno no encaja, se devuelve cadena vacia y no
    se intentara ningun bloqueo fisico (defensa en profundidad).
    """
    vid = (device.get("vendor_id") or "").strip()
    pid = (device.get("product_id") or "").strip()
    serial = (device.get("serial") or "").strip()
    if not (_HEXID_RE.match(vid) and _HEXID_RE.match(pid)
            and _TOKEN_RE.match(serial)):
        return ""
    return f"USB\\VID_{vid.upper()}&PID_{pid.upper()}\\{serial}"


def _persist_block(record: Dict[str, Any]) -> None:
    """Almacena el historial de bloqueos como lista JSON en config."""
    raw = get_config("prevention.block_log", "[]") or "[]"
    try:
        log = json.loads(raw)
        if not isinstance(log, list):
            log = []
    except json.JSONDecodeError:
        log = []
    log.append(record)
    set_config("prevention.block_log", json.dumps(log[-100:]))
