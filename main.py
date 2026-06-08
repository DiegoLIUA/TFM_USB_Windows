"""
Punto de entrada de la aplicación TFM_USB_Windows.
Lanza la ventana principal PyQt6.
"""

import sys
import logging
import traceback
from pathlib import Path

# El log se ancla a la carpeta del proyecto (no al directorio de trabajo), para
# que la ruta sea estable independientemente de desde donde se lance la app.
_LOG_PATH = Path(__file__).resolve().parent / "tfm_usb.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_PATH, encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def _show_fatal_error(mensaje: str) -> None:
    """
    Muestra un dialogo de error critico al usuario. Se usa cuando el arranque
    falla, para no cerrar en silencio. Si ni siquiera Qt esta disponible, cae a
    la salida estandar.
    """
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        # QMessageBox necesita una instancia de QApplication viva; se crea si
        # aun no existe (el fallo pudo ocurrir antes de instanciarla).
        if QApplication.instance() is None:
            QApplication(sys.argv)
        QMessageBox.critical(
            None, "Error al iniciar TFM USB",
            f"No se pudo iniciar la aplicación:\n\n{mensaje}\n\n"
            f"Hay más detalles en el registro:\n{_LOG_PATH}")
    except Exception:  # noqa: BLE001 (ultimo recurso: la GUI no esta disponible)
        print(f"ERROR FATAL al iniciar: {mensaje}", file=sys.stderr)


def main() -> None:
    # Por defecto se solicita elevacion a administrador (UAC) para que el
    # bloqueo fisico de dispositivos funcione. Use --no-admin para omitirlo
    # (util en desarrollo o para capturas de pantalla).
    try:
        from security.privileges import relaunch_as_admin
        if "--no-admin" not in sys.argv and relaunch_as_admin():
            sys.exit(0)  # se ha lanzado la copia elevada; cerrar esta

        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        from ui.theme import apply_theme
        from ui.app_icon import apply_app_icon

        app = QApplication(sys.argv)
        app.setApplicationName("TFM USB Windows")
        app.setOrganizationName("TFM")
        apply_theme(app)
        window = MainWindow()
        apply_app_icon(app, window)
        window.show()
        sys.exit(app.exec())
    except SystemExit:
        raise  # sys.exit() es control de flujo normal, no un error
    except Exception as exc:  # noqa: BLE001 (frontera de la aplicacion)
        logger.critical("Fallo no controlado en el arranque:\n%s",
                        traceback.format_exc())
        _show_fatal_error(f"{type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
