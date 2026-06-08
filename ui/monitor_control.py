"""
Control del monitor en segundo plano para la ventana principal.
Encapsula arranque/parada del hilo y la reaccion a USBs bloqueados.
"""

import logging
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import QPushButton, QLabel

from monitoring.monitor import BackgroundMonitor
from ui.unlock_dialog import UnlockDialog
from store.anomaly_store import set_config

logger = logging.getLogger(__name__)


class MonitorController:
    """Gestiona el ciclo de vida del BackgroundMonitor y su UI asociada."""

    def __init__(self, window) -> None:
        self._win = window
        self._monitor: Optional[BackgroundMonitor] = None
        self.button = QPushButton("Iniciar monitor")
        self.button.setObjectName("primaryButton")
        self.button.setFixedHeight(36)
        self.button.clicked.connect(self.toggle)
        self.status_label = QLabel("Monitor: detenido")

    def toggle(self) -> None:
        if self._monitor and self._monitor.is_running():
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        if self._monitor and self._monitor.is_running():
            return
        set_config("monitor.enabled", "true")
        self._monitor = BackgroundMonitor()
        self._monitor.cycle_done.connect(self._on_cycle)
        self._monitor.usb_blocked.connect(self._on_blocked)
        self._monitor.start()
        self.button.setText("Detener monitor")
        self.status_label.setText("Monitor: activo")
        self._win.status.showMessage("Monitor en segundo plano iniciado.")

    def stop(self) -> None:
        set_config("monitor.enabled", "false")
        if self._monitor:
            self._monitor.stop()
            self._monitor.wait(3000)
            self._monitor = None
        self.button.setText("Iniciar monitor")
        self.status_label.setText("Monitor: detenido")
        self._win.status.showMessage("Monitor detenido.")

    def _on_cycle(self, result: Dict[str, Any]) -> None:
        ns = result.get("new_signals", 0)
        nu = result.get("new_usb", [])
        ts = result.get("timestamp", "")
        extra = f" · {len(nu)} USB nuevo(s)" if nu else ""
        self.status_label.setText(
            f"Monitor: activo · {ns} señal(es) @ {ts}{extra}")
        # Refresca la vista de alertas por si el ciclo genero alguna
        if nu:
            self._win.alerts_view.refresh()

    def _on_blocked(self, blocks: List[Dict[str, Any]]) -> None:
        """Muestra el dialogo TOTP cuando un USB se bloquea por horario."""
        logger.warning("USB bloqueado por horario: %d", len(blocks))
        self._win.status.showMessage(
            "⚠ USB bloqueado fuera de horario — se requiere segundo factor.")
        dlg = UnlockDialog(blocks, parent=self._win)
        dlg.exec()

    def shutdown(self) -> None:
        """Detiene el monitor al cerrar la app."""
        if self._monitor and self._monitor.is_running():
            self._monitor.stop()
            self._monitor.wait(3000)
