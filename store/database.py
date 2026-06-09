"""
Gestión de la base de datos SQLite.
Proporciona conexión, inicialización y operaciones CRUD básicas.
"""

import sqlite3
import hashlib
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator

from store.models import ALL_TABLES

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "tfm_usb.db"


def _compute_hash(data: str) -> str:
    """Calcula SHA-256 del contenido de un evento."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    Conexion a la BD como gestor de contexto. A diferencia del 'with' nativo de
    sqlite3 (que solo gestiona la transaccion pero deja la conexion abierta),
    este SIEMPRE cierra la conexion al salir, evitando fugas de recursos en la
    ejecucion prolongada del monitor. Hace commit si no hubo excepcion y
    rollback si la hubo.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Columnas anadidas en versiones posteriores: (tabla, columna, definicion SQL).
# Se aplican con ALTER TABLE sobre bases de datos ya existentes para no perder
# datos al evolucionar el esquema.
_MIGRATIONS = [
    ("devices", "capacity", "TEXT"),
]


def _apply_migrations(conn) -> None:
    """Anade columnas que falten en una BD preexistente, sin borrar datos."""
    for table, column, coltype in _MIGRATIONS:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            logger.info("Migracion: anadida columna %s.%s", table, column)


def initialize_database() -> None:
    with get_connection() as conn:
        for sql in ALL_TABLES:
            conn.execute(sql)
        _apply_migrations(conn)
        conn.commit()
    logger.info("Base de datos inicializada en %s", DB_PATH)


def upsert_device(device: Dict[str, Any]) -> int:
    device = dict(device)
    device.setdefault("capacity", "")
    sql = """
    INSERT INTO devices (vendor_id, product_id, serial, friendly_name, device_type, capacity, first_seen, last_seen)
    VALUES (:vendor_id, :product_id, :serial, :friendly_name, :device_type, :capacity, :first_seen, :last_seen)
    ON CONFLICT(serial) DO UPDATE SET
        friendly_name = excluded.friendly_name,
        device_type   = excluded.device_type,
        capacity      = COALESCE(NULLIF(excluded.capacity, ''), devices.capacity),
        first_seen    = MIN(COALESCE(devices.first_seen, excluded.first_seen),
                           COALESCE(excluded.first_seen, devices.first_seen)),
        last_seen     = MAX(COALESCE(devices.last_seen, excluded.last_seen),
                           COALESCE(excluded.last_seen, devices.last_seen))
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


def open_drive_session(device_id, drive_letter: str, connected: str) -> int:
    """Abre una sesion (sin desconexion) para una unidad recien montada."""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (device_id, connected, disconnected, "
            "drive_letter) VALUES (?, ?, NULL, ?)",
            (device_id, connected, drive_letter),
        )
        conn.commit()
        return cur.lastrowid


def close_drive_session(drive_letter: str, disconnected: str) -> Optional[Dict[str, Any]]:
    """
    Cierra la sesion abierta mas reciente de una unidad (la que no tiene
    desconexion), registrando la hora de desconexion. Devuelve el registro de la
    sesion cerrada (id, device_id, connected, disconnected, drive_letter) o None
    si no habia ninguna abierta.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, device_id, connected, drive_letter FROM sessions "
            "WHERE drive_letter = ? AND disconnected IS NULL "
            "ORDER BY connected DESC LIMIT 1",
            (drive_letter,),
        ).fetchone()
        if not row:
            return None
        conn.execute("UPDATE sessions SET disconnected = ? WHERE id = ?",
                     (disconnected, row["id"]))
        conn.commit()
        return {"id": row["id"], "device_id": row["device_id"],
                "connected": row["connected"], "disconnected": disconnected,
                "drive_letter": row["drive_letter"]}


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


def set_device_trusted(serial: str, trusted: bool) -> None:
    """Marca o desmarca un dispositivo como de confianza (allowlist)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE devices SET trusted = ? WHERE serial = ?",
            (1 if trusted else 0, serial),
        )
        conn.commit()


def get_trusted_serials() -> set:
    """Devuelve el conjunto de seriales marcados como de confianza."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT serial FROM devices WHERE trusted = 1"
        ).fetchall()
        return {r["serial"] for r in rows}


def get_device_by_serial(serial: str) -> Optional[Dict[str, Any]]:
    """Devuelve el dispositivo con ese serial, o None si no existe."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM devices WHERE serial = ?", (serial,)
        ).fetchone()
        return dict(row) if row else None
