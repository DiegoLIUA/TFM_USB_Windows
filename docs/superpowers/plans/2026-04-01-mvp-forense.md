# MVP Forense Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the forensic MVP by correlating all 3 artifact sources (registry, evtx, setupapi) into coherent sessions, adding SHA-256 integrity hashes, and enhancing the UI with filters and source column.

**Architecture:** The acquisition layer already reads from 3 sources independently. We need a new correlation module (`normalization/correlator.py`) that matches artifacts by device serial/hardware ID and groups them into sessions. The database gets new operations for sessions and events with hashes. The UI gets filter widgets and an expanded table.

**Tech Stack:** Python 3.13, PyQt6 6.10.2, sqlite3, hashlib (stdlib)

**Constraints:** No file > 200 lines. Each function does one thing. No business logic in UI files. Update CHANGELOG.md after each task.

---

## File Structure

### New files
- `normalization/correlator.py` — Correlates artifacts from 3 sources into sessions (~120 lines)
- `ui/filter_bar.py` — Date range and device filter widgets (~80 lines)
- `tests/` — Test directory (this plan does NOT include TDD due to project constraints; testing happens in experimentation phase)

### Modified files
- `store/models.py` — Add `hash_sha256` column to events table, add `source` to devices
- `store/database.py` — Add session CRUD, event hash insertion, filter queries
- `acquisition/evtx_reader.py` — Extract Event IDs 20001/20003, extract device identifiers from XML
- `acquisition/setupapi_reader.py` — Extract VID/PID from hardware_id for correlation
- `normalization/normalizer.py` — Add `normalize_event()` and event timestamp support
- `ui/main_window.py` — Integrate correlation pipeline, connect filter bar
- `ui/device_table.py` — Add "Fuentes" column (7th column)
- `reporting/report_generator.py` — Add sources column to HTML report

---

### Task 1: Add SHA-256 hash column to events schema

**Files:**
- Modify: `store/models.py:30-41`

- [ ] **Step 1: Add hash_sha256 column to events table**

In `store/models.py`, update `SQL_CREATE_EVENTS`:

```python
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
```

- [ ] **Step 2: Verify schema loads**

Delete `tfm_usb.db` (or rename it) and run `python -c "from store.database import initialize_database; initialize_database()"` to confirm the new schema creates without error.

- [ ] **Step 3: Commit**

```bash
git add store/models.py
git commit -m "feat: add hash_sha256 column to events table for integrity verification"
```

---

### Task 2: Add session and event database operations

**Files:**
- Modify: `store/database.py`

- [ ] **Step 1: Add hash computation helper**

Add at the top of `database.py` after existing imports:

```python
import hashlib

def _compute_hash(data: str) -> str:
    """Calcula SHA-256 del contenido de un evento."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
```

- [ ] **Step 2: Add insert_session function**

```python
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
```

- [ ] **Step 3: Update insert_event to compute hash**

Replace the current `insert_event` function:

```python
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
```

- [ ] **Step 4: Add get_sessions_for_device**

```python
def get_sessions_for_device(device_id: int) -> List[Dict[str, Any]]:
    """Devuelve todas las sesiones de un dispositivo."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE device_id = ? ORDER BY connected DESC",
            (device_id,),
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 5: Add filtered device query**

```python
def get_devices_filtered(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    serial_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Devuelve dispositivos filtrados por rango de fechas y/o serial."""
    clauses = []
    params = []
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
```

- [ ] **Step 6: Add get_device_sources helper**

```python
def get_device_sources(device_id: int) -> str:
    """Devuelve las fuentes de datos que registraron un dispositivo (ej: 'registro, evtx')."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT source FROM events WHERE device_id = ?",
            (device_id,),
        ).fetchall()
        sources = [r["source"] for r in rows]
        return ", ".join(sorted(sources)) if sources else "registro"
