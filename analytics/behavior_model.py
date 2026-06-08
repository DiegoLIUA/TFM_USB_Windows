"""
Modelo de comportamiento USB para deteccion de anomalias.
Tres componentes:
- HourHistogram: rareza temporal por hora del dia.
- SerialFrequency: penalizacion por dispositivo poco visto.
- MahalanobisModel: desviacion multivariable (hora, duracion, dias_desde_ultima).
Todos serializables a/desde dict para persistencia en SQLite.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, Any, List, Optional

import numpy as np

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s, _TS_FMT)
    except (ValueError, TypeError):
        return None


def session_features(
    session: Dict[str, Any],
    last_seen_for_serial: Optional[str] = None,
) -> Optional[np.ndarray]:
    """Vector [hora, duracion_min, dias_desde_ultima] o None si datos insuficientes."""
    connected = _parse_ts(session.get("connected"))
    if connected is None:
        return None
    hour = connected.hour + connected.minute / 60.0
    disconnected = _parse_ts(session.get("disconnected"))
    duration_min = ((disconnected - connected).total_seconds() / 60.0
                    if disconnected else 0.0)
    last = _parse_ts(last_seen_for_serial)
    days_since = ((connected - last).total_seconds() / 86400.0
                  if last and last < connected else 0.0)
    return np.array([hour, max(duration_min, 0.0), max(days_since, 0.0)],
                    dtype=float)


class HourHistogram:
    """
    Histograma circular de 24 bins. La rareza de una hora no se mide solo por
    su bin exacto, sino por su entorno: se aplica un suavizado por vecindad
    (ventana +-WINDOW horas, con decaimiento) antes de normalizar. Asi una hora
    contigua al pico de actividad hereda densidad y deja de considerarse rara,
    aunque nunca se haya conectado un USB exactamente en ese bin. Score = rareza
    relativa al bin mas denso, en [0, 1].
    """

    WINDOW = 2  # horas de vecindad consideradas a cada lado

    def __init__(self) -> None:
        self.counts = np.zeros(24, dtype=float)
        self.total = 0

    def fit(self, sessions: List[Dict[str, Any]]) -> None:
        for s in sessions:
            ts = _parse_ts(s.get("connected"))
            if ts is None:
                continue
            self.counts[ts.hour] += 1
            self.total += 1

    def _smoothed_density(self) -> np.ndarray:
        """Densidad por bin difundida a las horas vecinas (kernel triangular)."""
        dens = np.zeros(24, dtype=float)
        for offset in range(-self.WINDOW, self.WINDOW + 1):
            peso = 1.0 - abs(offset) / (self.WINDOW + 1)
            dens += np.roll(self.counts, offset) * peso
        return dens + 1.0  # suavizado de Laplace para evitar ceros

    def score(self, session: Dict[str, Any]) -> float:
        ts = _parse_ts(session.get("connected"))
        if ts is None or self.total == 0:
            return 0.0
        dens = self._smoothed_density()
        prob = dens[ts.hour] / dens.sum()
        max_prob = dens.max() / dens.sum()
        return float(min(1.0, 1.0 - (prob / max_prob)))

    def to_dict(self) -> Dict[str, Any]:
        return {"counts": self.counts.tolist(), "total": self.total}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HourHistogram":
        h = cls()
        h.counts = np.array(data.get("counts", [0.0] * 24), dtype=float)
        h.total = int(data.get("total", 0))
        return h


class SerialFrequency:
    """Penalizacion por baja frecuencia. Nunca visto = 1.0."""

    def __init__(self) -> None:
        self.counts: Dict[str, int] = {}
        self.total = 0

    def fit(self, sessions: List[Dict[str, Any]]) -> None:
        for s in sessions:
            serial = (s.get("serial") or "").strip()
            if not serial:
                continue
            self.counts[serial] = self.counts.get(serial, 0) + 1
            self.total += 1

    def score(self, session: Dict[str, Any]) -> float:
        serial = (session.get("serial") or "").strip()
        if not serial or self.total == 0:
            return 1.0
        c = self.counts.get(serial, 0)
        if c == 0:
            return 1.0
        max_c = max(self.counts.values())
        return float(max(0.0, 1.0 - (c / max_c)))

    def to_dict(self) -> Dict[str, Any]:
        return {"counts": self.counts, "total": self.total}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SerialFrequency":
        m = cls()
        m.counts = dict(data.get("counts", {}))
        m.total = int(data.get("total", 0))
        return m


class MahalanobisModel:
    """Distancia de Mahalanobis al centroide. Saturada y normalizada en [0, 1]."""

    SAT = 6.0  # umbral de saturacion (chi-cuadrado 3 gl, p<0.1)

    def __init__(self) -> None:
        self.mean: Optional[np.ndarray] = None
        self.inv_cov: Optional[np.ndarray] = None

    def fit(self, vectors: List[np.ndarray]) -> None:
        if len(vectors) < 3:
            return
        X = np.vstack(vectors)
        self.mean = X.mean(axis=0)
        cov = np.cov(X, rowvar=False) + np.eye(X.shape[1]) * 1e-3
        try:
            self.inv_cov = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            self.inv_cov = None

    def score_vector(self, v: np.ndarray) -> float:
        if self.mean is None or self.inv_cov is None:
            return 0.0
        diff = v - self.mean
        d2 = float(diff @ self.inv_cov @ diff.T)
        if d2 < 0 or math.isnan(d2):
            return 0.0
        return float(min(1.0, math.sqrt(d2) / self.SAT))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean": self.mean.tolist() if self.mean is not None else None,
            "inv_cov": self.inv_cov.tolist() if self.inv_cov is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MahalanobisModel":
        m = cls()
        if data.get("mean") is not None:
            m.mean = np.array(data["mean"], dtype=float)
        if data.get("inv_cov") is not None:
            m.inv_cov = np.array(data["inv_cov"], dtype=float)
        return m
