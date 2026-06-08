"""
Carga del icono de la aplicacion.
Coloca un fichero PNG en assets/app_icon.png (idealmente cuadrado, 256x256).
Si no existe, la aplicacion arranca con el icono por defecto sin fallar.
En Windows, fija ademas el AppUserModelID para que la barra de tareas use el
icono propio en lugar del de python.exe.
"""

import logging
import platform
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QIcon

logger = logging.getLogger(__name__)

_ICON_PATH = Path(__file__).parent.parent / "assets" / "app_icon.png"
_APP_ID = "tfm.usb.forense.monitor"


def _set_windows_app_id() -> None:
    """Asocia un AppUserModelID propio para la barra de tareas de Windows."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except (AttributeError, OSError) as exc:
        logger.debug("No se pudo fijar AppUserModelID: %s", exc)


def load_app_icon() -> Optional[QIcon]:
    """Devuelve el QIcon de la aplicacion, o None si no hay fichero."""
    if not _ICON_PATH.exists():
        logger.info("Icono no encontrado en %s; se usa el por defecto.",
                    _ICON_PATH)
        return None
    return QIcon(str(_ICON_PATH))


def apply_app_icon(app, window=None) -> None:
    """Aplica el icono a la aplicacion y, si se pasa, a la ventana."""
    _set_windows_app_id()
    icon = load_app_icon()
    if icon is None:
        return
    app.setWindowIcon(icon)
    if window is not None:
        window.setWindowIcon(icon)
