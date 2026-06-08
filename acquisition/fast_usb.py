"""
Deteccion rapida de unidades USB extraibles montadas (WinAPI, ~0 ms).
Sirve para reaccionar de inmediato a la insercion de un USB de almacenamiento,
sin esperar al ciclo completo del monitor (que consulta WMI/PowerShell y tarda
mas de un segundo). No identifica dispositivos no-almacenamiento; para eso esta
el estado en vivo completo (live_state).
"""

import ctypes
import logging
import platform
import string
from typing import Dict

logger = logging.getLogger(__name__)

_DRIVE_REMOVABLE = 2
_DRIVE_FIXED = 3


def _volume_info(k32, root: str) -> Dict[str, str]:
    """Lee etiqueta y numero de serie de volumen de una unidad montada."""
    label = ctypes.create_unicode_buffer(1024)
    fsname = ctypes.create_unicode_buffer(1024)
    vol_serial = ctypes.c_uint()
    k32.GetVolumeInformationW(
        root, label, 1024, ctypes.byref(vol_serial),
        None, None, fsname, 1024)
    return {
        "label": label.value or "",
        "volume_serial": format(vol_serial.value, "08X"),
    }


def get_storage_drives() -> Dict[str, Dict[str, str]]:
    """
    Devuelve las unidades de almacenamiento montadas ahora mismo, tanto las
    extraibles (REMOVABLE: pendrives) como las fijas (FIXED). Esto ultimo es
    necesario porque algunos discos externos —SSD/HDD con adaptador UAS/USB-C—
    el sistema los presenta como FIXED, no como extraibles.
        { "D:": {"label": "...", "volume_serial": "AC115C2C",
                 "removable": "1"|"0"}, ... }
    Operacion casi instantanea (solo WinAPI, sin PowerShell). La distincion
    entre disco interno del sistema y disco externo recien conectado NO se hace
    aqui: corresponde a quien compara contra el conjunto ya conocido.
    """
    result: Dict[str, Dict[str, str]] = {}
    if platform.system() != "Windows":
        return result
    try:
        k32 = ctypes.windll.kernel32
        bitmask = k32.GetLogicalDrives()
        for i, letra in enumerate(string.ascii_uppercase):
            if not (bitmask & (1 << i)):
                continue
            root = letra + ":" + chr(92)  # "D:\"
            tipo = k32.GetDriveTypeW(root)
            if tipo not in (_DRIVE_REMOVABLE, _DRIVE_FIXED):
                continue
            info = _volume_info(k32, root)
            info["removable"] = "1" if tipo == _DRIVE_REMOVABLE else "0"
            result[letra + ":"] = info
    except OSError as exc:
        logger.debug("Error leyendo unidades de almacenamiento: %s", exc)
    return result


def get_removable_drives() -> Dict[str, Dict[str, str]]:
    """
    Devuelve solo las unidades extraibles montadas ahora mismo:
        { "D:": {"label": "ESD-USB", "volume_serial": "AC115C2C"}, ... }
    Se conserva por compatibilidad; para cubrir tambien discos externos fijos
    (UAS) usar get_storage_drives.
    """
    return {dl: {k: v for k, v in info.items() if k != "removable"}
            for dl, info in get_storage_drives().items()
            if info.get("removable") == "1"}
