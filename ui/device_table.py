"""
Widget de tabla para mostrar los dispositivos USB detectados.
"""

from typing import List, Dict, Any

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

COLUMNS = [
    ("friendly_name", "Nombre del dispositivo"),
    ("device_type",   "Tipo"),
    ("capacity",      "Capacidad"),
    ("trusted",       "Confiable"),
    ("serial",        "Número de serie"),
    ("vendor_id",     "Vendor ID"),
    ("product_id",    "Product ID"),
    ("first_seen",    "Primera conexión"),
    ("last_seen",     "Última conexión"),
    ("connected",     "Estado"),
    ("sources",       "Fuentes"),
]

# Columnas que solo se muestran en modo experto
_EXPERT_ONLY = {"serial", "vendor_id", "product_id", "sources"}

# Columnas que contienen fechas a reformatear a dd-MM-yyyy
_DATE_COLUMNS = {"first_seen", "last_seen"}


def _format_date(value: str) -> str:
    """Convierte 'yyyy-MM-dd HH:MM:SS' a 'dd-MM-yyyy HH:MM:SS'."""
    if not value or len(value) < 10:
        return value
    fecha = value[:10]
    resto = value[10:]
    partes = fecha.split("-")
    if len(partes) == 3 and len(partes[0]) == 4:
        return f"{partes[2]}-{partes[1]}-{partes[0]}{resto}"
    return value


class DeviceTable(QTableWidget):
    # Emitida al marcar/desmarcar 'Confiable': (serial, es_confiable)
    trust_changed = pyqtSignal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        self._setup_table()
        self.itemChanged.connect(self._on_item_changed)

    def _setup_table(self) -> None:
        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels([label for _, label in COLUMNS])
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        # Columnas redimensionables por el usuario (arrastrando el borde)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for col, (_, _) in enumerate(COLUMNS):
            self.setColumnWidth(col, 130)
        self.setColumnWidth(0, 220)  # nombre del dispositivo mas ancho
        # Filas redimensionables verticalmente por el usuario
        vheader = self.verticalHeader()
        vheader.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        vheader.setVisible(True)
        vheader.setDefaultSectionSize(28)

    def set_expert_mode(self, expert: bool) -> None:
        """Muestra (experto) u oculta (basico) las columnas tecnicas."""
        for col, (key, _) in enumerate(COLUMNS):
            if key in _EXPERT_ONLY:
                self.setColumnHidden(col, not expert)

    def load_devices(self, devices: List[Dict[str, Any]]) -> None:
        self._loading = True
        self.setSortingEnabled(False)
        self.setRowCount(0)

        for row_idx, dev in enumerate(devices):
            self.insertRow(row_idx)
            is_connected = bool(dev.get("connected"))
            for col_idx, (key, _) in enumerate(COLUMNS):
                if key == "trusted":
                    self.setItem(row_idx, col_idx, self._trust_item(dev))
                    continue
                if key == "connected":
                    value = "Conectado" if is_connected else "Desconectado"
                elif key in _DATE_COLUMNS:
                    value = _format_date(dev.get(key) or "") or "—"
                else:
                    value = dev.get(key) or "—"
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if "[DEMO]" in str(dev.get("friendly_name", "")):
                    item.setForeground(QColor("#b05800"))
                if key == "connected":
                    item.setForeground(QColor("#1a7a1a") if is_connected else QColor("#999"))
                self.setItem(row_idx, col_idx, item)

        self.setSortingEnabled(True)
        self._loading = False

    def _trust_item(self, dev: Dict[str, Any]) -> QTableWidgetItem:
        """Celda con checkbox de confianza, guardando el serial en UserRole."""
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                      | Qt.ItemFlag.ItemIsEnabled
                      | Qt.ItemFlag.ItemIsSelectable)
        checked = bool(dev.get("trusted"))
        item.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, dev.get("serial") or "")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Emite trust_changed cuando el usuario marca/desmarca la casilla."""
        if self._loading:
            return
        col_key = COLUMNS[item.column()][0]
        if col_key != "trusted":
            return
        serial = item.data(Qt.ItemDataRole.UserRole) or ""
        if serial:
            self.trust_changed.emit(
                serial, item.checkState() == Qt.CheckState.Checked)
