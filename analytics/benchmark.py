"""
Medicion de rendimiento del sistema (RNF1 y RNF2).
- RNF1: el analisis de un ano de eventos debe completarse en < 30 s.
- RNF2: el tiempo de reaccion deteccion -> respuesta debe ser < 3 s.
Genera datos sinteticos a escala anual y mide tiempos reales sobre una BD
temporal aislada. Reproducible: no depende de artefactos del equipo.
"""

import os
import tempfile
import time
from datetime import datetime, timedelta
from typing import Dict, Any


def _setup_temp_db():
    """Apunta la BD a un fichero temporal e inicializa el esquema."""
    import store.database as database
    fd, path = tempfile.mkstemp(suffix=".db", prefix="bench_")
    os.close(fd)
    database.DB_PATH = path
    database.initialize_database()
    return path


def _seed_year_of_sessions(n_per_day: int = 3) -> int:
    """Inserta ~un ano de sesiones (varios dispositivos, horario laboral)."""
    from store.database import upsert_device, insert_session
    serials = ["USB_TRABAJO", "USB_BACKUP", "USB_PROYECTO"]
    ids = {}
    for s in serials:
        ids[s] = upsert_device({
            "vendor_id": "0001", "product_id": "0001", "serial": s,
            "friendly_name": s, "device_type": "almacenamiento",
            "first_seen": "2025-06-01 09:00:00",
            "last_seen": "2026-06-01 09:00:00",
        })
    base = datetime(2026, 6, 1, 12, 0, 0)
    total = 0
    for d in range(365):
        for k in range(n_per_day):
            serial = serials[(d + k) % len(serials)]
            t = (base - timedelta(days=d)).replace(
                hour=9 + (k * 3) % 9, minute=0, second=0, microsecond=0)
            insert_session({
                "device_id": ids[serial],
                "connected": t.strftime("%Y-%m-%d %H:%M:%S"),
                "disconnected": (t + timedelta(minutes=30)).strftime(
                    "%Y-%m-%d %H:%M:%S"),
                "drive_letter": "D:",
            })
            total += 1
    return total


def measure_rnf1() -> Dict[str, Any]:
    """Mide el tiempo de entrenar el modelo y puntuar un ano de sesiones."""
    from analytics.pipeline import _train_new
    from analytics.anomaly_detector import AnomalyDetector
    from store.anomaly_store import load_latest_model_state
    from store.database import get_connection

    t0 = time.perf_counter()
    detector = _train_new()                       # entrena con todo el historial
    train_s = time.perf_counter() - t0

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.*, d.serial FROM sessions s "
            "LEFT JOIN devices d ON s.device_id = d.id").fetchall()
    sessions = [dict(r) for r in rows]

    t1 = time.perf_counter()
    for s in sessions:
        detector.score(s)
    score_s = time.perf_counter() - t1

    total_s = train_s + score_s
    return {
        "n_sessions": len(sessions),
        "train_s": round(train_s, 3),
        "score_s": round(score_s, 3),
        "total_s": round(total_s, 3),
        "cumple_rnf1": total_s < 30.0,
    }


def measure_rnf2() -> Dict[str, Any]:
    """Mide el tiempo de reaccion: puntuar una sesion y registrar la alerta."""
    from analytics.pipeline import load_or_train_detector
    from analytics.anomaly_detector import severity_from_score, reason_from_components
    from store.anomaly_store import insert_alert, set_config
    import json

    set_config("anomaly.mode", "monitorizacion")
    set_config("anomaly.threshold", "0.5")
    detector = load_or_train_detector()

    sesion = {"serial": "USB_INTRUSO",
              "connected": "2026-06-01 03:00:00",
              "disconnected": "2026-06-01 04:30:00"}

    t0 = time.perf_counter()
    result = detector.score(sesion)
    severity = severity_from_score(result["score"], 0.5)
    if severity:
        insert_alert({
            "device_id": None, "session_id": None, "severity": severity,
            "score": result["score"],
            "reason": reason_from_components(result["components"]),
            "components": json.dumps(result["components"]),
        })
    react_s = time.perf_counter() - t0

    return {
        "reaccion_s": round(react_s, 4),
        "score": result["score"],
        "severity": severity,
        "cumple_rnf2": react_s < 3.0,
    }


def run() -> None:
    path = _setup_temp_db()
    try:
        n = _seed_year_of_sessions()
        print("=" * 56)
        print(" MEDICION DE RENDIMIENTO (RNF1 / RNF2)")
        print("=" * 56)
        print(f"\nSesiones generadas (1 ano): {n}")

        r1 = measure_rnf1()
        print("\n[RNF1] Analisis de un ano de eventos (< 30 s)")
        print(f"  Entrenamiento : {r1['train_s']} s")
        print(f"  Puntuacion    : {r1['score_s']} s ({r1['n_sessions']} sesiones)")
        print(f"  TOTAL         : {r1['total_s']} s")
        print(f"  Cumple RNF1   : {'SI' if r1['cumple_rnf1'] else 'NO'}")

        r2 = measure_rnf2()
        print("\n[RNF2] Reaccion deteccion -> respuesta (< 3 s)")
        print(f"  Tiempo        : {r2['reaccion_s']} s")
        print(f"  Score/severidad: {r2['score']} / {r2['severity']}")
        print(f"  Cumple RNF2   : {'SI' if r2['cumple_rnf2'] else 'NO'}")
        print("\n" + "=" * 56)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    run()
