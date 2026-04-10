"""
Ventana principal de la aplicación PyQt6.
Coordina los módulos de adquisición, normalización, persistencia y UI.
"""

import logging
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStatusBar, QLabel, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ui.device_table import DeviceTable
from ui.report_viewer import ReportViewerDialog
from ui.filter_bar import FilterBar

logger = logging.getLogger(__name__)


class AnalysisWorker(QThread):
    """Hilo secundario para ejecutar la adquisición sin bloquear la UI."""
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def run(self) -> None:
        try:
            from acquisition.registry_reader import read_usb_devices
            from acquisition.evtx_reader import read_usb_events
            from acquisition.setupapi_reader import read_setupapi_devices
            from normalization.normalizer import normalize_devices
            from normalization.correlator import correlate_sources
            from store.database import (
                initialize_database, upsert_device, get_all_devices,
                insert_event, get_device_sources,
            )

            raw = read_usb_devices()
            evtx_events = read_usb_events()
            setupapi_entries = read_setupapi_devices()

            clean = normalize_devices(raw)
            initialize_database()

            result = correlate_sources(clean, evtx_events, setupapi_entries)

            # Persistir dispositivos y obtener IDs
            serial_to_id = {}
            for dev in result["devices"]:
                dev_id = upsert_device(dev)
                serial_to_id[dev.get("serial", "")] = dev_id

            # Persistir eventos con device_id resuelto
            for evt in result["events"]:
                serial = evt.pop("_serial", "")
                evt["device_id"] = serial_to_id.get(serial)
                insert_event(evt)

            # Recuperar dispositivos y anadir fuentes
            devices = get_all_devices()
            for dev in devices:
                dev["sources"] = get_device_sources(dev["id"])

            self.finished.emit(devices)
        except Exception as exc:
            logger.exception("Error durante el analisis")
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TFM — Análisis Forense USB en Windows")
        self.setMinimumSize(900, 500)
        self._devices = []
        self._worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # Cabecera
        title = QLabel("<h2>Sistema inteligente de análisis forense USB</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # Barra de filtros
        self.filter_bar = FilterBar()
        self.filter_bar.filter_changed.connect(self._apply_filters)
        root.addWidget(self.filter_bar)

        # Tabla de dispositivos
        self.table = DeviceTable()
        root.addWidget(self.table)

        # Barra de botones
        btn_row = QHBoxLayout()
        self.btn_analyze = QPushButton("Analizar")
        self.btn_analyze.setFixedHeight(36)
        self.btn_analyze.clicked.connect(self._run_analysis)

        self.btn_export = QPushButton("Exportar informe")
        self.btn_export.setFixedHeight(36)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_report)

        btn_row.addWidget(self.btn_analyze)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Listo. Pulse 'Analizar' para iniciar.")

    def _run_analysis(self) -> None:
        self.btn_analyze.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.status.showMessage("Analizando dispositivos USB…")

        self._worker = AnalysisWorker()
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_done(self, devices: list) -> None:
        self._devices = devices
        self.table.load_devices(devices)
        self.btn_analyze.setEnabled(True)
        self.btn_export.setEnabled(bool(devices))
        n = len(devices)
        self.status.showMessage(f"Análisis completado — {n} dispositivo(s) encontrado(s).")

    def _on_analysis_error(self, msg: str) -> None:
        self.btn_analyze.setEnabled(True)
        self.status.showMessage("Error durante el análisis.")
        QMessageBox.critical(self, "Error", f"Error durante el análisis:\n{msg}")

    def _apply_filters(self) -> None:
        """Aplica los filtros de la barra sobre los dispositivos en memoria."""
        if not self._devices:
            return
        filters = self.filter_bar.get_filters()
        filtered = []
        for dev in self._devices:
            last_seen = dev.get("last_seen") or ""
            first_seen = dev.get("first_seen") or ""
            if filters["date_from"] and last_seen and last_seen < filters["date_from"]:
                continue
            if filters["date_to"] and first_seen and first_seen > filters["date_to"]:
                continue
            if filters["search"]:
                text = filters["search"].lower()
                name = (dev.get("friendly_name") or "").lower()
                serial = (dev.get("serial") or "").lower()
                if text not in name and text not in serial:
                    continue
            filtered.append(dev)
        self.table.load_devices(filtered)
        self.status.showMessage(
            f"Mostrando {len(filtered)} de {len(self._devices)} dispositivo(s)."
        )

    def _export_report(self) -> None:
        if not self._devices:
            return
        try:
            from reporting.report_generator import generate_html_report
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = Path(__file__).parent.parent / f"informe_usb_{ts}.html"
            generate_html_report(self._devices, out)
            dlg = ReportViewerDialog(out, parent=self)
            dlg.exec()
        except Exception as exc:
            logger.exception("Error generando informe")
            QMessageBox.critical(self, "Error", f"No se pudo generar el informe:\n{exc}")
