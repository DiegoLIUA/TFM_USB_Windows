"""
Lectura de eventos de sesion de usuario (sin requerir admin).
Usa TerminalServices-LocalSessionManager/Operational:
  21=logon, 22=shell start, 23=logoff, 24=disconnect, 25=reconnect,
  39/40=session disconnect detail.
Reconstruye horarios reales de uso del equipo.
"""

import logging
from typing import List, Dict, Any

from acquisition.winevent import query_events

logger = logging.getLogger(__name__)

CATEGORY = "session"
_LOG = "Microsoft-Windows-TerminalServices-LocalSessionManager/Operational"

_TYPE_MAP = {
    21: "logon",
    22: "shell_start",
    23: "logoff",
    24: "disconnect",
    25: "reconnect",
}


def read_session_signals(max_events: int = 80) -> List[Dict[str, Any]]:
    """Lee eventos de sesion como senales del sistema."""
    signals: List[Dict[str, Any]] = []
    events = query_events(_LOG, None, list(_TYPE_MAP.keys()), max_events)
    for evt in events:
        stype = _TYPE_MAP.get(evt.get("id"), "session_other")
        signals.append({
            "category":    CATEGORY,
            "signal_type": stype,
            "timestamp":   evt.get("timestamp") or "",
            "detail":      evt.get("message") or "",
        })
    logger.info("Senales de sesion leidas: %d", len(signals))
    return signals
