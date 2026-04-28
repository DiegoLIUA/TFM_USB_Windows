"""
Lee artefactos USB del Registro de Windows (USBSTOR + USB).
Cruza ambas claves para obtener VID/PID reales, timestamps y tipo de dispositivo.
Fallback automático con datos simulados si no hay entradas reales o no hay acceso.
"""

import logging
import platform
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

USBSTOR_KEY = r"SYSTEM\CurrentControlSet\Enum\USBSTOR"
USB_KEY = r"SYSTEM\CurrentControlSet\Enum\USB"

_EPOCH_AS_FILETIME = 116444736000000000  # 1970-01-01 as Windows FILETIME

# Mapping de Service -> tipo de dispositivo
_SERVICE_TYPE_MAP = {
    "usbstor": "almacenamiento",
    "uaspstor": "almacenamiento",
    "hidusb": "HID",
    "usbhub": "hub",
    "usbhub3": "hub",
    "usbaudio": "audio",
    "usbvideo": "video",
    "usbccgp": "compuesto",
    "winusb": "winusb",
    "usbprint": "impresora",
}


def _filetime_to_str(filetime: int) -> Optional[str]:
    """Convierte Windows FILETIME (100ns desde 1601) a string ISO."""
    if filetime <= 0:
        return None
    try:
        us = (filetime - _EPOCH_AS_FILETIME) // 10
        dt = datetime(1970, 1, 1) + timedelta(microseconds=us)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return None


def _parse_serial(raw_serial: str) -> str:
    """Limpia el número de serie eliminando sufijos de instancia."""
    return raw_serial.split("&")[0] if "&" in raw_serial else raw_serial


def _build_container_map() -> Dict[str, Dict[str, str]]:
    """Construye mapa ContainerID -> {vendor_id, product_id, device_type}."""
    import winreg
    cmap: Dict[str, Dict[str, str]] = {}
    try:
        usb = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, USB_KEY)
    except FileNotFoundError:
        return cmap
    vid_pid_re = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", re.I)
    i = 0
    try:
        while True:
            name = winreg.EnumKey(usb, i); i += 1
            m = vid_pid_re.search(name)
            if not m:
                continue
            vid, pid = m.group(1).upper(), m.group(2).upper()
            try:
                vk = winreg.OpenKey(usb, name); j = 0
                while True:
                    try:
                        sk = winreg.OpenKey(vk, winreg.EnumKey(vk, j)); j += 1
                        cid = _read_str_value(sk, "ContainerID")
                        if not cid or cid.lower() in cmap:
                            continue
                        svc = (_read_str_value(sk, "Service") or "").lower()
                        cmap[cid.lower()] = {"vendor_id": vid, "product_id": pid,
                                             "device_type": _SERVICE_TYPE_MAP.get(svc, "otro")}
                    except OSError:
                        break
            except OSError:
                pass
    except OSError:
        pass
    return cmap


def _read_str_value(key, name: str) -> Optional[str]:
    import winreg
    try:
        val, _ = winreg.QueryValueEx(key, name)
        return str(val)
    except FileNotFoundError:
        return None


def _read_from_registry() -> List[Dict[str, Any]]:
    import winreg
    container_map = _build_container_map()
    devices: List[Dict[str, Any]] = []

    try:
        usbstor = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, USBSTOR_KEY)
    except FileNotFoundError:
        logger.warning("Clave USBSTOR no encontrada en el registro.")
        return devices

    class_idx = 0
    try:
        while True:
            device_class = winreg.EnumKey(usbstor, class_idx)
            class_idx += 1
            class_key = winreg.OpenKey(usbstor, device_class)

            # Timestamp de la clave de clase ≈ primera instalación
            class_info = winreg.QueryInfoKey(class_key)
            class_ts = _filetime_to_str(class_info[2])

            serial_idx = 0
            try:
                while True:
                    serial_raw = winreg.EnumKey(class_key, serial_idx)
                    serial_idx += 1
                    serial = _parse_serial(serial_raw)
                    serial_key = winreg.OpenKey(class_key, serial_raw)

                    # Timestamp de la clave serial ≈ última actividad
                    serial_info = winreg.QueryInfoKey(serial_key)
                    last_seen = _filetime_to_str(serial_info[2])
                    first_seen = class_ts

                    friendly = _read_str_value(serial_key, "FriendlyName")
                    if not friendly:
                        friendly = device_class

                    # Cruzar con USB key vía ContainerID
                    cid = _read_str_value(serial_key, "ContainerID")
                    vid = pid = ""
                    device_type = "almacenamiento"  # USBSTOR = storage
                    if cid and cid.lower() in container_map:
                        usb_info = container_map[cid.lower()]
                        vid = usb_info["vendor_id"]
                        pid = usb_info["product_id"]
                        device_type = usb_info["device_type"]

                    devices.append({
                        "vendor_id": vid,
                        "product_id": pid,
                        "serial": serial,
                        "friendly_name": friendly,
                        "first_seen": first_seen,
                        "last_seen": last_seen,
                        "device_type": device_type,
                    })
            except OSError:
                pass
    except OSError:
        pass

    return devices


def _simulated_devices() -> List[Dict[str, Any]]:
    """Datos simulados para entornos sin entradas USB reales."""
    tpl = {"device_type": "almacenamiento"}
    return [
        {**tpl, "vendor_id": "0781", "product_id": "5581", "serial": "DEMO_SN_001",
         "friendly_name": "SanDisk Ultra 32GB [DEMO]",
         "first_seen": "2025-01-10 08:30:00", "last_seen": "2025-03-15 17:45:00"},
        {**tpl, "vendor_id": "058F", "product_id": "6387", "serial": "DEMO_SN_002",
         "friendly_name": "Kingston DataTraveler 16GB [DEMO]",
         "first_seen": "2025-02-20 09:15:00", "last_seen": "2025-03-10 12:00:00"},
    ]


def read_usb_devices() -> List[Dict[str, Any]]:
    """Punto de entrada principal."""
    if platform.system() != "Windows":
        logger.info("Sistema no Windows — usando datos simulados.")
        return _simulated_devices()

    try:
        devices = _read_from_registry()
    except Exception as exc:
        logger.warning("Error leyendo registro: %s — usando datos simulados.", exc)
        return _simulated_devices()

    if not devices:
        logger.info("No se encontraron dispositivos USB reales — datos simulados.")
        return _simulated_devices()

    logger.info("Dispositivos USB leídos del registro: %d", len(devices))
    return devices
