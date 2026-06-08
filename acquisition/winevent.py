"""
Helper comun para consultar Event Logs de Windows via Get-WinEvent.
Devuelve eventos como lista de dicts {id, timestamp, message}.
No requiere admin para System y logs operacionales.
"""

import json
import logging
import platform
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def _build_filter(log_name: str, provider: Optional[str],
                  ids: Optional[List[int]]) -> str:
    """Construye el FilterHashtable de PowerShell."""
    parts = [f"LogName='{log_name}'"]
    if provider:
        parts.append(f"ProviderName='{provider}'")
    if ids:
        id_list = ",".join(str(i) for i in ids)
        parts.append(f"Id={id_list}")
    return "@{" + "; ".join(parts) + "}"


def query_events(
    log_name: str,
    provider: Optional[str] = None,
    ids: Optional[List[int]] = None,
    max_events: int = 50,
) -> List[Dict[str, Any]]:
    """Consulta eventos y los normaliza. Lista vacia si falla o no hay."""
    if platform.system() != "Windows":
        return []
    flt = _build_filter(log_name, provider, ids)
    ps = (
        f"$e = Get-WinEvent -FilterHashtable {flt} "
        f"-MaxEvents {max_events} -ErrorAction Stop; "
        "$e | ForEach-Object { [PSCustomObject]@{ "
        "id = $_.Id; "
        "ts = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss'); "
        "msg = $_.Message } } | ConvertTo-Json -Depth 2 -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Get-WinEvent fallo (%s): %s", log_name, exc)
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        data = [data]
    out: List[Dict[str, Any]] = []
    for d in data:
        out.append({
            "id":        d.get("id"),
            "timestamp": d.get("ts") or "",
            "message":   (d.get("msg") or "")[:200],
        })
    return out


def now_str() -> str:
    return datetime.now().strftime(_TS_FMT)
