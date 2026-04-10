"""
Gestión de la base de datos SQLite.
Proporciona conexión, inicialización y operaciones CRUD básicas.
"""

import sqlite3
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from store.models import ALL_TABLES

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "tfm_usb.db"


def _compute_hash(data: str) -> str:
    """Calcula SHA-256 del contenido de un evento."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    with get_connection() as conn:
        for sql in ALL_TABLES:
            conn.execute(sql)
        conn.commit()
    logger.info("Base de datos inicializada en %s", DB_PATH)


def upsert_device(device: Dict[str, Any]) -> int:
    sql = """
    INSERT INTO devices (vendor_id, product_id, serial, friendly_name, first_seen, last_seen)
    VALUES (:vendor_id, :product_id, :serial, :friendly_name, :first_seen, :last_seen)
    ON CONFLICT(serial) DO UPDATE SET
        friendly_name = excluded.friendly_name,
        last_seen     = excluded.last_seen
    """
    with get_connection() as conn:
        cur = conn.execute(sql, device)
        conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM devices WHERE serial = ?", (device["serial"],)
        ).fetchone()
        return row["id"] if row else -1


def get_all_devices() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM devices ORDER BY last_seen DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def insert_session(session: Dict[str, Any]) -> int:
    """Inserta una sesion USB y devuelve su id."""
    sql = """
    INSERT INTO sessions (device_id, connected, disconnected, drive_letter)
    VALUES (:device_id, :connected, :disconnected, :drive_letter)
    """
    with get_connection() as conn:
        cur = conn.execute(sql, session)
        conn.commit()
        return cur.lastrowid


def insert_event(event: Dict[str, Any]) -> None:
    """Inserta un evento con hash SHA-256 de integridad."""
    raw = event.get("raw") or ""
    event["hash_sha256"] = _compute_hash(raw)
    sql = """
    INSERT INTO events (device_id, session_id, event_type, timestamp, source, raw, hash_sha256)
    VALUES (:device_id, :session_id, :event_type, :timestamp, :source, :raw, :hash_sha256)
    """
    with get_connection() as conn:
        conn.execute(sql, event)
        conn.commit()


def get_events_for_device(device_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE device_id = ? ORDER BY timestamp DESC",
            (device_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_sessions_for_device(device_id: int) -> List[Dict[str, Any]]:
    """Devuelve todas las sesiones de un dispositivo."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE device_id = ? ORDER BY connected DESC",
            (device_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_devices_filtered(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    serial_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Devuelve dispositivos filtrados por rango de fechas y/o serial."""
    clauses = []
    params: List[Any] = []
    if date_from:
        clauses.append("last_seen >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("first_seen <= ?")
        params.append(date_to)
    if serial_filter:
        clauses.append("(serial LIKE ? OR friendly_name LIKE ?)")
        params.extend([f"%{serial_filter}%", f"%{serial_filter}%"])

    where = " AND ".join(clauses)
    sql = "SELECT * FROM devices"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY last_seen DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_device_sources(device_id: int) -> str:
    """Devuelve las fuentes de datos que registraron un dispositivo."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT source FROM events WHERE device_id = ?",
            (device_id,),
        ).fetchall()
        sources = [r["source"] for r in rows]
        if "registro" not in sources:
            sources.append("registro")
        return ", ".join(sorted(set(sources)))


def clear_devices() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM devices")
        conn.commit()
