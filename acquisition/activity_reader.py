"""
Captura de actividad en vivo:
- Aplicacion en primer plano (ventana activa) via Win32 user32.
- Tiempo de inactividad del sistema via GetLastInputInfo (ctypes).
Senales instantaneas; el monitor las muestrea periodicamente.
"""

import ctypes
import logging
import platform
from ctypes import wintypes
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

CATEGORY = "activity"
_TS_FMT = "%Y-%m-%d %H:%M:%S"
_IDLE_THRESHOLD_S = 300  # 5 min sin input => inactivo


def _foreground_app() -> Optional[str]:
    """Nombre del ejecutable de la ventana en primer plano."""
    if platform.system() != "Windows":
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return _process_name(pid.value)
    except OSError as exc:
        logger.debug("No se pudo leer ventana activa: %s", exc)
        return None


def _process_name(pid: int) -> Optional[str]:
    try:
        import psutil
        return psutil.Process(pid).name()
    except Exception:
        return _process_name_winapi(pid)


def _process_name_winapi(pid: int) -> Optional[str]:
    """Fallback sin psutil usando QueryFullProcessImageName."""
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFO
        if not h:
            return None
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        k32.CloseHandle(h)
        if ok:
            return buf.value.rsplit("\\", 1)[-1]
    except OSError:
        pass
    return None


def _idle_seconds() -> float:
    """Segundos desde el ultimo input de usuario."""
    if platform.system() != "Windows":
        return 0.0

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    try:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        tick = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (tick - info.dwTime) / 1000.0)
    except OSError:
        return 0.0


def sample_activity() -> List[Dict[str, Any]]:
    """Muestrea actividad actual; devuelve senales nuevas."""
    now = datetime.now().strftime(_TS_FMT)
    idle = _idle_seconds()
    signals: List[Dict[str, Any]] = [{
        "category":    CATEGORY,
        "signal_type": "idle" if idle >= _IDLE_THRESHOLD_S else "active",
        "timestamp":   now,
        "detail":      f"idle_s={int(idle)}",
    }]
    app = _foreground_app()
    if app and idle < _IDLE_THRESHOLD_S:
        signals.append({
            "category":    CATEGORY,
            "signal_type": "foreground_app",
            "timestamp":   now,
            "detail":      app,
        })
    return signals
