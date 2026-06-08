"""
Detecta dispositivos USB conectados actualmente, su tipo y su capacidad.
Usa Win32_DiskDrive (WMI) para capacidad de almacenamiento y
Get-PnpDevice para enumerar TODOS los USB presentes (no solo almacenamiento).
"""

import json
import logging
import platform
import re
import subprocess
from typing import Dict, Any, List, Set

logger = logging.getLogger(__name__)

_PS_SCRIPT = r"""
$result = @()
# Discos externos: los USB clasicos (InterfaceType USB) y los que se presentan
# como SCSI pero son externos (adaptadores UAS/USB-SCSI, p. ej. SSD con cable
# tipo C). MediaType 'External hard disk media' distingue estos ultimos del
# disco interno del sistema, que es 'Fixed'.
$usbDrives = Get-WmiObject Win32_DiskDrive | Where-Object {
    $_.InterfaceType -eq 'USB' -or
    $_.MediaType -eq 'External hard disk media'
}
foreach ($drive in $usbDrives) {
    $pnpParts = $drive.PNPDeviceID.Split('\')
    $regSerial = if ($pnpParts.Count -ge 3) {
        ($pnpParts[2] -split '&')[0]
    } else { '' }
    # VID/PID: si el disco es USB clasico esta en su propio PNPDeviceID; si es
    # UAS/SCSI hay que mirar el dispositivo USB padre. El serial del padre
    # (inst) es el que casa con la enumeracion PnP de abajo.
    $vidpid = ''
    $usbInst = ''
    if ($drive.PNPDeviceID -match 'VID_([0-9A-Fa-f]{4}).PID_([0-9A-Fa-f]{4})') {
        $vidpid = "VID_$($matches[1])&PID_$($matches[2])"
    } else {
        $parent = (Get-PnpDeviceProperty -InstanceId $drive.PNPDeviceID `
            -KeyName 'DEVPKEY_Device_Parent' -ErrorAction SilentlyContinue).Data
        if ($parent -and $parent -match 'VID_([0-9A-Fa-f]{4}).PID_([0-9A-Fa-f]{4})') {
            $vidpid = "VID_$($matches[1])&PID_$($matches[2])"
            $pp = $parent.Split('\')
            if ($pp.Count -ge 3) { $usbInst = ($pp[2] -split '&')[0] }
        }
    }
    $letter = ''
    $parts = Get-WmiObject -Query (
        "ASSOCIATORS OF {Win32_DiskDrive.DeviceID='" +
        $drive.DeviceID +
        "'} WHERE AssocClass=Win32_DiskDriveToDiskPartition")
    foreach ($p in $parts) {
        $lds = Get-WmiObject -Query (
            "ASSOCIATORS OF {Win32_DiskPartition.DeviceID='" +
            $p.DeviceID +
            "'} WHERE AssocClass=Win32_LogicalDiskToPartition")
        foreach ($l in $lds) { $letter = $l.DeviceID }
    }
    $result += [PSCustomObject]@{
        t = 's'
        serial = $regSerial
        vidpid = $vidpid
        inst = $usbInst
        sz = [long]$drive.Size
        model = $drive.Model.Trim()
        dl = $letter
    }
}
$usbDevs = Get-PnpDevice -PresentOnly |
    Where-Object { $_.InstanceId.StartsWith('USB\VID_') }
foreach ($dev in $usbDevs) {
    $idParts = $dev.InstanceId.Split('\')
    $vidpid = if ($idParts.Count -ge 2) { $idParts[1] } else { '' }
    $inst = if ($idParts.Count -ge 3) { ($idParts[2] -split '&')[0] } else { '' }
    $result += [PSCustomObject]@{
        t = 'o'
        vidpid = $vidpid
        inst = $inst
        fn = $dev.FriendlyName
        cls = $dev.Class
    }
}
$result | ConvertTo-Json -Depth 2 -Compress
"""

_VID_PID_RE = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", re.I)

# Mapa de clase PnP de Windows -> tipo legible en espanol
_CLASS_TYPE_MAP = {
    "diskdrive":   "almacenamiento",
    "usbstor":     "almacenamiento",
    "wpd":         "almacenamiento",
    "scsiadapter": "almacenamiento",  # discos externos SSD/HDD por UAS (USB-SCSI)
    "hidclass":    "entrada (HID)",
    "keyboard":    "teclado",
    "mouse":       "raton",
    "bluetooth":   "bluetooth",
    "camera":      "camara",
    "image":       "camara",
    "media":       "audio/video",
    "audioendpoint": "audio",
    "net":         "red",
    "printer":     "impresora",
    "display":     "pantalla",
    "monitor":     "pantalla",
    "usbdevice":   "dispositivo USB",
    "usb":         "concentrador/compuesto",
    "ports":       "puerto serie",
}

# Clases que son infraestructura, no dispositivos de interes para el usuario
_IGNORED_CLASSES = {"usb"}  # hubs raiz / dispositivos compuestos contenedores


def _format_capacity(size_bytes: int) -> str:
    """Formatea bytes a una cadena legible (GB o MB)."""
    if size_bytes <= 0:
        return ""
    gb = size_bytes / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    return f"{size_bytes / (1024 ** 2):.0f} MB"


