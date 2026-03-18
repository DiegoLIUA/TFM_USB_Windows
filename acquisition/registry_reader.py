"""
Lee artefactos USB del Registro de Windows (USBSTOR).
Fallback automático con datos simulados si no hay entradas reales o no hay acceso.
"""

import logging
import platform
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

USBSTOR_KEY = r"SYSTEM\CurrentControlSet\Enum\USBSTOR"


def _parse_serial(raw_serial: str) -> str:
    """Limpia el número de serie eliminando sufijos de instancia."""
    return raw_serial.split("&")[0] if "&" in raw_serial else raw_serial


def _read_from_registry() -> List[Dict[str, Any]]:
    """Lee HKLM\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR via winreg."""
    import winreg

    devices: List[Dict[str, Any]] = []

    try:
        usbstor = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, USBSTOR_KEY)
    except FileNotFoundError:
        logger.warning("Clave USBSTOR no encontrada en el registro.")
        return devices

    device_class_count = 0
    try:
        while True:
            device_class = winreg.EnumKey(usbstor, device_class_count)
            device_class_count += 1
            parts = device_class.split("&")
            vendor_id = parts[1].replace("Vid_", "") if len(parts) > 1 else ""
            product_id = parts[2].replace("Pid_", "") if len(parts) > 2 else ""
            friendly = device_class

            try:
                class_key = winreg.OpenKey(usbstor, device_class)
                serial_idx = 0
                while True:
                    serial_raw = winreg.EnumKey(class_key, serial_idx)
                    serial_idx += 1
                    serial = _parse_serial(serial_raw)

                    first_seen = last_seen = None
                    try:
                        serial_key = winreg.OpenKey(class_key, serial_raw)
                        try:
                            props_key = winreg.OpenKey(serial_key, "Properties\\{83da6326-97a6-4088-9453-a1923f573b29}")
                            try:
                                val, _ = winreg.QueryValueEx(props_key, "0064")
                                first_seen = str(val)
                            except FileNotFoundError:
                                pass
                            try:
                                val, _ = winreg.QueryValueEx(props_key, "0066")
                                last_seen = str(val)
                            except FileNotFoundError:
                                pass
                        except FileNotFoundError:
                            pass
                        try:
                            fn_val, _ = winreg.QueryValueEx(serial_key, "FriendlyName")
                            friendly = fn_val
                        except FileNotFoundError:
                            pass
                    except OSError:
                        pass

                    devices.append({
                        "vendor_id":    vendor_id,
                        "product_id":   product_id,
                        "serial":       serial,
                        "friendly_name": friendly,
                        "first_seen":   first_seen,
                        "last_seen":    last_seen,
                    })
            except OSError:
                pass
    except OSError:
        pass

    return devices


def _simulated_devices() -> List[Dict[str, Any]]:
    """Datos simulados para entornos sin entradas USB reales."""
    return [
        {
            "vendor_id":    "0781",
            "product_id":   "5581",
            "serial":       "DEMO_SN_001",
            "friendly_name": "SanDisk Ultra 32GB [DEMO]",
            "first_seen":   "2025-01-10 08:30:00",
            "last_seen":    "2025-03-15 17:45:00",
        },
        {
            "vendor_id":    "058F",
            "product_id":   "6387",
            "serial":       "DEMO_SN_002",
            "friendly_name": "Kingston DataTraveler 16GB [DEMO]",
            "first_seen":   "2025-02-20 09:15:00",
            "last_seen":    "2025-03-10 12:00:00",
        },
        {
            "vendor_id":    "13FE",
            "product_id":   "4200",
            "serial":       "DEMO_SN_003",
            "friendly_name": "Patriot Memory 64GB [DEMO]",
            "first_seen":   "2024-11-05 16:00:00",
            "last_seen":    "2025-01-22 11:30:00",
        },
    ]


def read_usb_devices() -> List[Dict[str, Any]]:
    """
    Punto de entrada principal.
    Intenta leer el registro real; si falla o no hay datos, usa simulados.
    """
    if platform.system() != "Windows":
        logger.info("Sistema no Windows — usando datos simulados.")
        return _simulated_devices()

    try:
        devices = _read_from_registry()
    except Exception as exc:
        logger.warning("Error leyendo registro: %s — usando datos simulados.", exc)
        return _simulated_devices()

    if not devices:
        logger.info("No se encontraron dispositivos USB reales — usando datos simulados.")
        return _simulated_devices()

    logger.info("Dispositivos USB leídos del registro: %d", len(devices))
    return devices
