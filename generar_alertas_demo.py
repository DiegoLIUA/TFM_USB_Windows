"""
Genera alertas variadas de demostracion para poblar la pestana de Alertas
(util para capturas de pantalla de la memoria).

Entrena el detector con un comportamiento normal sintetico y luego puntua varias
sesiones anomalas de distinto tipo, de modo que las alertas resultantes tengan
severidades (baja/media/alta), scores y desgloses por componentes DISTINTOS y
REALES (calculados por el motor, no inventados).

Uso:
    python generar_alertas_demo.py          # inserta las alertas demo
    python generar_alertas_demo.py --limpiar # borra las alertas demo

Las alertas demo se marcan con el prefijo "[DEMO]" en el motivo, por lo que se
pueden borrar sin tocar las alertas reales.
"""

import json
import sys
from datetime import datetime, timedelta

from store.database import initialize_database, get_connection, upsert_device
from store.anomaly_store import insert_alert
from analytics.anomaly_detector import (
    AnomalyDetector, severity_from_score, reason_from_components,
)

_DEMO_TAG = "[DEMO]"
_THRESHOLD = 0.5  # umbral bajo para que las anomalias sutiles tambien alerten


def _train_detector() -> AnomalyDetector:
    """Entrena con un comportamiento normal: USB conocido, horario laboral,
    sesiones cortas (~20 min)."""
    base = datetime.now()
    sessions = []
    for d in range(21):
        for h in (9, 11, 14, 16):
            t = (base - timedelta(days=d)).replace(
                hour=h, minute=0, second=0, microsecond=0)
            sessions.append({
                "serial": "USB_TRABAJO",
                "connected": t.strftime("%Y-%m-%d %H:%M:%S"),
                "disconnected": (t + timedelta(minutes=20)).strftime(
                    "%Y-%m-%d %H:%M:%S"),
            })
    det = AnomalyDetector()
    det.train(sessions, train_days=30)
    return det


def _demo_sessions():
    """Sesiones anomalas de distinto tipo (serial, connected, disconnected)."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return [
        # 1. USB conocido a hora de madrugada -> rareza temporal alta
        ("USB_TRABAJO", f"{hoy} 03:00:00", f"{hoy} 03:25:00"),
        # 2. USB nunca visto en horario normal -> dispositivo desconocido
        ("USB_INTRUSO_42", f"{hoy} 11:00:00", f"{hoy} 11:20:00"),
        # 3. USB conocido con sesion MUY larga -> mahalanobis alto (duracion)
        ("USB_TRABAJO", f"{ayer} 10:00:00", f"{ayer} 14:00:00"),
        # 4. USB desconocido + madrugada + sesion larga -> los 3 componentes
        ("USB_DESCONOCIDO_7", f"{hoy} 04:00:00", f"{hoy} 06:30:00"),
        # 5. USB nuevo a hora limite de la noche -> media (disp + algo de hora)
        ("USB_INTRUSO_99", f"{ayer} 23:00:00", f"{ayer} 23:30:00"),
    ]


def _ensure_devices():
    """Crea en BD los dispositivos demo para que la alerta muestre su nombre."""
    nombres = {
        "USB_TRABAJO": "Kingston DataTraveler [DEMO]",
        "USB_INTRUSO_42": "Pendrive desconocido [DEMO]",
        "USB_DESCONOCIDO_7": "SanDisk Cruzer [DEMO]",
        "USB_INTRUSO_99": "USB sin marca [DEMO]",
    }
    ids = {}
    for serial, nombre in nombres.items():
        ids[serial] = upsert_device({
            "vendor_id": "1234", "product_id": "5678", "serial": serial,
            "friendly_name": nombre, "device_type": "almacenamiento",
            "capacity": "16 GB",
            "first_seen": "2026-05-01 09:00:00",
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    return ids


def _demo_sessions_with_duration(ids) -> int:
    """
    Crea sesiones de almacenamiento con desconexion registrada, para poblar la
    grafica de duracion media. Devuelve cuantas sesiones se insertaron.
    """
    from store.database import insert_session
    # (serial, [duraciones_en_minutos de cada sesion])
    planes = {
        "USB_TRABAJO": [20, 25, 30, 18, 22],       # uso corto frecuente
        "USB_INTRUSO_42": [90, 120, 75],            # sesiones largas
        "USB_DESCONOCIDO_7": [45, 60, 50, 55],      # uso medio
    }
    base = datetime.now() - timedelta(days=10)
    n = 0
    for serial, durs in planes.items():
        dev_id = ids.get(serial)
        for i, d in enumerate(durs):
            t = base + timedelta(days=i, hours=10)
            insert_session({
                "device_id": dev_id,
                "connected": t.strftime("%Y-%m-%d %H:%M:%S"),
                "disconnected": (t + timedelta(minutes=d)).strftime(
                    "%Y-%m-%d %H:%M:%S"),
                "drive_letter": "D:",
            })
            n += 1
    return n


def generar() -> None:
    initialize_database()
    det = _train_detector()
    ids = _ensure_devices()
    n_sesiones = _demo_sessions_with_duration(ids)
    print(f"{n_sesiones} sesiones demo con duración generadas "
          "(grafica de duracion media).")
    creadas = 0
    for serial, conn, disc in _demo_sessions():
        session = {"serial": serial, "connected": conn, "disconnected": disc}
        result = det.score(session)
        sev = severity_from_score(result["score"], _THRESHOLD)
        if not sev:
            sev = "baja"  # forzar que aparezca para la demo
        comp = result["components"]
        reason = f"{_DEMO_TAG} {reason_from_components(comp)}"
        insert_alert({
            "device_id": ids.get(serial),
            "session_id": None,
            "severity": sev,
            "score": result["score"],
            "reason": reason,
            "components": json.dumps(comp),
        })
        creadas += 1
        print(f"  [{sev:<5}] score={result['score']:.2f}  {serial:<18} "
              f"hora={comp['hour_rarity']:.2f} disp={comp['device_rarity']:.2f} "
              f"maha={comp['mahalanobis']:.2f}")
    print(f"\n{creadas} alertas demo generadas. Abra la pestana «Alertas».")


def limpiar() -> None:
    initialize_database()
    with get_connection() as conn:
        # Borra alertas demo
        cur = conn.execute(
            "DELETE FROM alerts WHERE reason LIKE ?", (f"{_DEMO_TAG}%",))
        n_alertas = cur.rowcount
        # Borra sesiones y dispositivos demo (nombre con [DEMO])
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM devices WHERE friendly_name LIKE ?",
            ("%[DEMO]%",)).fetchall()]
        n_ses = 0
        for did in ids:
            n_ses += conn.execute(
                "DELETE FROM sessions WHERE device_id = ?", (did,)).rowcount
        conn.execute("DELETE FROM devices WHERE friendly_name LIKE ?",
                     ("%[DEMO]%",))
        conn.commit()
        print(f"{n_alertas} alertas, {n_ses} sesiones y {len(ids)} "
              "dispositivos demo eliminados.")


if __name__ == "__main__":
    if "--limpiar" in sys.argv:
        limpiar()
    else:
        generar()
