"""
Lectura de eventos de energia: suspensiones y reanudaciones.
- Kernel-Power ID 42  -> el equipo entra en suspension.
- Power-Troubleshooter ID 1 -> el equipo se reanuda.
Devuelve senales normalizadas para system_signals.
"""

import logging
from typing import List, Dict, Any

from acquisition.winevent import query_events

logger = logging.getLogger(__name__)

CATEGORY = "power"


def read_power_signals(max_events: int = 50) -> List[Dict[str, Any]]:
    """Lee eventos de suspension/reanudacion como senales del sistema."""
    signals: List[Dict[str, Any]] = []

    for evt in query_events("System", "Microsoft-Windows-Kernel-Power",
                            [42], max_events):
        signals.append(_signal("suspend", evt))

    for evt in query_events("System", "Microsoft-Windows-Power-Troubleshooter",
                            [1], max_events):
        signals.append(_signal("resume", evt))

    logger.info("Senales de energia leidas: %d", len(signals))
    return signals


def _signal(signal_type: str, evt: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category":    CATEGORY,
        "signal_type": signal_type,
        "timestamp":   evt.get("timestamp") or "",
        "detail":      evt.get("message") or "",
    }
