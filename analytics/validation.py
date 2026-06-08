"""
Validacion experimental del detector de anomalias.
Genera sesiones sinteticas (comportamiento normal + anomalias inyectadas),
entrena el modelo y calcula precision, recall, F1 y matriz de confusion.
No depende de la BD ni de Qt: usa el detector en memoria.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

from analytics.anomaly_detector import AnomalyDetector, severity_from_score

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def _session(serial: str, day_offset: int, hour: int,
             dur_min: int, base: datetime) -> Dict[str, Any]:
    t = (base - timedelta(days=day_offset)).replace(
        hour=hour, minute=0, second=0, microsecond=0)
    return {
        "serial": serial,
        "connected": t.strftime(_TS_FMT),
        "disconnected": (t + timedelta(minutes=dur_min)).strftime(_TS_FMT),
    }


def make_normal_sessions(n_days: int = 21, seed: int = 42) -> List[Dict[str, Any]]:
    """Comportamiento normal: pocos USB habituales en horario laboral."""
    rng = random.Random(seed)
    base = datetime(2026, 5, 25, 12, 0, 0)
    serials = ["USB_TRABAJO", "USB_BACKUP"]
    out: List[Dict[str, Any]] = []
    for d in range(n_days):
        for _ in range(rng.randint(2, 4)):
            out.append(_session(
                rng.choice(serials), d,
                rng.choice([9, 10, 11, 14, 16, 17]),
                rng.randint(10, 60), base))
    return out


def make_test_set(seed: int = 7) -> List[Tuple[Dict[str, Any], bool]]:
    """
    Conjunto de prueba etiquetado: (sesion, es_anomala).
    Normales: USB conocido en horario laboral.
    Anomalas: USB desconocido y/o hora de madrugada.
    """
    rng = random.Random(seed)
    base = datetime(2026, 5, 25, 12, 0, 0)
    tests: List[Tuple[Dict[str, Any], bool]] = []
    for _ in range(30):
        s = _session(rng.choice(["USB_TRABAJO", "USB_BACKUP"]),
                     rng.randint(0, 5), rng.choice([9, 11, 15, 17]),
                     rng.randint(10, 50), base)
        tests.append((s, False))
    for _ in range(15):
        s = _session("USB_INTRUSO_" + str(rng.randint(1, 99)),
                     rng.randint(0, 5), rng.choice([2, 3, 4, 23]),
                     rng.randint(60, 180), base)
        tests.append((s, True))
    rng.shuffle(tests)
    return tests


def make_noisy_test_set(seed: int = 13) -> List[Tuple[Dict[str, Any], bool]]:
    """
    Conjunto de prueba REALISTA con solapamiento entre clases:
    - Normales que rozan lo atípico: USB conocido a horas límite (8 h, 19 h) o
      con duraciones largas; un caso legítimo en fin de semana / tarde-noche.
    - Anómalas sutiles: dispositivo de nombre PARECIDO a uno habitual,
      o USB conocido a una hora inusual pero no extrema (madrugada temprana).
    Este solapamiento provoca falsos positivos y falsos negativos reales.
    """
    rng = random.Random(seed)
    base = datetime(2026, 5, 25, 12, 0, 0)
    tests: List[Tuple[Dict[str, Any], bool]] = []

    # Normales claros (horario y dispositivo habituales)
    for _ in range(18):
        tests.append((_session(
            rng.choice(["USB_TRABAJO", "USB_BACKUP"]),
            rng.randint(0, 6), rng.choice([9, 10, 11, 14, 16]),
            rng.randint(10, 50), base), False))
    # Normales "frontera": dispositivo conocido a hora límite (8 h, 19-21 h).
    # Estos elevan la rareza temporal y pueden disparar falsos positivos.
    for _ in range(12):
        tests.append((_session(
            rng.choice(["USB_TRABAJO", "USB_BACKUP"]),
            rng.randint(0, 6), rng.choice([7, 8, 20, 21, 22]),
            rng.randint(20, 120), base), False))
    # Anomalas claras (desconocido + madrugada profunda)
    for _ in range(10):
        tests.append((_session(
            "USB_INTRUSO_" + str(rng.randint(1, 99)),
            rng.randint(0, 6), rng.choice([2, 3, 4]),
            rng.randint(60, 180), base), True))
    # Anomalas SUTILES: dispositivo CONOCIDO (no salta por serial nuevo) usado
    # a una hora moderadamente inusual. Solo el componente temporal las delata,
    # por lo que se solapan con los normales frontera -> falsos negativos.
    for _ in range(10):
        tests.append((_session(
            rng.choice(["USB_TRABAJO", "USB_BACKUP"]),
            rng.randint(0, 6), rng.choice([6, 7, 22, 23]),
            rng.randint(20, 70), base), True))
    rng.shuffle(tests)
    return tests


def _confusion(detector, test_set, threshold) -> Dict[str, int]:
    tp = fp = tn = fn = 0
    for session, is_anomaly in test_set:
        score = detector.score(session)["score"]
        predicted = severity_from_score(score, threshold) is not None
        if predicted and is_anomaly:
            tp += 1
        elif predicted and not is_anomaly:
            fp += 1
        elif not predicted and is_anomaly:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def _metrics(c: Dict[str, int]) -> Dict[str, float]:
    tp, fp, tn, fn = c["tp"], c["fp"], c["tn"], c["fn"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0
    # tasa de falsos positivos (para curva ROC)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "precision": round(precision, 3), "recall": round(recall, 3),
        "f1": round(f1, 3), "accuracy": round(accuracy, 3),
        "fpr": round(fpr, 3), "tpr": round(recall, 3),
    }


def evaluate(threshold: float = 0.6, noisy: bool = False) -> Dict[str, Any]:
    """
    Entrena con datos normales y evalua contra el conjunto etiquetado.
    Si noisy=True usa el conjunto con solapamiento entre clases (mas realista).
    """
    detector = AnomalyDetector()
    detector.train(make_normal_sessions(), train_days=30)
    test_set = make_noisy_test_set() if noisy else make_test_set()
    c = _confusion(detector, test_set, threshold)
    return {"threshold": threshold, "confusion": c, "degraded":
            detector.is_degraded(), **_metrics(c)}


def _print_block(titulo: str, noisy: bool) -> None:
    print("\n" + "=" * 60)
    print(f" {titulo}")
    print("=" * 60)
    for th in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        r = evaluate(th, noisy=noisy)
        c = r["confusion"]
        print(f"\nUmbral {th}:")
        print(f"  Matriz: TP={c['tp']} FP={c['fp']} "
              f"TN={c['tn']} FN={c['fn']}")
        print(f"  Precision={r['precision']}  Recall={r['recall']}  "
              f"F1={r['f1']}  Accuracy={r['accuracy']}  FPR={r['fpr']}")


def print_report() -> None:
    """Imprime los dos experimentos: ideal (separado) y realista (con ruido)."""
    _print_block("EXPERIMENTO 1 — CLASES SEPARADAS (caso ideal)", noisy=False)
    _print_block("EXPERIMENTO 2 — CON SOLAPAMIENTO (caso realista)", noisy=True)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_report()
