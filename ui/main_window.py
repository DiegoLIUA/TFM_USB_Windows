"""
Ventana principal de la aplicación PyQt6.
Coordina los módulos de adquisición, normalización, persistencia y UI.
"""

import logging
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStatusBar, QLabel, QMessageBox, QTabWidget, QComboBox,
    QFileDialog, QButtonGroup,
)
from PyQt6.QtCore import Qt, QTimer

from ui.device_table import DeviceTable
from ui.report_viewer import ReportViewerDialog
from ui.filter_bar import FilterBar
from ui.alerts_view import AlertsView
from ui.analysis_worker import AnalysisWorker
from ui.settings_view import SettingsView
from ui.dashboard_view import DashboardView
from ui.monitor_control import MonitorController

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TFM — Análisis Forense USB en Windows")
        self.setMinimumSize(900, 500)
        self._devices = []
        self._worker = None
        self._build_ui()
        QTimer.singleShot(300, self._check_privileges)

    def _check_privileges(self) -> None:
        """Avisa una sola vez si la app no tiene privilegios de admin."""
        from security.privileges import privilege_warning
        msg = privilege_warning()
        if msg:
            QMessageBox.warning(self, "Privilegios limitados", msg)

    def _build_ui(self) -> None:
        from store.anomaly_store import get_config, set_config
        from store.database import initialize_database
        initialize_database()
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Sistema inteligente de análisis forense USB")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # Selector de vista Basico/Experto, centrado bajo el titulo. Solo se
        # muestra en la pestana de Dispositivos (ver _on_tab_changed).
        view_row = QHBoxLayout()
        view_row.addStretch()
        view_row.addWidget(QLabel("Vista:"))
        self.rb_basic = QPushButton("Básico")
        self.rb_expert = QPushButton("Experto")
        for b in (self.rb_basic, self.rb_expert):
            b.setObjectName("viewToggle")
            b.setCheckable(True)
            b.setFixedSize(78, 26)
        self._view_group = QButtonGroup(self)
        self._view_group.setExclusive(True)
        self._view_group.addButton(self.rb_basic)
        self._view_group.addButton(self.rb_expert)
        is_expert = (get_config("ui.view", "basico") or "basico") == "experto"
        self.rb_expert.setChecked(is_expert)
        self.rb_basic.setChecked(not is_expert)
        self.rb_basic.toggled.connect(self._on_view_changed)
        view_row.addWidget(self.rb_basic)
        view_row.addWidget(self.rb_expert)
        view_row.addStretch()
        self.view_row_widget = QWidget()
        self.view_row_widget.setLayout(view_row)
        root.addWidget(self.view_row_widget)

        # Selector de modo de operacion
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Modo:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["aprendizaje", "monitorizacion", "estricto"])
        idx = self.mode_combo.findText(get_config("anomaly.mode", "aprendizaje"))
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.currentTextChanged.connect(
            lambda m: set_config("anomaly.mode", m))
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        root.addLayout(mode_row)

        self.tabs = QTabWidget()
        self._devices_tab = QWidget()
        dl = QVBoxLayout(self._devices_tab); dl.setContentsMargins(0, 0, 0, 0)
        self.filter_bar = FilterBar()
        self.filter_bar.filter_changed.connect(self._apply_filters)
        dl.addWidget(self.filter_bar)
        self.table = DeviceTable()
        self.table.set_expert_mode(is_expert)
        self.table.trust_changed.connect(self._on_trust_changed)
        dl.addWidget(self.table)
        self.tabs.addTab(self._devices_tab, "Dispositivos")
        self.alerts_view = AlertsView()
        self.tabs.addTab(self.alerts_view, "Alertas")
        self.dashboard_view = DashboardView()
        self.tabs.addTab(self.dashboard_view, "Estadísticas")
        self.settings_view = SettingsView()
        self.tabs.addTab(self.settings_view, "Ajustes")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.monitor = MonitorController(self)
        self.status.addPermanentWidget(self.monitor.status_label)

        btn_row = QHBoxLayout()
        self.btn_analyze = QPushButton("Analizar")
        self.btn_analyze.setFixedHeight(36)
        self.btn_analyze.clicked.connect(self._run_analysis)
        self.btn_export = QPushButton("Exportar HTML")
        self.btn_export.setFixedHeight(36)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_report)
        self.btn_export_json = QPushButton("Exportar JSON")
        self.btn_export_json.setFixedHeight(36)
        self.btn_export_json.setEnabled(False)
        self.btn_export_json.clicked.connect(self._export_json)
        btn_row.addWidget(self.btn_analyze)
        btn_row.addWidget(self.monitor.button)
        btn_row.addWidget(self.btn_export)
        btn_row.addWidget(self.btn_export_json)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.status.showMessage("Listo. Pulse 'Analizar' o inicie el monitor.")
        # Estado inicial coherente (arranca en Dispositivos): selector visible.
        self._on_tab_changed(self.tabs.currentIndex())

    def _on_view_changed(self) -> None:
        """Alterna entre vista basica y experta (oculta columnas tecnicas)."""
        from store.anomaly_store import set_config
        expert = self.rb_expert.isChecked()
        self.table.set_expert_mode(expert)
        set_config("ui.view", "experto" if expert else "basico")

    def _on_tab_changed(self, index: int) -> None:
        """Ajusta la UI segun la pestana activa."""
        widget = self.tabs.widget(index)
        # El selector de vista Basico/Experto solo aplica a Dispositivos.
        self.view_row_widget.setVisible(widget is self._devices_tab)
        if widget is self.dashboard_view:
            self.dashboard_view.refresh()
        self._update_export_buttons()

    def _update_export_buttons(self) -> None:
        """Habilita exportar HTML/JSON segun la pestana y si hay datos."""
        widget = self.tabs.currentWidget()
        if widget is self._devices_tab:
            enabled = bool(self._devices)
        elif widget is self.alerts_view:
            from store.anomaly_store import get_alerts
            enabled = bool(get_alerts())
        else:
            enabled = False
        self.btn_export.setEnabled(enabled)
        self.btn_export_json.setEnabled(enabled)

    def _on_trust_changed(self, serial: str, trusted: bool) -> None:
        """Persiste el estado de confianza de un dispositivo (allowlist)."""
        from store.database import set_device_trusted
        set_device_trusted(serial, trusted)
        # Refleja el cambio en la copia en memoria
        for dev in self._devices:
            if (dev.get("serial") or "") == serial:
                dev["trusted"] = 1 if trusted else 0
        estado = "confiable" if trusted else "no confiable"
        self.status.showMessage(f"Dispositivo {serial} marcado como {estado}.")

    def _run_analysis(self) -> None:
        self.btn_analyze.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.status.showMessage("Analizando dispositivos USB…")

        self._worker = AnalysisWorker()
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_done(self, payload: dict) -> None:
        devices = payload.get("devices", [])
        alerts = payload.get("alerts", [])
        self._devices = devices
        self.table.load_devices(devices)
        self.alerts_view.refresh()
        self.btn_analyze.setEnabled(True)
        self._update_export_buttons()
        n, a = len(devices), len(alerts)
        msg = f"Análisis completado — {n} dispositivo(s)."
        if a:
            msg += f" {a} alerta(s) nueva(s)."
            self.tabs.setCurrentWidget(self.alerts_view)
        self.status.showMessage(msg)

    def _on_analysis_error(self, msg: str) -> None:
        self.btn_analyze.setEnabled(True)
        self.status.showMessage("Error durante el análisis.")
        QMessageBox.critical(self, "Error", f"Error durante el análisis:\n{msg}")

    def closeEvent(self, event) -> None:
        """Detiene el monitor en segundo plano al cerrar la ventana."""
        self.monitor.shutdown()
        super().closeEvent(event)

    def _apply_filters(self) -> None:
        """Aplica los filtros de la barra sobre los dispositivos en memoria."""
        if not self._devices:
            return
        filters = self.filter_bar.get_filters()
        filtered = []
        for dev in self._devices:
            if filters.get("only_connected") and not dev.get("connected"):
                continue
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

    def _on_alerts_tab(self) -> bool:
        return self.tabs.currentWidget() is self.alerts_view

    def _export_report(self) -> None:
        """Exporta a HTML el contenido de la pestana activa (dispositivos o alertas)."""
        try:
            from reporting.report_generator import (
                generate_html_report, generate_alerts_html_report, reports_dir)
            from store.anomaly_store import get_alerts
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self._on_alerts_tab():
                alerts = get_alerts()
                if not alerts:
                    return
                out = reports_dir() / f"informe_alertas_{ts}.html"
                generate_alerts_html_report(alerts, out)
            else:
                if not self._devices:
                    return
                out = reports_dir() / f"informe_usb_{ts}.html"
                generate_html_report(self._devices, out)
            ReportViewerDialog(out, parent=self).exec()
        except Exception as exc:
            logger.exception("Error generando informe")
            QMessageBox.critical(self, "Error", f"No se pudo generar el informe:\n{exc}")

    def _export_json(self) -> None:
        """Exporta a JSON el contenido de la pestana activa."""
        try:
            from reporting.report_generator import (
                generate_json_report, generate_alerts_json_report, reports_dir)
            from store.anomaly_store import get_alerts
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            es_alertas = self._on_alerts_tab()
            nombre = "informe_alertas" if es_alertas else "informe_usb"
            default = reports_dir() / f"{nombre}_{ts}.json"
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar informe JSON", str(default), "JSON (*.json)")
            if not path:
                return
            if es_alertas:
                generate_alerts_json_report(get_alerts(), Path(path))
            else:
                generate_json_report(self._devices, get_alerts(), Path(path))
            self.status.showMessage(f"Informe JSON guardado en {path}")
        except Exception as exc:
            logger.exception("Error generando JSON")
            QMessageBox.critical(self, "Error", f"No se pudo generar JSON:\n{exc}")
