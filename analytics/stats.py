"""
Agregaciones estadisticas a partir de las senales del sistema y dispositivos.
Alimenta el dashboard de la UI. Sin dependencias de Qt (testeable aislado).
"""

from collections import Counter
from typing import Dict, List, Tuple

from store.signals_store import get_signals, count_signals_by_category
from store.database import get_all_devices


def _hour_of(timestamp: str) -> int:
    """Extrae la hora (0-23) de un timestamp 'yyyy-MM-dd HH:MM:SS'."""
    try:
        return int(timestamp[11:13])
    except (ValueError, IndexError):
        return -1


def usage_by_hour(limit: int = 5000) -> List[int]:
    """
    Distribucion de actividad por hora del dia (24 bins) a partir de
    las senales de actividad 'active'. Devuelve lista de 24 enteros.
    """
    counts = [0] * 24
    for sig in get_signals(category="activity", limit=limit):
        if sig.get("signal_type") != "active":
            continue
        h = _hour_of(sig.get("timestamp") or "")
        if 0 <= h <= 23:
            counts[h] += 1
    return counts


def suspensions_by_day(limit: int = 2000) -> Dict[str, int]:
    """Numero de suspensiones por dia (fecha -> conteo)."""
    counts: Counter = Counter()
    for sig in get_signals(category="power", limit=limit):
        if sig.get("signal_type") != "suspend":
            continue
        day = (sig.get("timestamp") or "")[:10]
        if day:
            counts[day] += 1
    return dict(sorted(counts.items()))


def top_apps(n: int = 8, limit: int = 5000) -> List[Tuple[str, int]]:
    """Aplicaciones mas usadas (por muestras en primer plano)."""
    counts: Counter = Counter()
    for sig in get_signals(category="activity", limit=limit):
        if sig.get("signal_type") != "foreground_app":
            continue
        app = (sig.get("detail") or "").strip()
        if app:
            counts[app] += 1
    return counts.most_common(n)


def device_type_distribution() -> Dict[str, int]:
    """Numero de dispositivos por tipo."""
    counts: Counter = Counter()
    for dev in get_all_devices():
        counts[dev.get("device_type") or "otro"] += 1
    return dict(counts)


# Duracion minima (minutos) para que una sesion cuente. Descarta conexiones de
# duracion nula o insignificante (montajes fugaces o sesiones sin uso real), que
# no representan un uso efectivo del dispositivo.
_MIN_SESSION_MIN = 1.0

# Duracion maxima (minutos) plausible para una sesion. Por encima se considera
# un error de registro (USB retirado sin que se detectara la desconexion, o dato
# heredado de la generacion inicial), no uso real, y se descarta para no
# distorsionar la estadistica. 12 h es un limite conservador para uso continuado.
_MAX_SESSION_MIN = 12 * 60.0


def _mediana(valores: List[float]) -> float:
    """Mediana de una lista no vacia (valor central, robusto a atipicos)."""
    ordenados = sorted(valores)
    n = len(ordenados)
    medio = n // 2
    if n % 2 == 1:
        return ordenados[medio]
    return (ordenados[medio - 1] + ordenados[medio]) / 2.0


def median_duration_top_storage(n: int = 3) -> List[Tuple[str, float]]:
    """
    Duracion TIPICA (mediana, en minutos) de las sesiones de los dispositivos de
    almacenamiento mas usados. Se usa la mediana en lugar de la media porque es
    robusta frente a sesiones atipicas, que distorsionarian la media. Solo se
    cuentan sesiones con desconexion registrada y de duracion plausible
    (entre _MIN_SESSION_MIN y _MAX_SESSION_MIN): se ignoran tanto las fugaces
    como las imposiblemente largas (errores de registro).
    Devuelve los n dispositivos con mas sesiones (utiles), como
    (nombre, minutos_mediana).
    """
    from datetime import datetime
    from store.database import get_connection
    fmt = "%Y-%m-%d %H:%M:%S"
    sql = (
        "SELECT d.friendly_name, s.connected, s.disconnected "
        "FROM sessions s JOIN devices d ON s.device_id = d.id "
        "WHERE d.device_type = 'almacenamiento' "
        "AND s.disconnected IS NOT NULL"
    )
    por_dispositivo: Dict[str, List[float]] = {}
    with get_connection() as conn:
        for r in conn.execute(sql):
            try:
                ini = datetime.strptime(r["connected"], fmt)
                fin = datetime.strptime(r["disconnected"], fmt)
            except (ValueError, TypeError):
                continue
            mins = (fin - ini).total_seconds() / 60.0
            if mins < _MIN_SESSION_MIN or mins > _MAX_SESSION_MIN:
                continue  # descarta sesiones fugaces o imposiblemente largas
            nombre = r["friendly_name"] or "Dispositivo USB"
            por_dispositivo.setdefault(nombre, []).append(mins)
    # Ordena por numero de sesiones utiles (mas usados) y toma los n primeros
    ordenados = sorted(por_dispositivo.items(),
                       key=lambda kv: len(kv[1]), reverse=True)[:n]
    return [(nombre, round(_mediana(v), 1)) for nombre, v in ordenados]


def signal_summary() -> Dict[str, int]:
    """Resumen de senales por categoria (power, session, activity)."""
    return count_signals_by_category()


def session_events_by_type(limit: int = 2000) -> Dict[str, int]:
    """Conteo de eventos de sesion por tipo (logon, logoff, ...)."""
    counts: Counter = Counter()
    for sig in get_signals(category="session", limit=limit):
        counts[sig.get("signal_type") or "otro"] += 1
    return dict(counts)


def compute_usual_schedule(min_ratio: float = 0.15) -> Dict[str, object]:
    """
    Deriva la franja horaria habitual a partir de la actividad observada.
    Se consideran 'horas de uso' aquellas cuya actividad alcanza al menos
    min_ratio del pico. La franja propuesta abarca de la primera a la ultima
    hora de uso (con la hora final redondeada al inicio de la hora siguiente).
    Devuelve {start, end, total_active, hours} o un dict vacio si no hay datos.
    """
    counts = usage_by_hour()
    total = sum(counts)
    if total == 0:
        return {"start": None, "end": None, "total_active": 0, "hours": []}
    pico = max(counts)
    umbral = pico * min_ratio
    horas = [h for h, c in enumerate(counts) if c >= umbral]
    if not horas:
        return {"start": None, "end": None, "total_active": total, "hours": []}
    h_ini, h_fin = horas[0], horas[-1]
    # La franja termina al final de la ultima hora con uso (h_fin + 1).
    fin = (h_fin + 1) % 24
    return {
        "start": f"{h_ini:02d}:00",
        "end": f"{fin:02d}:00",
        "total_active": total,
        "hours": horas,
    }
