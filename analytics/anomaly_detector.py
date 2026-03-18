"""
Motor de detección de anomalías (placeholder).
La implementación completa se desarrollará en la fase de IA + Prevención.
Actualmente devuelve un score neutro con explicación vacía.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Placeholder del motor de anomalías.
    Interfaz pública estable para integración futura.
    """

    def __init__(self) -> None:
        self._trained = False
        logger.info("AnomalyDetector inicializado (modo placeholder).")

    def train(self, device_history: List[Dict[str, Any]]) -> None:
        """Entrena el modelo con el historial de dispositivos. No implementado aún."""
        logger.info("train() llamado — pendiente de implementación.")
        self._trained = True

    def score(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """
        Devuelve un score de anomalía para un dispositivo.
        Retorna 0.0 (sin anomalía) hasta la implementación real.
        """
        return {
            "score":       0.0,
            "anomaly":     False,
            "explanation": "Módulo de anomalías pendiente de implementación.",
            "components":  {},
        }

    def is_trained(self) -> bool:
        return self._trained
