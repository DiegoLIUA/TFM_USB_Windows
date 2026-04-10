"""
Barra de filtros para la tabla de dispositivos.
Permite filtrar por rango de fechas y por texto (serial/nombre).
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QDateEdit, QLineEdit, QPushButton,
)
from PyQt6.QtCore import pyqtSignal, QDate


class FilterBar(QWidget):
    """Barra de filtros con fecha desde, fecha hasta y texto libre."""
    filter_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(2020, 1, 1))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_from)

        layout.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_to)

        layout.addWidget(QLabel("Buscar:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Serial o nombre del dispositivo...")
        self.search_box.setMinimumWidth(200)
        layout.addWidget(self.search_box)

        self.btn_filter = QPushButton("Filtrar")
        self.btn_filter.clicked.connect(self.filter_changed.emit)
        layout.addWidget(self.btn_filter)

        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.clicked.connect(self._clear_filters)
        layout.addWidget(self.btn_clear)

        layout.addStretch()

    def _clear_filters(self) -> None:
        """Restablece los filtros a sus valores por defecto."""
        self.date_from.setDate(QDate(2020, 1, 1))
        self.date_to.setDate(QDate.currentDate())
        self.search_box.clear()
        self.filter_changed.emit()

    def get_filters(self) -> dict:
        """Devuelve los filtros actuales como diccionario."""
        return {
            "date_from": self.date_from.date().toString("yyyy-MM-dd") + " 00:00:00",
            "date_to": self.date_to.date().toString("yyyy-MM-dd") + " 23:59:59",
            "search": self.search_box.text().strip() or None,
        }
