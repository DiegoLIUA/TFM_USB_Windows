"""
Dashboard de estadisticas: graficas a partir de las senales del sistema.
Incrusta un lienzo matplotlib en PyQt6. Boton de refresco manual.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from analytics import stats

logger = logging.getLogger(__name__)

_AZUL = "#1f6feb"
_GRIS = "#57606a"


class DashboardView(QWidget):
    """Panel con cuatro graficas de uso del equipo y dispositivos."""

    def __init__(self, parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("<b>Estadísticas de uso del sistema</b>"))
        bar.addStretch()
        btn = QPushButton("Actualizar")
        btn.setObjectName("primaryButton")
        btn.setFixedHeight(32)
        btn.clicked.connect(self.refresh)
        bar.addWidget(btn)
        root.addLayout(bar)

        self.figure = Figure(figsize=(8, 6), facecolor="#ffffff")
        self.canvas = FigureCanvasQTAgg(self.figure)
        root.addWidget(self.canvas)

    def refresh(self) -> None:
        """Recalcula las agregaciones y redibuja las graficas."""
        self.figure.clear()
        try:
            self._draw_usage_by_hour(self.figure.add_subplot(2, 2, 1))
            self._draw_suspensions(self.figure.add_subplot(2, 2, 2))
            self._draw_top_apps(self.figure.add_subplot(2, 2, 3))
            self._draw_avg_duration(self.figure.add_subplot(2, 2, 4))
            self.figure.tight_layout()
        except Exception as exc:
            logger.warning("Error dibujando dashboard: %s", exc)
        self.canvas.draw()

    def _draw_usage_by_hour(self, ax) -> None:
        data = stats.usage_by_hour()
        ax.bar(range(24), data, color=_AZUL)
        ax.set_title("Actividad por hora del día")
        ax.set_xlabel("Hora")
        ax.set_ylabel("Muestras activas")
        ax.set_xticks(range(0, 24, 3))

    def _draw_suspensions(self, ax) -> None:
        data = stats.suspensions_by_day()
        if data:
            dias = list(data.keys())[-10:]
            vals = [data[d] for d in dias]
            etiquetas = [d[5:] for d in dias]  # MM-DD
            ax.bar(etiquetas, vals, color=_GRIS)
            ax.tick_params(axis="x", labelrotation=45, labelsize=7)
        else:
            _empty(ax)
        ax.set_title("Suspensiones por día")
        ax.set_ylabel("Nº suspensiones")

    def _draw_top_apps(self, ax) -> None:
        data = stats.top_apps(n=6)
        if data:
            nombres = [a[:14] for a, _ in data][::-1]
            vals = [c for _, c in data][::-1]
            ax.barh(nombres, vals, color=_AZUL)
            ax.tick_params(axis="y", labelsize=8)
        else:
            _empty(ax)
        ax.set_title("Aplicaciones más usadas")
        ax.set_xlabel("Muestras en primer plano")

    def _draw_avg_duration(self, ax) -> None:
        data = stats.median_duration_top_storage(n=3)
        if data:
            nombres = [n[:16] for n, _ in data][::-1]
            vals = [m for _, m in data][::-1]
            ax.barh(nombres, vals, color=_GRIS)
            ax.tick_params(axis="y", labelsize=8)
            for i, v in enumerate(vals):
                ax.text(v, i, f" {v:.0f} min", va="center", fontsize=8)
        else:
            _empty(ax)
        ax.set_title("Duración típica de uso (almacenamiento)")
        ax.set_xlabel("Minutos por sesión (mediana)")


def _empty(ax) -> None:
    """Muestra un mensaje cuando no hay datos para la grafica."""
    ax.text(0.5, 0.5, "Sin datos todavía", ha="center", va="center",
            transform=ax.transAxes, color=_GRIS)
    ax.set_xticks([]); ax.set_yticks([])
