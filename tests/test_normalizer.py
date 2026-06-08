"""
Tests de normalizacion de dispositivos: formatos de fecha y deduplicacion.
"""

from normalization.normalizer import (
    normalize_timestamp, normalize_device, deduplicate_devices,
)


def test_normalize_timestamp_formatos():
    assert normalize_timestamp("2026-05-04 10:30:00") == "2026-05-04 10:30:00"
    assert normalize_timestamp("2026/05/04 10:30:00") == "2026-05-04 10:30:00"
    assert normalize_timestamp("04/05/2026 10:30:00") == "2026-05-04 10:30:00"
    assert normalize_timestamp(None) is None


def test_normalize_device_defaults():
    dev = normalize_device({"serial": "  ABC123 "})
    assert dev["serial"] == "ABC123"
    assert dev["device_type"] == "almacenamiento"
    assert dev["friendly_name"] == "Dispositivo USB"


def test_normalize_device_uppercase_ids():
    dev = normalize_device({"vendor_id": "0a1b", "product_id": "ffff",
                            "serial": "X"})
    assert dev["vendor_id"] == "0A1B"
    assert dev["product_id"] == "FFFF"


def test_deduplicate_conserva_mas_reciente():
    devs = [
        {"serial": "S1", "last_seen": "2026-01-01 00:00:00"},
        {"serial": "S1", "last_seen": "2026-05-01 00:00:00"},
        {"serial": "S2", "last_seen": "2026-03-01 00:00:00"},
    ]
    out = deduplicate_devices(devs)
    by_serial = {d["serial"]: d for d in out}
    assert len(out) == 2
    assert by_serial["S1"]["last_seen"] == "2026-05-01 00:00:00"
