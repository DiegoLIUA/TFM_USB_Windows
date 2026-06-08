"""
Operaciones de BD para senales del sistema (power, session, app, idle).
Insercion idempotente: las senales duplicadas se ignoran (UNIQUE).
"""

import hashlib
from typing import List, Dict, Any, Optional

from store.database import get_connection


def _hash_signal(s: Dict[str, Any]) -> str:
    raw = f"{s.get('category')}|{s.get('signal_type')}|{s.get('timestamp')}|{s.get('detail')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def insert_signal(signal: Dict[str, Any]) -> bool:
    """Inserta una senal; devuelve True si era nueva, False si duplicada."""
    signal = dict(signal)
    signal.setdefault("detail", "")
    signal["hash_sha256"] = _hash_signal(signal)
    sql = """
    INSERT OR IGNORE INTO system_signals
        (category, signal_type, timestamp, detail, hash_sha256)
    VALUES (:category, :signal_type, :timestamp, :detail, :hash_sha256)
    """
    with get_connection() as conn:
        cur = conn.execute(sql, signal)
        conn.commit()
        return cur.rowcount > 0


def insert_signals(signals: List[Dict[str, Any]]) -> int:
    """Inserta una lista de senales; devuelve cuantas eran nuevas."""
    return sum(1 for s in signals if insert_signal(s))


def get_signals(
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Lista senales filtradas por categoria y rango de fechas."""
    clauses: List[str] = []
    params: List[Any] = []
    if category:
        clauses.append("category = ?"); params.append(category)
    if date_from:
        clauses.append("timestamp >= ?"); params.append(date_from)
    if date_to:
        clauses.append("timestamp <= ?"); params.append(date_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = ("SELECT * FROM system_signals" + where
           + " ORDER BY timestamp DESC LIMIT ?")
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def count_signals_by_category() -> Dict[str, int]:
    """Resumen: numero de senales por categoria."""
    sql = "SELECT category, COUNT(*) AS n FROM system_signals GROUP BY category"
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
        return {r["category"]: r["n"] for r in rows}
