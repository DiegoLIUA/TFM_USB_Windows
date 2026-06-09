"""
Operaciones de BD para configuracion, alertas y estado del modelo de anomalias.
"""

from typing import List, Dict, Any, Optional

from store.database import get_connection

_DEFAULT_CONFIG = {
    "anomaly.threshold":   "0.6",
    "anomaly.train_days":  "7",
    "anomaly.mode":        "aprendizaje",
    "monitor.enabled":     "false",
    "monitor.interval_s":  "30",
    "schedule.start":      "08:00",
    "schedule.end":        "22:00",
    "schedule.days":       "0,1,2,3,4",
    "schedule.margin_h":   "2",
    "schedule.enforce":    "false",
    "totp.secret":         "",
    "totp.verified":       "false",
    "prevention.physical_block": "false",
    "ui.view":             "basico",
}


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """Devuelve un valor de configuracion o el default."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        ).fetchone()
        if row:
            return row["value"]
    return default if default is not None else _DEFAULT_CONFIG.get(key)


def set_config(key: str, value: str) -> None:
    sql = """
    INSERT INTO config (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """
    with get_connection() as conn:
        conn.execute(sql, (key, value))
        conn.commit()


def insert_alert(alert: Dict[str, Any]) -> int:
    from datetime import datetime
    alert = dict(alert)
    alert.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    sql = """
    INSERT INTO alerts (device_id, session_id, severity, score, reason, components, timestamp)
    VALUES (:device_id, :session_id, :severity, :score, :reason, :components, :timestamp)
    """
    with get_connection() as conn:
        cur = conn.execute(sql, alert)
        conn.commit()
        return cur.lastrowid


def get_alerts(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    device_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Lista alertas con join a devices para incluir nombre y serial."""
    clauses: List[str] = []
    params: List[Any] = []
    if date_from:
        clauses.append("a.timestamp >= ?"); params.append(date_from)
    if date_to:
        clauses.append("a.timestamp <= ?"); params.append(date_to)
    if device_id:
        clauses.append("a.device_id = ?"); params.append(device_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT a.*, d.friendly_name, d.serial "
        "FROM alerts a LEFT JOIN devices d ON a.device_id = d.id"
        + where + " ORDER BY a.timestamp DESC"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def recompute_alert_severities() -> int:
    """
    Recalcula la severidad de todas las alertas ya guardadas segun las bandas
    fijas por score (alta >0,75; media [0,5; 0,75]; baja en el resto). Util tras
    cambiar el criterio de severidad, para que las alertas historicas sean
    coherentes con las nuevas. No crea ni borra alertas: solo actualiza la
    columna 'severity' de las que cambian. Devuelve cuantas se actualizaron.

    El umbral de alerta no se reaplica aqui: se respeta que la alerta ya existe
    (en su momento supero el umbral vigente); solo se reasigna su banda. Para el
    calculo de banda se usa un umbral 0 para que severity_from_score nunca
    devuelva None sobre una alerta que ya fue emitida.
    """
    from analytics.anomaly_detector import severity_from_score
    actualizadas = 0
    with get_connection() as conn:
        rows = conn.execute("SELECT id, score, severity FROM alerts").fetchall()
        for r in rows:
            nueva = severity_from_score(float(r["score"] or 0.0), 0.0)
            if nueva and nueva != r["severity"]:
                conn.execute("UPDATE alerts SET severity = ? WHERE id = ?",
                             (nueva, r["id"]))
                actualizadas += 1
        conn.commit()
    return actualizadas


def get_all_sessions() -> List[Dict[str, Any]]:
    """Devuelve todas las sesiones con datos del dispositivo."""
    sql = (
        "SELECT s.*, d.serial, d.friendly_name "
        "FROM sessions s LEFT JOIN devices d ON s.device_id = d.id "
        "ORDER BY s.connected ASC"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def save_model_state(version: int, payload: str) -> None:
    """Guarda el estado serializado del modelo (JSON)."""
    sql = "INSERT INTO model_state (version, payload) VALUES (?, ?)"
    with get_connection() as conn:
        conn.execute(sql, (version, payload))
        conn.commit()


def load_latest_model_state() -> Optional[Dict[str, Any]]:
    """Recupera el estado de modelo mas reciente."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM model_state ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
