"""
Tests del motor de anomalias: rango del score, componentes, modo degradado,
persistencia y conversion a severidad.
"""

from datetime import datetime, timedelta

from analytics.anomaly_detector import (
    AnomalyDetector, severity_from_score, reason_from_components,
)


def _make_sessions(n_days=7, hours=(9, 11, 16), serial="SN_NORMAL"):
    """Genera sesiones normales en horario laboral."""
    now = datetime.now()
    sessions = []
    for d in range(n_days):
        for h in hours:
            t = (now - timedelta(days=d)).replace(
                hour=h, minute=0, second=0, microsecond=0)
            sessions.append({
                "serial": serial,
                "connected": t.strftime("%Y-%m-%d %H:%M:%S"),
                "disconnected": (t + timedelta(minutes=20)).strftime(
                    "%Y-%m-%d %H:%M:%S"),
            })
    return sessions


def test_score_siempre_en_rango():
    det = AnomalyDetector()
    det.train(_make_sessions(), train_days=30)
    for serial in ("SN_NORMAL", "SN_RARO"):
        for hour in (3, 10, 23):
            r = det.score({
                "serial": serial,
                "connected": f"2026-05-10 {hour:02d}:00:00",
                "disconnected": f"2026-05-10 {hour:02d}:30:00",
            })
            assert 0.0 <= r["score"] <= 1.0
            assert set(r["components"]) == {
                "hour_rarity", "device_rarity", "mahalanobis"}


def test_modo_degradado_con_pocos_datos():
    det = AnomalyDetector()
    ok = det.train(_make_sessions(n_days=1, hours=(9,)), train_days=30)
    assert ok is False
    assert det.is_degraded() is True


def test_entrena_con_datos_suficientes():
    det = AnomalyDetector()
    ok = det.train(_make_sessions(), train_days=30)
    assert ok is True
    assert det.is_trained() is True
    assert det.is_degraded() is False


def test_dispositivo_desconocido_puntua_mas():
    det = AnomalyDetector()
    det.train(_make_sessions(), train_days=30)
    conocido = det.score({"serial": "SN_NORMAL",
                          "connected": "2026-05-10 10:00:00",
                          "disconnected": "2026-05-10 10:20:00"})
    nuevo = det.score({"serial": "SN_JAMAS_VISTO",
                       "connected": "2026-05-10 10:00:00",
                       "disconnected": "2026-05-10 10:20:00"})
    assert nuevo["components"]["device_rarity"] >= \
        conocido["components"]["device_rarity"]


def test_persistencia_roundtrip():
    det = AnomalyDetector()
    det.train(_make_sessions(), train_days=30)
    sesion = {"serial": "SN_NORMAL",
              "connected": "2026-05-10 03:00:00",
              "disconnected": "2026-05-10 04:00:00"}
    antes = det.score(sesion)["score"]
    payload = det.to_payload()
    det2 = AnomalyDetector.from_payload(payload)
    despues = det2.score(sesion)["score"]
    assert abs(antes - despues) < 1e-9


def test_severity_from_score():
    # Por debajo del umbral de alerta -> no genera alerta
    assert severity_from_score(0.5, 0.6) is None
    # Bandas fijas por score: baja <0,5; media [0,5; 0,75]; alta >0,75
    assert severity_from_score(0.49, 0.4) == "baja"
    assert severity_from_score(0.5, 0.4) == "media"
    assert severity_from_score(0.68, 0.4) == "media"
    assert severity_from_score(0.75, 0.4) == "media"
    assert severity_from_score(0.76, 0.4) == "alta"
    assert severity_from_score(0.9, 0.4) == "alta"


def test_reason_from_components():
    msg = reason_from_components(
        {"hour_rarity": 0.9, "device_rarity": 0.1, "mahalanobis": 0.0})
    assert "hora" in msg.lower()
