"""
Tests de persistencia: allowlist (trusted), upsert con MIN/MAX de fechas
y agregaciones de estadisticas.
"""

from store.database import (
    upsert_device, get_all_devices, set_device_trusted, get_trusted_serials,
)
from store.signals_store import insert_signal, insert_signals, get_signals


def _device(serial, **kw):
    base = {"vendor_id": "0001", "product_id": "0002", "serial": serial,
            "friendly_name": "Test", "device_type": "almacenamiento",
            "first_seen": "2026-05-01 10:00:00",
            "last_seen": "2026-05-01 10:00:00"}
    base.update(kw)
    return base


def test_allowlist_marca_y_consulta(temp_db):
    upsert_device(_device("SN_A"))
    upsert_device(_device("SN_B"))
    assert get_trusted_serials() == set()
    set_device_trusted("SN_A", True)
    assert get_trusted_serials() == {"SN_A"}
    set_device_trusted("SN_A", False)
    assert get_trusted_serials() == set()


def test_upsert_preserva_first_seen_y_actualiza_last(temp_db):
    upsert_device(_device("SN_X", first_seen="2026-05-01 10:00:00",
                          last_seen="2026-05-01 10:00:00"))
    upsert_device(_device("SN_X", first_seen="2026-05-10 09:00:00",
                          last_seen="2026-05-10 09:00:00"))
    dev = next(d for d in get_all_devices() if d["serial"] == "SN_X")
    # first_seen = el mas antiguo, last_seen = el mas reciente
    assert dev["first_seen"] == "2026-05-01 10:00:00"
    assert dev["last_seen"] == "2026-05-10 09:00:00"


def test_signals_idempotentes(temp_db):
    sig = {"category": "power", "signal_type": "suspend",
           "timestamp": "2026-05-04 23:00:00", "detail": "x"}
    assert insert_signal(sig) is True
    assert insert_signal(sig) is False  # duplicado ignorado
    assert len(get_signals(category="power")) == 1


def test_signals_batch(temp_db):
    sigs = [
        {"category": "session", "signal_type": "logon",
         "timestamp": "2026-05-04 08:00:00", "detail": ""},
        {"category": "session", "signal_type": "logoff",
         "timestamp": "2026-05-04 18:00:00", "detail": ""},
    ]
    assert insert_signals(sigs) == 2
