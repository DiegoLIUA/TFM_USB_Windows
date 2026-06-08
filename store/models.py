"""
Definición del esquema de la base de datos SQLite.
Contiene las sentencias SQL de creación de tablas.
"""

SQL_CREATE_DEVICES = """
CREATE TABLE IF NOT EXISTS devices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id     TEXT,
    product_id    TEXT,
    serial        TEXT UNIQUE,
    friendly_name TEXT,
    device_type   TEXT DEFAULT 'almacenamiento',
    capacity      TEXT,
    first_seen    TEXT,
    last_seen     TEXT,
    trusted       INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now', 'localtime'))
);
"""

SQL_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id  INTEGER NOT NULL,
    connected  TEXT,
    disconnected TEXT,
    drive_letter TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);
"""

SQL_CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   INTEGER,
    session_id  INTEGER,
    event_type  TEXT,
    timestamp   TEXT,
    source      TEXT,
    raw         TEXT,
    hash_sha256 TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""

SQL_CREATE_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   INTEGER,
    session_id  INTEGER,
    severity    TEXT,
    score       REAL,
    reason      TEXT,
    components  TEXT,
    timestamp   TEXT DEFAULT (datetime('now', 'localtime')),
    acknowledged INTEGER DEFAULT 0,
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""

SQL_CREATE_CONFIG = """
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

SQL_CREATE_MODEL_STATE = """
CREATE TABLE IF NOT EXISTS model_state (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version    INTEGER,
    trained_at TEXT DEFAULT (datetime('now', 'localtime')),
    payload    TEXT
);
"""

SQL_CREATE_SYSTEM_SIGNALS = """
CREATE TABLE IF NOT EXISTS system_signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT,
    signal_type TEXT,
    timestamp   TEXT,
    detail      TEXT,
    hash_sha256 TEXT,
    UNIQUE(category, signal_type, timestamp, detail)
);
"""

ALL_TABLES = [
    SQL_CREATE_DEVICES,
    SQL_CREATE_SESSIONS,
    SQL_CREATE_EVENTS,
    SQL_CREATE_ALERTS,
    SQL_CREATE_CONFIG,
    SQL_CREATE_MODEL_STATE,
    SQL_CREATE_SYSTEM_SIGNALS,
]
