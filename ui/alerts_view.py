"""
Vista de alertas: tabla con filtros por fecha y dispositivo.
Muestra fecha, dispositivo, score, severidad y desglose de componentes.
"""

import json
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

from store.anomaly_store import get_alerts

_COLUMNS = [
    ("timestamp",  "Fecha"),
    ("friendly_name", "Dispositivo"),
    ("serial",     "Serial"),
    ("severity",   "Severidad"),
    ("score",      "Score"),
    ("reason",     "Motivo"),
    ("breakdown",  "Desglose"),
]

_SEVERITY_COLOR = {
    "alta":  QColor("#c0392b"),
    "media": QColor("#d97400"),
    "baja":  QColor("#7d6608"),
}


class AlertsView(QWidget):
    """Tabla de alertas con barra de filtros propia."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setDisplayFormat("dd-MM-yyyy")
        self.date_from.setMinimumWidth(120)
        bar.addWidget(self.date_from)

        bar.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("dd-MM-yyyy")
        self.date_to.setMinimumWidth(120)
        bar.addWidget(self.date_to)

        bar.addWidget(QLabel("Dispositivo:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Serial o nombre...")
        self.search_box.setMinimumWidth(180)
        bar.addWidget(self.search_box)

        btn = QPushButton("Filtrar"); btn.clicked.connect(self.refresh)
        bar.addWidget(btn)
        clr = QPushButton("Limpiar"); clr.clicked.connect(self._clear)
        bar.addWidget(clr)
        bar.addStretch()
        root.addLayout(bar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([h for _, h in _COLUMNS])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        for col in range(len(_COLUMNS)):
            self.table.setColumnWidth(col, 130)
        vh = self.table.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        vh.setDefaultSectionSize(28)
        root.addWidget(self.table)

        self.lbl_summary = QLabel("")
        root.addWidget(self.lbl_summary)

    def _clear(self) -> None:
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_to.setDate(QDate.currentDate())
        self.search_box.clear()
        self.refresh()

    def refresh(self) -> None:
        df = self.date_from.date().toString("yyyy-MM-dd") + " 00:00:00"
        dt = self.date_to.date().toString("yyyy-MM-dd") + " 23:59:59"
        rows = get_alerts(date_from=df, date_to=dt)
        text = (self.search_box.text() or "").strip().lower()
        if text:
            rows = [r for r in rows
                    if text in (r.get("friendly_name") or "").lower()
                    or text in (r.get("serial") or "").lower()]
        self._populate(rows)

    def _populate(self, alerts: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(0)
        for i, a in enumerate(alerts):
            self.table.insertRow(i)
            comp = _format_components(a.get("components"))
            display = {
                "timestamp":     a.get("timestamp") or "",
                "friendly_name": a.get("friendly_name") or "—",
                "serial":        a.get("serial") or "—",
                "severity":      (a.get("severity") or "").upper(),
                "score":         f"{(a.get('score') or 0):.2f}",
                "reason":        a.get("reason") or "",
                "breakdown":     comp,
            }
            for col, (key, _) in enumerate(_COLUMNS):
                item = QTableWidgetItem(str(display.get(key, "")))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if key == "severity":
                    color = _SEVERITY_COLOR.get((a.get("severity") or "").lower())
                    if color:
                        item.setForeground(color)
                self.table.setItem(i, col, item)
        self.lbl_summary.setText(f"{len(alerts)} alerta(s) encontradas.")


def _format_components(raw: Any) -> str:
    """Convierte el JSON de componentes a texto legible."""
    if not raw:
        return ""
    try:
        d = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return ""
    parts = [f"hora={d.get('hour_rarity', 0):.2f}",
             f"disp={d.get('device_rarity', 0):.2f}",
             f"maha={d.get('mahalanobis', 0):.2f}"]
    return " | ".join(parts)
