"""
Tests del recalculo de severidad de alertas ya guardadas
(anomaly_store.recompute_alert_severities), que reasigna la banda fija por score
a las alertas historicas sin crearlas ni borrarlas.
"""

from store.anomaly_store import (
    insert_alert, get_alerts, recompute_alert_severities,
)


def _insert(score, severity):
    insert_alert({"device_id": None, "session_id": None, "severity": severity,
                  "score": score, "reason": "x", "components": "{}"})


def test_recompute_corrige_bandas(temp_db):
    # Alertas guardadas con severidad incorrecta respecto a la banda fija
    _insert(0.67, "baja")    # deberia ser media
    _insert(0.80, "media")   # deberia ser alta
    _insert(0.40, "baja")    # ya correcta
    _insert(0.60, "media")   # ya correcta
    n = recompute_alert_severities()
    assert n == 2  # solo cambian las dos primeras

    por_score = {round(a["score"], 2): a["severity"] for a in get_alerts()}
    assert por_score[0.67] == "media"
    assert por_score[0.80] == "alta"
    assert por_score[0.40] == "baja"
    assert por_score[0.60] == "media"


def test_recompute_idempotente(temp_db):
    _insert(0.67, "baja")
    recompute_alert_severities()
    # Una segunda pasada no cambia nada (ya estan coherentes)
    assert recompute_alert_severities() == 0


def test_recompute_respeta_limites_de_banda(temp_db):
    _insert(0.75, "alta")    # 0.75 NO es >0.75 -> media
    _insert(0.50, "baja")    # 0.50 es el limite inferior de media
    recompute_alert_severities()
    por_score = {round(a["score"], 2): a["severity"] for a in get_alerts()}
    assert por_score[0.75] == "media"
    assert por_score[0.50] == "media"
