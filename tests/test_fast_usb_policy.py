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


def _mock_estado_ssd(monkeypatch):
    """Configura el doble del sistema: C: ya estaba; D: (SSD FIXED) es nuevo."""
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


def test_disco_fixed_nuevo_se_detecta(temp_db, monkeypatch):
    """
    Una unidad FIXED nueva (SSD externo) que no estaba al inicio debe detectarse
    como insercion. Las ya presentes al arrancar (en known_drives) no reaccionan.
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
    _mock_estado_ssd(monkeypatch)

    # known_drives = lo presente al arrancar (solo C:). D: es nuevo.
    result = mc.run_fast_usb_check({"C:"})
    assert result["new_drives"] == ["D:"]
    assert "D:" in result["current_drives"] and "C:" in result["current_drives"]


def test_zero_trust_no_bloquea_en_monitorizacion(temp_db, monkeypatch):
    """La politica Zero Trust (bloqueo) es exclusiva del modo estricto."""
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
    _mock_estado_ssd(monkeypatch)

    result = mc.run_fast_usb_check({"C:"})
    assert result["blocks"] == []  # en monitorizacion no hay bloqueo por politica


def test_zero_trust_bloquea_en_estricto(temp_db, monkeypatch):
    """En estricto, un dispositivo no confiable nuevo genera bloqueo por politica."""
    from store.database import upsert_device
    from store.anomaly_store import set_config
    from security import schedule
    upsert_device({"vendor_id": "0781", "product_id": "558C",
                   "serial": "SSDSERIAL123456", "friendly_name": "SSD Externo",
                   "device_type": "almacenamiento",
                   "first_seen": "2026-06-01 10:00:00",
                   "last_seen": "2026-06-01 10:00:00"})
    set_config("anomaly.mode", "estricto")
    set_config("prevention.physical_block", "false")  # sin admin: bloqueo logico
    schedule.set_schedule("10:00", "15:00", list(range(7)), margin_h=0)
    _mock_estado_ssd(monkeypatch)

    result = mc.run_fast_usb_check({"C:"})
    assert len(result["blocks"]) == 1
    assert result["blocks"][0]["serial"] == "SSDSERIAL123456"


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


# --- Puntuacion de sesion cerrada por el motor (alerta con desglose gradual) --

def test_sesion_cerrada_genera_alerta_del_motor(temp_db, monkeypatch):
    """
    Al cerrar una sesion en monitorizacion, el motor la puntua y, si supera el
    umbral, genera alerta con desglose real (no la regla binaria de Zero Trust).
    """
    from store.database import upsert_device
    from store.anomaly_store import set_config, get_alerts
    set_config("anomaly.mode", "monitorizacion")
    set_config("anomaly.threshold", "0.3")
    upsert_device({"vendor_id": "0781", "product_id": "558C",
                   "serial": "SN_DISCO", "friendly_name": "Disco",
                   "device_type": "almacenamiento",
                   "first_seen": "2026-06-01 03:00:00",
                   "last_seen": "2026-06-01 03:00:00"})

    # Detector que devuelve un score alto con desglose gradual (no binario).
    class _FakeDetector:
        def score(self, session):
            return {"score": 0.8,
                    "components": {"hour_rarity": 0.9, "device_rarity": 0.4,
                                   "mahalanobis": 0.2}}
    import monitoring.monitor_cycle as mcyc
    monkeypatch.setattr(mcyc, "load_or_train_detector",
                        lambda: _FakeDetector(), raising=False)
    import analytics.pipeline as pl
    monkeypatch.setattr(pl, "load_or_train_detector", lambda: _FakeDetector())

    # session_id None evita la restriccion FK (en produccion la sesion existe
    # porque la acaba de cerrar close_drive_session).
    from store.database import get_all_devices
    closed = {"id": None, "device_id": get_all_devices()[0]["id"],
              "connected": "2026-06-09 03:00:00",
              "disconnected": "2026-06-09 03:30:00"}

    mc._score_closed_session(closed)
    alerts = get_alerts()
    assert len(alerts) == 1
    import json
    comp = json.loads(alerts[0]["components"])
    # Desglose gradual del motor, no la regla binaria 1.0/0.0
    assert comp["device_rarity"] == 0.4
    assert alerts[0]["severity"] == "alta"  # 0.8 > 0.75


def test_sesion_cerrada_no_alerta_en_aprendizaje(temp_db, monkeypatch):
    """En modo aprendizaje no se generan alertas al cerrar sesiones."""
    from store.anomaly_store import set_config, get_alerts
    set_config("anomaly.mode", "aprendizaje")
    closed = {"id": 1, "device_id": 1, "connected": "2026-06-09 03:00:00",
              "disconnected": "2026-06-09 03:30:00"}
    mc._score_closed_session(closed)
    assert get_alerts() == []