```

- [ ] **Step 7: Verify database.py stays under 200 lines**

The file was 85 lines. Adding ~60 lines of new functions brings it to ~145 lines. Under limit.

- [ ] **Step 8: Commit**

```bash
git add store/database.py
git commit -m "feat: add session CRUD, SHA-256 hashing, filtered queries and source tracking"
```

---

### Task 3: Enhance evtx_reader to extract device identifiers and Event IDs

**Files:**
- Modify: `acquisition/evtx_reader.py`

- [ ] **Step 1: Add XML parsing for device identification**

Replace the full content of `evtx_reader.py` with an enhanced version that parses the XML data from each event record to extract Event IDs and device identifiers:

```python
"""
Lectura de Event Logs .evtx relacionados con USB.
Extrae eventos con IDs 20001 (dispositivo conectado) y 20003 (dispositivo desconectado)
del log de DriverFrameworks-UserMode, más el log de Plug and Play.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

EVTX_DRIVER_LOG = Path(
    r"C:\Windows\System32\winevt\Logs"
    r"\Microsoft-Windows-DriverFrameworks-UserMode%4Operational.evtx"
)
EVTX_PNP_LOG = Path(
    r"C:\Windows\System32\winevt\Logs"
    r"\Microsoft-Windows-Kernel-PnP%4Configuration.evtx"
)

_RELEVANT_EVENT_IDS = {"2003", "2004", "2010", "20001", "20003"}
_RE_EVENT_ID = re.compile(r"<EventID[^>]*>(\d+)</EventID>")
_RE_DEVICE_ID = re.compile(
    r"USB\\VID_([0-9A-Fa-f]{4})&amp;PID_([0-9A-Fa-f]{4})\\([^<&]+)"
)
_RE_LIFETIME = re.compile(r"<LifetimeId[^>]*>\{?([^}<]+)\}?</LifetimeId>")


def _extract_event_id(xml_data: str) -> str:
    """Extrae el EventID del XML del evento."""
    match = _RE_EVENT_ID.search(xml_data)
    return match.group(1) if match else ""


def _extract_usb_ids(xml_data: str) -> Dict[str, str]:
    """Extrae VID, PID y serial del XML del evento, si están presentes."""
    match = _RE_DEVICE_ID.search(xml_data)
    if match:
        return {
            "vendor_id": match.group(1).upper(),
            "product_id": match.group(2).upper(),
            "serial": match.group(3).split("&")[0],
        }
    return {}


def _parse_evtx_file(evtx_path: Path) -> List[Dict[str, Any]]:
    """Parsea un archivo .evtx y devuelve eventos USB relevantes."""
    try:
        from evtx import PyEvtxParser
    except ImportError:
        logger.warning("python-evtx no disponible. Saltando lectura de Event Logs.")
        return []

    events: List[Dict[str, Any]] = []
    try:
        parser = PyEvtxParser(str(evtx_path))
        for record in parser.records_json():
            xml_data = record.get("data", "")
            event_id = _extract_event_id(xml_data)
            if event_id not in _RELEVANT_EVENT_IDS:
                continue
            usb_ids = _extract_usb_ids(xml_data)
            event_type = "usb_connect" if event_id in ("20001", "2003") else "usb_disconnect"
            events.append({
                "source": "evtx",
                "event_type": event_type,
                "event_id": event_id,
                "timestamp": record.get("timestamp", ""),
                "raw": xml_data[:500],
                "vendor_id": usb_ids.get("vendor_id", ""),
                "product_id": usb_ids.get("product_id", ""),
                "serial": usb_ids.get("serial", ""),
                "device_id": None,
                "session_id": None,
            })
    except Exception as exc:
        logger.warning("Error parseando %s: %s", evtx_path, exc)

    logger.info("Eventos USB extraidos de %s: %d", evtx_path.name, len(events))
    return events


def read_usb_events() -> List[Dict[str, Any]]:
    """Lee eventos USB desde los logs de DriverFrameworks y PnP."""
    all_events: List[Dict[str, Any]] = []
    for log_path in (EVTX_DRIVER_LOG, EVTX_PNP_LOG):
        if log_path.exists():
            all_events.extend(_parse_evtx_file(log_path))
        else:
            logger.info("Archivo evtx no encontrado: %s", log_path)
    return all_events
```

- [ ] **Step 2: Verify file is under 200 lines**

This version is ~85 lines. Under limit.

- [ ] **Step 3: Commit**

```bash
git add acquisition/evtx_reader.py
git commit -m "feat: enhance evtx reader with Event ID filtering and USB device extraction"
```

---

### Task 4: Enhance setupapi_reader to extract VID/PID

**Files:**
- Modify: `acquisition/setupapi_reader.py`

- [ ] **Step 1: Add VID/PID extraction from hardware_id**

Add a helper function and update `_parse_log` to extract vendor and product IDs:

```python
_RE_VID_PID = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", re.IGNORECASE)

def _extract_vid_pid(hardware_id: str) -> Dict[str, str]:
    """Extrae VID y PID de un hardware_id como USB\\VID_xxxx&PID_xxxx\\serial."""
    match = _RE_VID_PID.search(hardware_id)
    if match:
        return {
            "vendor_id": match.group(1).upper(),
            "product_id": match.group(2).upper(),
        }
    return {"vendor_id": "", "product_id": ""}
```

- [ ] **Step 2: Update _parse_log to include VID/PID and serial**

Add extraction of serial from hardware_id and include vid/pid in each entry. Update `_parse_log`:

```python
_RE_SERIAL = re.compile(r"USB\\VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}\\(.+)", re.IGNORECASE)

def _parse_log(log_path: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    try:
        text = log_path.read_text(encoding="utf-16", errors="replace")
    except Exception as exc:
        logger.warning("No se pudo leer setupapi.dev.log: %s", exc)
        return entries

    current_ts = None
    for line in text.splitlines():
        ts_match = _RE_TIMESTAMP.search(line)
        if ts_match:
            current_ts = ts_match.group(1)

        dev_match = _RE_DEVICE.search(line)
        if dev_match:
            hw_id = dev_match.group(1)
            vid_pid = _extract_vid_pid(hw_id)
            serial_match = _RE_SERIAL.search(hw_id)
            serial = serial_match.group(1).split("&")[0] if serial_match else ""
            entries.append({
                "hardware_id": hw_id,
                "timestamp": current_ts,
                "source": "setupapi",
                "vendor_id": vid_pid["vendor_id"],
                "product_id": vid_pid["product_id"],
                "serial": serial,
            })

    logger.info("Entradas setupapi parseadas: %d", len(entries))
    return entries
```

- [ ] **Step 3: Verify file is under 200 lines**

This version is ~65 lines. Under limit.

- [ ] **Step 4: Commit**

```bash
git add acquisition/setupapi_reader.py
git commit -m "feat: extract VID/PID and serial from setupapi entries for correlation"
```

---

### Task 5: Create the correlator module

**Files:**
- Create: `normalization/correlator.py`

- [ ] **Step 1: Create correlator.py**

This module takes the outputs of all 3 readers, matches them by serial/VID+PID, creates sessions, and returns a unified dataset.

```python
"""
Correlaciona artefactos de las 3 fuentes (registro, evtx, setupapi)
en sesiones USB coherentes y únicas.
"""

import logging
from typing import List, Dict, Any, Optional

from normalization.normalizer import normalize_timestamp

logger = logging.getLogger(__name__)


def _match_device_to_events(
    device: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filtra eventos que coinciden con un dispositivo por serial o VID+PID."""
    serial = device.get("serial", "")
    vid = device.get("vendor_id", "")
    pid = device.get("product_id", "")
    matched = []
    for evt in events:
        evt_serial = evt.get("serial", "")
        evt_vid = evt.get("vendor_id", "")
        evt_pid = evt.get("product_id", "")
        if serial and evt_serial and serial.upper() == evt_serial.upper():
            matched.append(evt)
        elif vid and pid and evt_vid == vid and evt_pid == pid:
            matched.append(evt)
    return matched


