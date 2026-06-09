"""
Tests de la duracion tipica de uso de almacenamiento
(stats.median_duration_top_storage): uso de la mediana (robusta a atipicos),
descarte de sesiones fugaces y de sesiones imposiblemente largas (errores de
registro).
"""

from datetime import datetime, timedelta

from analytics.stats import median_duration_top_storage, _mediana
from store.database import upsert_device, insert_session


def _device(serial, nombre):
    return upsert_device({
        "vendor_id": "1234", "product_id": "5678", "serial": serial,
        "friendly_name": nombre, "device_type": "almacenamiento",
        "first_seen": "2026-06-01 10:00:00", "last_seen": "2026-06-01 10:00:00",
    })


def _sesion(device_id, inicio: str, dur_min: float):
    ini = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
    fin = ini + timedelta(minutes=dur_min)
    insert_session({
        "device_id": device_id,
        "connected": inicio,
        "disconnected": fin.strftime("%Y-%m-%d %H:%M:%S"),
        "drive_letter": "E:",
    })


def test_mediana_funcion():
    assert _mediana([5]) == 5
    assert _mediana([1, 3]) == 2.0           # par: promedio de los centrales
    assert _mediana([1, 2, 3]) == 2          # impar: el central
    assert _mediana([10, 1, 5]) == 5          # ordena internamente


def test_usa_mediana_no_media(temp_db):
    # Tres sesiones: 10, 12, 200 min. Media=74, mediana=12 (robusta al atipico).
    did = _device("SN1", "Disco A")
    for i, d in enumerate((10, 12, 200)):
        _sesion(did, f"2026-06-0{i + 1} 10:00:00", d)
    data = dict(median_duration_top_storage())
    assert data["Disco A"] == 12.0


def test_descarta_sesiones_fugaces(temp_db):
    # Sesiones de 0 min no cuentan; solo la de 8 min.
    did = _device("SN2", "Disco B")
    _sesion(did, "2026-06-01 10:00:00", 0)
    _sesion(did, "2026-06-02 10:00:00", 8)
    data = dict(median_duration_top_storage())
    assert data["Disco B"] == 8.0


def test_descarta_sesiones_imposiblemente_largas(temp_db):
    # Una sesion de 25 h (error de registro) se descarta; queda la de 31 min.
    did = _device("SN3", "Disco C")
    _sesion(did, "2026-06-01 10:00:00", 25 * 60)   # 1500 min -> descartada
    _sesion(did, "2026-06-02 10:00:00", 31)
    data = dict(median_duration_top_storage())
    assert data["Disco C"] == 31.0


def test_dispositivo_sin_sesiones_validas_no_aparece(temp_db):
    # Solo tiene una sesion de 30 h: se descarta y el dispositivo no figura.
    did = _device("SN4", "Disco D")
    _sesion(did, "2026-06-01 10:00:00", 30 * 60)
    data = dict(median_duration_top_storage())
    assert "Disco D" not in data
