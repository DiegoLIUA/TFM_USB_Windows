"""
Tests del calculo automatico de horario y del resumen de uso a partir de las
senales de actividad.
"""

from analytics.stats import compute_usual_schedule
from store.signals_store import insert_signal


_counter = [0]


def _activity(day: str, hour: int, kind: str = "active") -> None:
    # Timestamp unico (minuto:segundo crecientes) porque insert_signal deduplica
    # por (category, signal_type, timestamp, detail).
    _counter[0] += 1
    mm, ss = divmod(_counter[0] % 3600, 60)
    insert_signal({
        "category": "activity", "signal_type": kind,
        "timestamp": f"{day} {hour:02d}:{mm:02d}:{ss:02d}", "detail": "",
    })


def test_horario_sin_datos(temp_db):
    sch = compute_usual_schedule()
    assert sch["start"] is None
    assert sch["total_active"] == 0


def test_horario_franja_laboral(temp_db):
    # Actividad concentrada de 9 a 13 h durante varios dias
    for d in range(3):
        dia = f"2026-06-0{d + 1}"
        for h in (9, 10, 11, 12, 13):
            _activity(dia, h)
            _activity(dia, h)  # refuerza el peso
    sch = compute_usual_schedule()
    assert sch["start"] == "09:00"
    # La franja cierra al final de la ultima hora con uso (13 -> 14:00)
    assert sch["end"] == "14:00"
    assert set(sch["hours"]) >= {9, 10, 11, 12, 13}


def test_horario_descarta_ruido(temp_db):
    # Mucha actividad de 10-12 h y una sola muestra aislada a las 3 h
    for _ in range(20):
        _activity("2026-06-01", 10)
        _activity("2026-06-01", 11)
    _activity("2026-06-01", 3)  # ruido, por debajo del umbral
    sch = compute_usual_schedule(min_ratio=0.15)
    assert 3 not in sch["hours"]
    assert sch["start"] == "10:00"
