"""
Tests de interpretacion del estado USB en vivo (acquisition.live_state).
Se centran en el cruce de capacidad/tipo para discos externos por adaptador
UAS (USB-SCSI), cuyo serial de enumeracion es corto y no fiable.
"""

from acquisition.live_state import _parse_live_data


def test_ssd_uas_es_almacenamiento_con_capacidad():
    """
    Un SSD externo por adaptador UAS llega como disco SCSI (registro 's' con
    vidpid del padre y serial corto) y como PnP SCSIAdapter (registro 'o'). Debe
    resolverse como almacenamiento con su capacidad, cruzando por VID_PID.
    """
    data = [
        {"t": "s", "serial": "6", "vidpid": "VID_0781&PID_558C",
         "inst": "MSFT3031383136", "sz": 250056737280,
         "model": "SanDisk Extreme SSD", "dl": "D:"},
        {"t": "o", "vidpid": "VID_0781&PID_558C", "inst": "MSFT3031383136",
         "fn": "Disp. almacenamiento SCSI por USB (UAS)", "cls": "SCSIAdapter"},
    ]
    state = _parse_live_data(data)
    ssd = [d for d in state["present_devices"]
           if d["product_id"] == "558C"][0]
    assert ssd["device_type"] == "almacenamiento"
    assert ssd["capacity"] == "232.9 GB"


def test_serial_corto_no_contamina_otros_dispositivos():
    """
    El serial de enumeracion corto del disco ('6') NO debe marcar como
    almacenamiento a otro PnP que comparta ese indice de instancia (p. ej. una
    camara cuyo 'inst' tambien es '6').
    """
    data = [
        {"t": "s", "serial": "6", "vidpid": "VID_0781&PID_558C",
         "inst": "MSFT3031383136", "sz": 250056737280,
         "model": "SanDisk Extreme SSD", "dl": "D:"},
        {"t": "o", "vidpid": "VID_04F2&PID_B76F", "inst": "6",
         "fn": "ACER HD User Facing", "cls": "Camera"},
    ]
    state = _parse_live_data(data)
    cam = [d for d in state["present_devices"]
           if d["product_id"] == "B76F"][0]
    assert cam["device_type"] == "camara"
    assert cam["capacity"] == ""


def test_pendrive_usb_clasico_por_serial():
    """Un pendrive USB clasico se cruza por su serial real (largo)."""
    data = [
        {"t": "s", "serial": "AA11223344556677", "vidpid": "VID_1234&PID_5678",
         "inst": "", "sz": 16000000000, "model": "USB DISK", "dl": "E:"},
        {"t": "o", "vidpid": "VID_1234&PID_5678", "inst": "AA11223344556677",
         "fn": "USB DISK 3.0", "cls": "DiskDrive"},
    ]
    state = _parse_live_data(data)
    pen = state["present_devices"][0]
    assert pen["device_type"] == "almacenamiento"
    assert pen["capacity"].endswith("GB")
