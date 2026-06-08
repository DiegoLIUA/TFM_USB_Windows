"""
Tests del chequeo rapido de almacenamiento y su integracion con la politica
Zero Trust. Cubren la deteccion de discos externos que el sistema presenta como
FIXED (SSD/HDD por adaptador UAS) y la resolucion del dispositivo por letra de
unidad. Las funciones de adquisicion (WinAPI/PowerShell) se sustituyen por
dobles para no depender del hardware.
"""

import monitoring.monitor_cycle as mc


def test_resolve_por_letra_usa_estado_en_vivo(temp_db, monkeypatch):
    """El dispositivo de una unidad se resuelve por su letra, no por el primero."""
    from store.database import upsert_device
    upsert_device({"vendor_id": "0781", "product_id": "558C",
                   "serial": "SSDSERIAL123456", "friendly_name": "SSD Externo",
                   "device_type": "almacenamiento",
                   "first_seen": "2026-06-01 10:00:00",
                   "last_seen": "2026-06-01 10:00:00"})
    # Otro almacenamiento mas reciente, para comprobar que NO se elige por orden
    upsert_device({"vendor_id": "1111", "product_id": "2222",
                   "serial": "OTROPENDRIVE99", "friendly_name": "Pendrive viejo",
                   "device_type": "almacenamiento",
                   "first_seen": "2026-06-07 10:00:00",
                   "last_seen": "2026-06-07 10:00:00"})
    # _resolve_drive_device importa get_live_usb_state desde acquisition.live_state.
    import acquisition.live_state as ls
    monkeypatch.setattr(ls, "get_live_usb_state", lambda: {
        "drive_letter": {"SSDSERIAL123456": "D:"},
        "capacity": {"SSDSERIAL123456": "232.9 GB"},
        "present_devices": [],
    })
    dev = mc._resolve_drive_device("D:")
    assert dev["serial"] == "SSDSERIAL123456"
    assert dev["friendly_name"] == "SSD Externo"


def test_disco_fixed_nuevo_dispara_politica(temp_db, monkeypatch):
    """
    Una unidad FIXED nueva (SSD externo) que no estaba al inicio debe tratarse
    como insercion: en modo estricto genera bloqueo. Las ya presentes al
    arrancar (en known_drives) no reaccionan.
    """
    from store.database import upsert_device
    from store.anomaly_store import set_config
    from security import schedule
    upsert_device({"vendor_id": "0781", "product_id": "558C",
                   "serial": "SSDSERIAL123456", "friendly_name": "SSD Externo",
                   "device_type": "almacenamiento",
                   "first_seen": "2026-06-01 10:00:00",
                   "last_seen": "2026-06-01 10:00:00"})
    set_config("anomaly.mode", "monitorizacion")
    schedule.set_schedule("10:00", "15:00", list(range(7)), margin_h=0)

    # Doble del estado del sistema: C: ya estaba; D: (SSD FIXED) es nuevo.
    import acquisition.fast_usb as fu
    monkeypatch.setattr(fu, "get_storage_drives", lambda: {
        "C:": {"label": "", "volume_serial": "1", "removable": "0"},
        "D:": {"label": "Extreme SSD", "volume_serial": "2", "removable": "0"},
    })
    import acquisition.live_state as ls
    monkeypatch.setattr(ls, "get_live_usb_state", lambda: {
        "drive_letter": {"SSDSERIAL123456": "D:"},
        "capacity": {"SSDSERIAL123456": "232.9 GB"},
        "present_devices": [],
    })

    # known_drives = lo presente al arrancar (solo C:). D: es nuevo.
    result = mc.run_fast_usb_check({"C:"})
    assert result["new_drives"] == ["D:"]
    assert "D:" in result["current_drives"] and "C:" in result["current_drives"]


def test_disco_ya_presente_no_reacciona(temp_db, monkeypatch):
    """Un disco fijo ya conocido (en known_drives) no genera deteccion nueva."""
    import acquisition.fast_usb as fu
    monkeypatch.setattr(fu, "get_storage_drives", lambda: {
        "C:": {"label": "", "volume_serial": "1", "removable": "0"},
        "D:": {"label": "Datos", "volume_serial": "2", "removable": "0"},
    })
    # Ambas ya estaban al arrancar -> sin novedades.
    result = mc.run_fast_usb_check({"C:", "D:"})
    assert result["new_drives"] == []
    assert result["blocks"] == []
