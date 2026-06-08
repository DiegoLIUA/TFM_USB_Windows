"""
Tests del reentreno inteligente del detector y de la validacion experimental.
"""

from datetime import datetime, timedelta

from analytics import validation
from analytics.pipeline import load_or_train_detector, _RETRAIN_SESSION_DELTA
from store.database import upsert_device, insert_session, get_connection


def _seed_sessions(n: int) -> None:
    did = upsert_device({
        "vendor_id": "0001", "product_id": "0001", "serial": "S_VAL",
        "friendly_name": "X", "device_type": "almacenamiento",
        "first_seen": "2026-05-01 09:00:00", "last_seen": "2026-05-01 09:00:00",
    })
    now = datetime.now()
    for i in range(n):
        t = (now - timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
        insert_session({"device_id": did, "connected": t,
                        "disconnected": t, "drive_letter": "D:"})


def _model_count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) c FROM model_state").fetchone()["c"]


def test_reutiliza_modelo_sin_cambios(temp_db):
    _seed_sessions(8)
    load_or_train_detector()        # entrena (1)
    load_or_train_detector()        # reutiliza (sigue 1)
    assert _model_count() == 1


def test_reentrena_con_muchas_sesiones_nuevas(temp_db):
    _seed_sessions(8)
    load_or_train_detector()
    _seed_sessions(_RETRAIN_SESSION_DELTA + 1)
    load_or_train_detector()        # reentrena (2)
    assert _model_count() == 2


def test_force_retrain_siempre_entrena(temp_db):
    _seed_sessions(8)
    load_or_train_detector(force_retrain=True)
    load_or_train_detector(force_retrain=True)
    assert _model_count() == 2


def test_validation_metricas_en_rango():
    r = validation.evaluate(threshold=0.6)
    for key in ("precision", "recall", "f1", "accuracy"):
        assert 0.0 <= r[key] <= 1.0
    c = r["confusion"]
    assert c["tp"] + c["fp"] + c["tn"] + c["fn"] == 45


def test_validation_recall_alto_umbral_bajo():
    # Con umbral bajo el detector deberia capturar todas las anomalias
    r = validation.evaluate(threshold=0.4)
    assert r["recall"] >= 0.9
