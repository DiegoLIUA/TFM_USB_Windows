"""
Motor de deteccion de anomalias USB.
Score = 0.4*rareza_horaria + 0.3*dispositivo_desconocido + 0.3*mahalanobis.
Resultado siempre explicable por componentes individuales.
Modo degradado (reglas simples) si no hay suficientes datos para entrenar.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from analytics.behavior_model import (
    HourHistogram, SerialFrequency, MahalanobisModel, session_features,
)

logger = logging.getLogger(__name__)

MODEL_VERSION = 1
W_HOUR, W_FREQ, W_MAHA = 0.4, 0.3, 0.3
_TS_FMT = "%Y-%m-%d %H:%M:%S"


class AnomalyDetector:
    """Motor de anomalias con 3 componentes y persistencia JSON."""

    def __init__(self) -> None:
        self.hour = HourHistogram()
        self.freq = SerialFrequency()
        self.maha = MahalanobisModel()
        self._last_seen: Dict[str, str] = {}
        self._trained = False
        self._degraded = False
        self._n_sessions = 0

    def train(
        self,
        sessions: List[Dict[str, Any]],
        train_days: int = 7,
    ) -> bool:
        """Entrena con sesiones de los ultimos train_days. Devuelve True si OK."""
        cutoff = datetime.now() - timedelta(days=train_days)
        recent = [s for s in sessions if _after(s.get("connected"), cutoff)]
        self._n_sessions = len(recent)
        if self._n_sessions < 5:
            logger.info("Datos insuficientes (%d sesiones): modo degradado.",
                        self._n_sessions)
            self._degraded = True
            self._trained = False
            self._build_last_seen(sessions)
            return False
        self.hour.fit(recent)
        self.freq.fit(recent)
        self._build_last_seen(recent)
        vectors = []
        for s in recent:
            v = session_features(s, self._last_seen.get(s.get("serial", "")))
            if v is not None:
                vectors.append(v)
        self.maha.fit(vectors)
        self._trained = True
        self._degraded = False
        logger.info("Modelo entrenado con %d sesiones.", self._n_sessions)
        return True

    def _build_last_seen(self, sessions: List[Dict[str, Any]]) -> None:
        for s in sorted(sessions, key=lambda x: x.get("connected") or ""):
            sn = (s.get("serial") or "").strip()
            ts = s.get("connected")
            if sn and ts:
                self._last_seen[sn] = ts

    def explain(self, session: Dict[str, Any]) -> Dict[str, float]:
        """Devuelve los 3 componentes individuales del score."""
        if self._degraded or not self._trained:
            return _degraded_components(session, self._last_seen)
        h = self.hour.score(session)
        f = self.freq.score(session)
        v = session_features(session, self._last_seen.get(session.get("serial", "")))
        m = self.maha.score_vector(v) if v is not None else 0.0
        return {"hour_rarity": h, "device_rarity": f, "mahalanobis": m}

    def score(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Score agregado en [0,1] con sus componentes."""
        comp = self.explain(session)
        agg = (W_HOUR * comp["hour_rarity"]
               + W_FREQ * comp["device_rarity"]
               + W_MAHA * comp["mahalanobis"])
        return {
            "score":      float(round(agg, 4)),
            "components": {k: float(round(v, 4)) for k, v in comp.items()},
            "degraded":   self._degraded,
        }

    def to_payload(self) -> str:
        return json.dumps({
            "version":    MODEL_VERSION,
            "hour":       self.hour.to_dict(),
            "freq":       self.freq.to_dict(),
            "maha":       self.maha.to_dict(),
            "last_seen":  self._last_seen,
            "trained":    self._trained,
            "degraded":   self._degraded,
            "n_sessions": self._n_sessions,
        })

    @classmethod
    def from_payload(cls, payload: str) -> "AnomalyDetector":
        d = json.loads(payload)
        a = cls()
        a.hour = HourHistogram.from_dict(d.get("hour", {}))
        a.freq = SerialFrequency.from_dict(d.get("freq", {}))
        a.maha = MahalanobisModel.from_dict(d.get("maha", {}))
        a._last_seen = dict(d.get("last_seen", {}))
        a._trained = bool(d.get("trained", False))
        a._degraded = bool(d.get("degraded", False))
        a._n_sessions = int(d.get("n_sessions", 0))
        return a

    def is_trained(self) -> bool:
        return self._trained

    def is_degraded(self) -> bool:
        return self._degraded

    def n_sessions(self) -> int:
        """Numero de sesiones con las que se entreno el modelo."""
        return self._n_sessions


def _after(ts: Optional[str], cutoff: datetime) -> bool:
    if not ts:
        return False
    try:
        return datetime.strptime(ts, _TS_FMT) >= cutoff
    except (ValueError, TypeError):
        return False


def _degraded_components(
    session: Dict[str, Any],
    last_seen: Dict[str, str],
) -> Dict[str, float]:
    """Reglas simples cuando no hay suficientes datos."""
    h = 0.0
    try:
        ts = datetime.strptime(session.get("connected") or "", _TS_FMT)
        h = 0.7 if (ts.hour < 7 or ts.hour > 22) else 0.0
    except (ValueError, TypeError):
        pass
    serial = (session.get("serial") or "").strip()
    f = 1.0 if serial and serial not in last_seen else 0.0
    return {"hour_rarity": h, "device_rarity": f, "mahalanobis": 0.0}


def severity_from_score(score: float, threshold: float) -> Optional[str]:
    """
    Convierte score numerico en severidad. None si no supera el umbral de
    alerta. Las bandas de severidad son fijas y dependen solo del score, para
    que un mismo valor siempre signifique lo mismo: alta >0,75; media [0,5;
    0,75]; baja <0,5.
    """
    if score < threshold:
        return None
    if score > 0.75:
        return "alta"
    if score >= 0.5:
        return "media"
    return "baja"


def reason_from_components(components: Dict[str, float]) -> str:
    """Mensaje legible con el componente dominante."""
    items = sorted(components.items(), key=lambda x: x[1], reverse=True)
    top = items[0] if items else ("", 0.0)
    label = {
        "hour_rarity":   "hora poco habitual",
        "device_rarity": "dispositivo poco visto",
        "mahalanobis":   "patron multivariable atipico",
    }.get(top[0], top[0])
    return f"{label} ({top[1]:.2f})"


def explain_to_dict(score_result: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    """Helper para extraer (score, componentes)."""
    return score_result.get("score", 0.0), score_result.get("components", {})