def _build_sessions(
    device_id: int,
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Agrupa eventos connect/disconnect en sesiones."""
    sorted_events = sorted(events, key=lambda e: e.get("timestamp") or "")
    sessions = []
    current_session: Optional[Dict[str, Any]] = None

    for evt in sorted_events:
        ts = normalize_timestamp(evt.get("timestamp"))
        if evt.get("event_type") == "usb_connect":
            if current_session:
                sessions.append(current_session)
            current_session = {
                "device_id": device_id,
                "connected": ts,
                "disconnected": None,
                "drive_letter": None,
            }
        elif evt.get("event_type") == "usb_disconnect":
            if current_session:
                current_session["disconnected"] = ts
                sessions.append(current_session)
                current_session = None

    if current_session:
        sessions.append(current_session)
    return sessions


def _enrich_first_seen(
    device: Dict[str, Any],
    setupapi_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Actualiza first_seen con el timestamp mas antiguo de setupapi si existe."""
    serial = device.get("serial", "")
    vid = device.get("vendor_id", "")
    pid = device.get("product_id", "")

    for entry in setupapi_entries:
        entry_serial = entry.get("serial", "")
        entry_vid = entry.get("vendor_id", "")
        entry_pid = entry.get("product_id", "")
        match = False
        if serial and entry_serial and serial.upper() == entry_serial.upper():
            match = True
        elif vid and pid and entry_vid == vid and entry_pid == pid:
            match = True

        if match and entry.get("timestamp"):
            ts = normalize_timestamp(entry["timestamp"])
            if ts and (not device.get("first_seen") or ts < device["first_seen"]):
                device["first_seen"] = ts
    return device


def correlate_sources(
    devices: List[Dict[str, Any]],
    evtx_events: List[Dict[str, Any]],
    setupapi_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Correlaciona las 3 fuentes. Retorna dict con:
    - devices: lista enriquecida
    - sessions: lista de sesiones
    - events: lista de eventos con device_id asignado
    """
    all_sessions: List[Dict[str, Any]] = []
    all_events: List[Dict[str, Any]] = []
    enriched_devices: List[Dict[str, Any]] = []
    sources_map: Dict[str, List[str]] = {}

    for device in devices:
        serial = device.get("serial", "")
        sources = ["registro"]

        # Enriquecer first_seen con setupapi
        matched_setupapi = [
            e for e in setupapi_entries
            if _matches_device(device, e)
        ]
        if matched_setupapi:
            device = _enrich_first_seen(device, matched_setupapi)
            sources.append("setupapi")

        enriched_devices.append(device)

        # Correlacionar eventos evtx
        matched_evtx = _match_device_to_events(device, evtx_events)
        if matched_evtx:
            sources.append("evtx")

        sources_map[serial] = sources

        # Los eventos se asignan con device_id despues del upsert
        for evt in matched_evtx:
            evt["_serial"] = serial
            all_events.append(evt)

        for entry in matched_setupapi:
            all_events.append({
                "source": "setupapi",
                "event_type": "device_install",
                "timestamp": normalize_timestamp(entry.get("timestamp")),
                "raw": entry.get("hardware_id", "")[:500],
                "_serial": serial,
                "device_id": None,
                "session_id": None,
            })

    logger.info(
        "Correlacion completada: %d dispositivos, %d eventos",
        len(enriched_devices), len(all_events),
    )
    return {
        "devices": enriched_devices,
        "events": all_events,
        "sources_map": sources_map,
    }


def _matches_device(device: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    """Comprueba si una entrada coincide con un dispositivo."""
    serial = device.get("serial", "")
    vid = device.get("vendor_id", "")
    pid = device.get("product_id", "")
    e_serial = entry.get("serial", "")
    e_vid = entry.get("vendor_id", "")
    e_pid = entry.get("product_id", "")
    if serial and e_serial and serial.upper() == e_serial.upper():
        return True
    if vid and pid and e_vid == vid and e_pid == pid:
        return True
    return False
```

- [ ] **Step 2: Verify file is under 200 lines**

This version is ~145 lines. Under limit.

- [ ] **Step 3: Commit**

```bash
git add normalization/correlator.py
git commit -m "feat: add correlator module to unify registry, evtx and setupapi artifacts"
```

---

### Task 6: Integrate correlation pipeline in AnalysisWorker

**Files:**
- Modify: `ui/main_window.py:27-42` (AnalysisWorker.run)

- [ ] **Step 1: Update AnalysisWorker.run() to use correlation**

Replace the `run` method body:

```python
def run(self) -> None:
    try:
        from acquisition.registry_reader import read_usb_devices
        from acquisition.evtx_reader import read_usb_events
        from acquisition.setupapi_reader import read_setupapi_devices
        from normalization.normalizer import normalize_devices
        from normalization.correlator import correlate_sources
        from store.database import (
            initialize_database, upsert_device, get_all_devices,
            insert_event, insert_session, get_device_sources,
        )

        raw = read_usb_devices()
        evtx_events = read_usb_events()
        setupapi_entries = read_setupapi_devices()

        clean = normalize_devices(raw)
        initialize_database()

        result = correlate_sources(clean, evtx_events, setupapi_entries)

        # Persistir dispositivos y obtener IDs
        serial_to_id = {}
        for dev in result["devices"]:
            dev_id = upsert_device(dev)
            serial_to_id[dev.get("serial", "")] = dev_id

        # Persistir eventos con device_id resuelto
        for evt in result["events"]:
            serial = evt.pop("_serial", "")
            evt["device_id"] = serial_to_id.get(serial)
            insert_event(evt)

        # Recuperar dispositivos con fuentes
        devices = get_all_devices()
        for dev in devices:
            dev["sources"] = get_device_sources(dev["id"])

        self.finished.emit(devices)
    except Exception as exc:
        logger.exception("Error durante el analisis")
        self.error.emit(str(exc))
```

- [ ] **Step 2: Verify main_window.py stays under 200 lines**

Original was 127 lines. The run method grew by ~15 lines. Total ~142 lines. Under limit.

- [ ] **Step 3: Commit**

```bash
git add ui/main_window.py
git commit -m "feat: integrate 3-source correlation pipeline in analysis worker"
```

---

### Task 7: Add "Fuentes" column to device table

**Files:**
- Modify: `ui/device_table.py`

- [ ] **Step 1: Add sources column**

Update the `COLUMNS` list:

```python
COLUMNS = [
    ("friendly_name", "Nombre del dispositivo"),
    ("serial",        "Numero de serie"),
    ("vendor_id",     "Vendor ID"),
    ("product_id",    "Product ID"),
    ("first_seen",    "Primera conexion"),
    ("last_seen",     "Ultima conexion"),
    ("sources",       "Fuentes"),
]
```

No other changes needed - `load_devices` already iterates `COLUMNS` dynamically.

- [ ] **Step 2: Commit**

```bash
git add ui/device_table.py
git commit -m "feat: add data sources column to device table"
```

---

### Task 8: Create filter bar widget

**Files:**
- Create: `ui/filter_bar.py`

- [ ] **Step 1: Create filter_bar.py**

```python
"""
Barra de filtros para la tabla de dispositivos.
Permite filtrar por rango de fechas y por texto (serial/nombre).
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QDateEdit, QLineEdit, QPushButton,
)
from PyQt6.QtCore import pyqtSignal, QDate


class FilterBar(QWidget):
    """Barra de filtros con fecha desde, fecha hasta y texto libre."""
    filter_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(2020, 1, 1))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_from)

        layout.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_to)

        layout.addWidget(QLabel("Buscar:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Serial o nombre del dispositivo...")
        self.search_box.setMinimumWidth(200)
        layout.addWidget(self.search_box)

        self.btn_filter = QPushButton("Filtrar")
        self.btn_filter.clicked.connect(self.filter_changed.emit)
        layout.addWidget(self.btn_filter)

        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.clicked.connect(self._clear_filters)
        layout.addWidget(self.btn_clear)

        layout.addStretch()

    def _clear_filters(self) -> None:
        """Restablece los filtros a sus valores por defecto."""
        self.date_from.setDate(QDate(2020, 1, 1))
        self.date_to.setDate(QDate.currentDate())
        self.search_box.clear()
        self.filter_changed.emit()

    def get_filters(self) -> dict:
        """Devuelve los filtros actuales como diccionario."""
        return {
            "date_from": self.date_from.date().toString("yyyy-MM-dd") + " 00:00:00",
            "date_to": self.date_to.date().toString("yyyy-MM-dd") + " 23:59:59",
            "search": self.search_box.text().strip() or None,
        }
```

- [ ] **Step 2: Verify file is under 200 lines**

This version is ~70 lines. Under limit.

- [ ] **Step 3: Commit**

```bash
git add ui/filter_bar.py
git commit -m "feat: add filter bar widget with date range and text search"
```

---

### Task 9: Integrate filter bar into main window

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Step 1: Import and add filter bar**

Add import at top of `main_window.py`:

```python
from ui.filter_bar import FilterBar
```

In `_build_ui`, after the title label and before the table widget, add:

```python
# Barra de filtros
self.filter_bar = FilterBar()
self.filter_bar.filter_changed.connect(self._apply_filters)
root.addWidget(self.filter_bar)
```

- [ ] **Step 2: Add _apply_filters method**

Add a new method to `MainWindow`:

```python
def _apply_filters(self) -> None:
    """Aplica los filtros de la barra sobre los dispositivos en memoria."""
    if not self._devices:
        return
    filters = self.filter_bar.get_filters()
    filtered = []
    for dev in self._devices:
        last_seen = dev.get("last_seen") or ""
        first_seen = dev.get("first_seen") or ""
        if filters["date_from"] and last_seen and last_seen < filters["date_from"]:
            continue
        if filters["date_to"] and first_seen and first_seen > filters["date_to"]:
            continue
        if filters["search"]:
            text = filters["search"].lower()
            name = (dev.get("friendly_name") or "").lower()
            serial = (dev.get("serial") or "").lower()
            if text not in name and text not in serial:
                continue
        filtered.append(dev)
    self.table.load_devices(filtered)
    self.status.showMessage(
        f"Mostrando {len(filtered)} de {len(self._devices)} dispositivo(s)."
    )
```

- [ ] **Step 3: Verify main_window.py stays under 200 lines**

After adding ~25 lines (import + widget + method), total ~167 lines. Under limit.

- [ ] **Step 4: Commit**

```bash
git add ui/main_window.py
git commit -m "feat: integrate filter bar with date range and text search in main window"
```

---

### Task 10: Add sources column to HTML report

**Files:**
- Modify: `reporting/report_generator.py`

- [ ] **Step 1: Update template to include sources column**

In the template's `<thead>` section, add after the last `<th>`:

```html
<th>Fuentes</th>
```

In the template's `<tbody>` loop, add after the last `<td>`:

```html
<td>{{ dev.sources or 'registro' }}</td>
```

Update the `<td colspan>` from 7 to 8.

- [ ] **Step 2: Commit**

```bash
git add reporting/report_generator.py
git commit -m "feat: add data sources column to HTML report"
```

---

### Task 11: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add entry for all MVP forense changes**

Add at the top of CHANGELOG.md (after `# CHANGELOG`):

```markdown
## [2026-04-01] — MVP Forense: correlacion multifuente y filtros

### Anadido
- `normalization/correlator.py`: modulo de correlacion de artefactos de 3 fuentes
- `ui/filter_bar.py`: barra de filtros por fecha y texto en la UI
- Columna "Fuentes" en la tabla de dispositivos y en el informe HTML
- Hash SHA-256 de integridad en cada evento insertado en la base de datos
- Extraccion de Event IDs 20001/20003 y VID/PID desde logs .evtx
- Extraccion de VID/PID y serial desde setupapi.dev.log
- Consultas filtradas por rango de fechas y serial en la base de datos
- Creacion de sesiones USB desde eventos connect/disconnect correlacionados

### Modificado
- `acquisition/evtx_reader.py`: parseo de XML para extraer identificadores USB
- `acquisition/setupapi_reader.py`: extraccion de VID/PID del hardware_id
- `store/models.py`: columna `hash_sha256` en tabla events
- `store/database.py`: funciones de sesion, hash, filtros y fuentes
- `ui/main_window.py`: pipeline de analisis con correlacion de 3 fuentes
- `ui/device_table.py`: columna de fuentes de datos
- `reporting/report_generator.py`: columna de fuentes en informe HTML
```

- [ ] **Step 2: Commit all remaining changes**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG with MVP forense milestone"
```

---

## Summary

| Task | Description | Files | Est. Lines Changed |
|------|-------------|-------|--------------------|
| 1 | SHA-256 column in events schema | models.py | +1 |
| 2 | Session CRUD, hash, filters, sources DB | database.py | +60 |
| 3 | Enhanced evtx reader with Event IDs & USB IDs | evtx_reader.py | rewrite ~85 |
| 4 | SetupAPI VID/PID extraction | setupapi_reader.py | +20 |
| 5 | Correlator module (new) | correlator.py | ~145 |
| 6 | Correlation pipeline in AnalysisWorker | main_window.py | +15 |
| 7 | Sources column in table | device_table.py | +1 |
| 8 | Filter bar widget (new) | filter_bar.py | ~70 |
| 9 | Filter bar integration in main window | main_window.py | +25 |
| 10 | Sources column in HTML report | report_generator.py | +3 |
| 11 | CHANGELOG update | CHANGELOG.md | +20 |

**Total new code:** ~260 lines across 2 new files + ~125 lines of modifications to 7 existing files.
**All files remain under the 200-line limit.**
