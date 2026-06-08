"""
Deteccion y elevacion de privilegios de administrador.
El bloqueo fisico de dispositivos (Disable/Enable-PnpDevice) requiere admin;
sin el, esas funciones quedan limitadas al bloqueo logico.
"""

import ctypes
import logging
import platform
import sys

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """True si el proceso se ejecuta con privilegios de administrador."""
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError) as exc:
        logger.debug("No se pudo comprobar admin: %s", exc)
        return False


def relaunch_as_admin() -> bool:
    """
    Relanza la aplicacion con privilegios de administrador mediante UAC.
    Devuelve True si se ha lanzado la copia elevada (el proceso actual debe
    cerrarse), o False si ya era admin, no es Windows o el usuario rechazo UAC.
    """
    if platform.system() != "Windows" or is_admin():
        return False
    try:
        import os
        # ShellExecuteW con verbo 'runas' dispara el dialogo UAC de Windows.
        # Ruta absoluta al script y working dir explicito, porque la copia
        # elevada arranca en C:\Windows\System32 por defecto.
        script = os.path.abspath(sys.argv[0])
        workdir = os.path.dirname(script)
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', workdir, 1)
        # ShellExecuteW devuelve >32 si tuvo exito
        if ret > 32:
            logger.info("Relanzando la aplicacion como administrador (UAC).")
            return True
        logger.info("El usuario rechazo la elevacion UAC (codigo %s).", ret)
        return False
    except (AttributeError, OSError) as exc:
        logger.warning("No se pudo solicitar elevacion: %s", exc)
        return False


def privilege_warning() -> str:
    """
    Mensaje a mostrar al arrancar segun los privilegios.
    Cadena vacia si es admin (no hace falta avisar).
    """
    if is_admin():
        return ""
    return (
        "La aplicación se está ejecutando SIN privilegios de administrador.\n\n"
        "El análisis, la monitorización y las alertas funcionan con normalidad, "
        "pero el bloqueo físico de dispositivos (deshabilitar un USB fuera de "
        "horario) no podrá aplicarse: el bloqueo quedará registrado de forma "
        "lógica y el diálogo de desbloqueo TOTP seguirá apareciendo.\n\n"
        "Para habilitar el bloqueo físico, ejecute la aplicación como "
        "administrador."
    )