def _class_to_type(cls: str) -> str:
    """Traduce la clase PnP a un tipo legible."""
    return _CLASS_TYPE_MAP.get((cls or "").lower(), "otro")


def _empty_state() -> Dict[str, Any]:
    return {
        "connected_serials": set(),
        "connected_vidpid": set(),
        "capacity": {},
        "drive_letter": {},
        "present_devices": [],
    }


def get_live_usb_state() -> Dict[str, Any]:
    """
    Estado actual de los dispositivos USB conectados.
    Returns dict con:
        connected_serials: set de seriales de almacenamiento conectados
        connected_vidpid: set de "VID_PID" de cualquier USB conectado
        capacity: {serial: "14.8 GB"}
        drive_letter: {serial: "D:"}
        present_devices: lista de dicts con todos los USB presentes y su tipo
    """
    if platform.system() != "Windows":
        return _empty_state()

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _PS_SCRIPT],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("No se pudo consultar estado en vivo: %s", exc)
        return _empty_state()

    if proc.returncode != 0 or not proc.stdout.strip():
        logger.debug("PowerShell sin resultados USB en vivo.")
        return _empty_state()

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        logger.warning("JSON invalido de PowerShell.")
        return _empty_state()

    if not isinstance(data, list):
        data = [data]

    return _parse_live_data(data)


def _parse_live_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convierte la salida de PowerShell en el estado estructurado."""
    state = _empty_state()
    serials: Set[str] = state["connected_serials"]
    vidpids: Set[str] = state["connected_vidpid"]
    capacity: Dict[str, str] = state["capacity"]
    drive_letter: Dict[str, str] = state["drive_letter"]
    present: List[Dict[str, Any]] = state["present_devices"]

    # Capacidad de discos indexada por serial y por VID_PID. El VID_PID es el
    # identificador estable para discos UAS (su serial es un MSFT... volatil),
    # asi que es la clave principal para cruzar con la enumeracion PnP.
    storage_caps: Dict[str, str] = {}      # por serial de registro de disco
    cap_by_vidpid: Dict[str, str] = {}     # por "VID_PID"
    dl_by_vidpid: Dict[str, str] = {}      # letra de unidad por "VID_PID"
    for item in data:
        if item.get("t") != "s":
            continue
        cap = _format_capacity(int(item.get("sz") or 0))
        dl = item.get("dl") or ""
        # El serial de Win32_DiskDrive de un disco SCSI/UAS suele ser un indice
        # de enumeracion corto ("6", "4"...) que colisiona con otros PnP; no es
        # fiable como identificador. Solo se conserva para discos USB clasicos,
        # cuyo serial si es significativo (largo).
        serial = (item.get("serial") or "").strip().upper()
        inst = (item.get("inst") or "").strip().upper()
        es_uas = bool(inst)  # tiene padre USB -> vino por la rama UAS/SCSI
        if serial and not es_uas:
            serials.add(serial)
            if cap:
                capacity[serial] = cap
                storage_caps[serial] = cap
            if dl:
                drive_letter[serial] = dl
        # Clave estable VID_PID (del propio disco o de su USB padre): es el
        # identificador robusto para discos externos por adaptador UAS.
        mv = _VID_PID_RE.search(item.get("vidpid") or "")
        if mv:
            key = f"{mv.group(1).upper()}_{mv.group(2).upper()}"
            if cap:
                cap_by_vidpid[key] = cap
            if dl:
                dl_by_vidpid[key] = dl
        # Serial del USB padre (caso UAS): identificador largo y unico, sirve
        # para marcar el dispositivo presente como almacenamiento.
        if inst:
            serials.add(inst)
            if cap:
                storage_caps[inst] = cap
            if dl:
                drive_letter[inst] = dl

    for item in data:
        if item.get("t") != "o":
            continue
        m = _VID_PID_RE.search(item.get("vidpid") or "")
        if not m:
            continue
        vid, pid = m.group(1).upper(), m.group(2).upper()
        key = f"{vid}_{pid}"
        cls = (item.get("cls") or "").lower()
        if cls in _IGNORED_CLASSES:
            continue
        vidpids.add(key)
        serial = (item.get("inst") or "").strip().upper()
        # Es almacenamiento si Win32_DiskDrive lo reconocio como disco: ya sea
        # por su VID_PID (clave estable, vale para SSD/HDD externos con
        # adaptador UAS) o por el serial del registro de disco. Este cruce
        # prevalece sobre el mapa de clases (que daria "otro" para SCSIAdapter).
        es_disco = key in cap_by_vidpid or serial in storage_caps
        tipo = "almacenamiento" if es_disco else _class_to_type(cls)
        cap = cap_by_vidpid.get(key) or capacity.get(serial, "")
        present.append({
            "vendor_id":    vid,
            "product_id":   pid,
            "serial":       serial,
            "friendly_name": item.get("fn") or "Dispositivo USB",
            "device_type":  tipo,
            "capacity":     cap,
            "connected":    True,
            "sources":      "tiempo real",
        })

    logger.info(
        "Estado en vivo: %d almacenamiento, %d dispositivos USB presentes.",
        len(serials), len(present),
    )
    return state
