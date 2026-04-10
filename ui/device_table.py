"""
Widget de tabla para mostrar los dispositivos USB detectados.
"""

from typing import List, Dict, Any

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

COLUMNS = [
    ("friendly_name", "Nombre del dispositivo"),
    ("serial",        "Número de serie"),
    ("vendor_id",     "Vendor ID"),
    ("product_id",    "Product ID"),
    ("first_seen",    "Primera conexión"),
    ("last_seen",     "Última conexión"),
    ("sources",       "Fuentes"),
]


class DeviceTable(QTableWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_table()

    def _setup_table(self) -> None:
        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels([label for _, label in COLUMNS])
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    def load_devices(self, devices: List[Dict[str, Any]]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)

        for row_idx, dev in enumerate(devices):
            self.insertRow(row_idx)
            for col_idx, (key, _) in enumerate(COLUMNS):
                value = dev.get(key) or "—"
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                # Resaltar filas de datos simulados (DEMO)
                if "[DEMO]" in str(dev.get("friendly_name", "")):
                    item.setForeground(QColor("#b05800"))
                self.setItem(row_idx, col_idx, item)

        self.setSortingEnabled(True)
