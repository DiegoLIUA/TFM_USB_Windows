"""
Diálogo de selección y apertura del informe HTML generado.
"""

import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QHBoxLayout,
)
from PyQt6.QtCore import Qt


class ReportViewerDialog(QDialog):
    def __init__(self, report_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.report_path = report_path
        self.setWindowTitle("Informe generado")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        label = QLabel(f"Informe guardado en:\n<b>{self.report_path}</b>")
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        layout.addWidget(label)

        btn_row = QHBoxLayout()
        btn_open = QPushButton("Abrir en navegador")
        btn_open.clicked.connect(self._open_in_browser)
        btn_save = QPushButton("Guardar en otra ubicación…")
        btn_save.clicked.connect(self._save_as)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_open)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _open_in_browser(self) -> None:
        if sys.platform == "win32":
            subprocess.Popen(["start", "", str(self.report_path)], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(self.report_path)])
        else:
            subprocess.Popen(["xdg-open", str(self.report_path)])

    def _save_as(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(
            self, "Guardar informe", str(self.report_path), "HTML (*.html)"
        )
        if dest:
            Path(dest).write_bytes(self.report_path.read_bytes())
