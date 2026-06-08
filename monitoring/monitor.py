"""
Monitor en segundo plano: QThread que sondea periodicamente el sistema.
Captura senales, detecta USBs nuevos y aplica bloqueo por horario.
Emite senales Qt para que la UI se actualice en vivo.
"""

import logging
from typing import Set

from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from monitoring.monitor_cycle import run_cycle, run_fast_usb_check
from store.anomaly_store import get_config

logger = logging.getLogger(__name__)

# Cada cuanto se hace el chequeo rapido de USB (deteccion de pendrives).
# 1 segundo equilibra reaccion casi inmediata y consumo de CPU minimo (el
# chequeo en si es de ~0,1 s y no usa PowerShell).
_FAST_INTERVAL_MS = 1000


class BackgroundMonitor(QThread):
    """
    Hilo de monitorizacion continua con dos ritmos:
    - chequeo rapido (cada ~1,5 s): detecta unidades USB extraibles recien
      montadas y reacciona de inmediato (alerta y, en estricto, bloqueo);
    - ciclo completo (intervalo configurable, por defecto 30 s): captura
      senales del sistema y el estado completo de dispositivos.
    """

    cycle_done = pyqtSignal(dict)   # resultado del ciclo completo
    usb_blocked = pyqtSignal(list)  # bloqueos por horario anomalo

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = False
        self._known_serials: Set[str] = set()
        self._known_drives: Set[str] = set()
        self._known_usb_keys: Set[str] = set()
        self._mutex = QMutex()
        self._wait = QWaitCondition()

    def _full_interval_ms(self) -> int:
        try:
            secs = int(get_config("monitor.interval_s", "30") or "30")
        except ValueError:
            secs = 30
        return max(5, secs) * 1000

    def run(self) -> None:
        self._running = True
        logger.info("Monitor en segundo plano iniciado.")
        # Estado inicial: aprende lo ya presente sin reaccionar.
        try:
            from acquisition.live_state import get_live_usb_state
            from acquisition.fast_usb import get_storage_drives
            from monitoring.monitor_cycle import _device_key
            estado = get_live_usb_state()
            self._known_serials = set(estado.get("connected_serials", set()))
            # Incluye unidades fijas presentes al arrancar (disco del sistema y
            # discos internos): asi solo se reacciona a las que se conecten
            # despues, no a las que ya estaban.
            self._known_drives = set(get_storage_drives().keys())
            self._known_usb_keys = {
                _device_key(d) for d in estado.get("present_devices", [])}
        except Exception as exc:
            logger.warning("Monitor: estado inicial fallo: %s", exc)

        cycle_index = 0
        elapsed_ms = self._full_interval_ms()  # forzar ciclo completo al inicio
        while self._running:
            # --- Chequeo rapido de USB (cada tick) ---
            try:
                fast = run_fast_usb_check(self._known_drives)
                self._known_drives = fast["current_drives"]
                if fast["blocks"]:
                    self.usb_blocked.emit(fast["blocks"])
            except Exception as exc:
                logger.exception("Monitor: error en chequeo rapido: %s", exc)

            # --- Ciclo completo (cuando toca por intervalo) ---
            if elapsed_ms >= self._full_interval_ms():
                try:
                    result = run_cycle(self._known_serials, cycle_index,
                                       self._known_usb_keys)
                    self._known_serials = result["connected_serials"]
                    self._known_usb_keys = result["current_usb_keys"]
                    self.cycle_done.emit(result)
                    if result["blocks"]:
                        self.usb_blocked.emit(result["blocks"])
                except Exception as exc:
                    logger.exception("Monitor: error en ciclo: %s", exc)
                cycle_index += 1
                elapsed_ms = 0

            self._mutex.lock()
            if self._running:
                self._wait.wait(self._mutex, _FAST_INTERVAL_MS)
            self._mutex.unlock()
            elapsed_ms += _FAST_INTERVAL_MS

        logger.info("Monitor en segundo plano detenido.")

    def stop(self) -> None:
        """Detiene el bucle de forma limpia."""
        self._mutex.lock()
        self._running = False
        self._wait.wakeAll()
        self._mutex.unlock()

    def is_running(self) -> bool:
        return self._running
