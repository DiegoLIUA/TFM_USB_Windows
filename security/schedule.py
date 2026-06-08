"""
Horario habitual de uso configurable: franja horaria + dias laborables.
Determina si un instante dado cae dentro del horario permitido.
La configuracion se persiste en la tabla config.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from store.anomaly_store import get_config, set_config

logger = logging.getLogger(__name__)

_TS_FMT = "%Y-%m-%d %H:%M:%S"
_DAY_NAMES = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]


def _parse_hhmm(value: str, default: str) -> int:
    """Convierte 'HH:MM' a minutos desde medianoche."""
    try:
        h, m = (value or default).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        h, m = default.split(":")
        return int(h) * 60 + int(m)


def get_schedule() -> Dict[str, Any]:
    """Devuelve la configuracion de horario actual."""
    days_raw = get_config("schedule.days", "0,1,2,3,4") or "0,1,2,3,4"
    try:
        days = [int(d) for d in days_raw.split(",") if d.strip() != ""]
    except ValueError:
        days = [0, 1, 2, 3, 4]
    try:
        margin = float(get_config("schedule.margin_h", "2") or "2")
    except ValueError:
        margin = 2.0
    return {
        "start":   get_config("schedule.start", "08:00"),
        "end":     get_config("schedule.end", "22:00"),
        "days":    days,
        "margin_h": margin,
        "enforce": (get_config("schedule.enforce", "false") or "").lower() == "true",
    }


def set_schedule(start: str, end: str, days: List[int],
                 enforce: bool = True, margin_h: Optional[float] = None) -> None:
    """
    Persiste la configuracion de horario. El parametro enforce se mantiene por
    compatibilidad; la activacion del bloqueo la determina ahora el modo de
    operacion (estricto). margin_h es la tolerancia (en horas) alrededor de la
    franja; si es None, se conserva el valor actual.
    """
    set_config("schedule.start", start)
    set_config("schedule.end", end)
    set_config("schedule.days", ",".join(str(d) for d in sorted(set(days))))
    set_config("schedule.enforce", "true" if enforce else "false")
    if margin_h is not None:
        set_config("schedule.margin_h", str(margin_h))
    logger.info("Horario actualizado: %s-%s dias=%s margen=%sh",
                start, end, days, get_config("schedule.margin_h", "2"))


def _in_band(cur_min: int, start_min: int, end_min: int) -> bool:
    """True si cur_min cae dentro de la franja [start, end] (con o sin cruce)."""
    if start_min <= end_min:
        return start_min <= cur_min <= end_min
    return cur_min >= start_min or cur_min <= end_min  # cruza medianoche


def is_within_schedule(when: Optional[datetime] = None) -> bool:
    """True si 'when' cae dentro del horario habitual configurado (sin margen)."""
    when = when or datetime.now()
    sch = get_schedule()
    if when.weekday() not in sch["days"]:
        return False
    start_min = _parse_hhmm(sch["start"], "08:00")
    end_min = _parse_hhmm(sch["end"], "22:00")
    return _in_band(when.hour * 60 + when.minute, start_min, end_min)


def is_anomalous_schedule(when: Optional[datetime] = None) -> bool:
    """
    True si 'when' es una hora ANOMALA, considerando una zona de tolerancia
    (margen) alrededor del horario habitual. Solo se considera anomala una hora
    que cae fuera del horario ampliado en 'margin_h' por ambos lados.
    Ejemplo: horario 10:00-15:00 con margen 2 h -> zona normal/tolerada
    08:00-17:00; fuera de ahi (17:00-08:00) es anomalo.
    """
    when = when or datetime.now()
    sch = get_schedule()
    if when.weekday() not in sch["days"]:
        return True  # dia no laborable: cualquier hora es anomala
    margin = int(sch["margin_h"] * 60)
    start_ext = (_parse_hhmm(sch["start"], "08:00") - margin) % 1440
    end_ext = (_parse_hhmm(sch["end"], "22:00") + margin) % 1440
    cur_min = when.hour * 60 + when.minute
    return not _in_band(cur_min, start_ext, end_ext)


def is_anomalous_time(when: Optional[datetime] = None) -> bool:
    """True si la insercion debe considerarse fuera de horario y enforzarse."""
    sch = get_schedule()
    if not sch["enforce"]:
        return False
    return not is_within_schedule(when)


def describe_schedule() -> str:
    """Texto legible del horario configurado."""
    sch = get_schedule()
    days = ", ".join(_DAY_NAMES[d] for d in sch["days"]) or "ninguno"
    return f"{sch['start']}–{sch['end']} ({days})"
