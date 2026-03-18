"""
Gestión de la base de datos SQLite.
Proporciona conexión, inicialización y operaciones CRUD básicas.
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from store.models import ALL_TABLES

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "tfm_usb.db"


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


def insert_event(event: Dict[str, Any]) -> None:
    sql = """
    INSERT INTO events (device_id, session_id, event_type, timestamp, source, raw)
    VALUES (:device_id, :session_id, :event_type, :timestamp, :source, :raw)
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


def clear_devices() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM devices")
        conn.commit()
