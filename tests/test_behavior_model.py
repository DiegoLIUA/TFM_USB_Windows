"""
Tests del motor de comportamiento (analytics.behavior_model): los tres
componentes explicables de la deteccion de anomalias —rareza horaria por
vecindad, frecuencia de dispositivo y distancia de Mahalanobis— y su
serializacion para persistencia.
"""

import numpy as np

from analytics.behavior_model import (
    HourHistogram, SerialFrequency, MahalanobisModel,
    session_features,
)


def _sesiones_hora(pares):
    """Construye sesiones {connected} a partir de pares (hora, repeticiones)."""
    out = []
    for hh, n in pares:
        out.extend({"connected": f"2026-06-01 {hh:02d}:30:00"} for _ in range(n))
    return out


# --- HourHistogram: rareza por vecindad --------------------------------------

def test_histograma_vacio_no_marca_nada():
    h = HourHistogram()
    assert h.score({"connected": "2026-06-08 12:00:00"}) == 0.0


def test_hora_en_el_pico_no_es_rara():
    h = HourHistogram()
    h.fit(_sesiones_hora([(13, 8), (14, 4), (11, 3)]))
    assert h.score({"connected": "2026-06-08 13:30:00"}) == 0.0


def test_hora_contigua_al_pico_es_poco_rara():
    """
    Clave del suavizado por vecindad: una hora pegada al pico (12 h, con el pico
    en 13 h) debe puntuar bajo aunque no haya conexiones en ese bin exacto.
    """
    h = HourHistogram()
    h.fit(_sesiones_hora([(13, 8), (14, 4), (11, 3), (10, 2)]))
    rareza_12 = h.score({"connected": "2026-06-08 12:35:00"})
    rareza_03 = h.score({"connected": "2026-06-08 03:35:00"})
    assert rareza_12 < 0.3          # contigua al pico: poco rara
    assert rareza_03 > 0.8          # madrugada lejana: muy rara
    assert rareza_12 < rareza_03    # coherencia relativa


def test_histograma_serializa_y_restaura():
    h = HourHistogram()
    h.fit(_sesiones_hora([(9, 5), (18, 2)]))
    h2 = HourHistogram.from_dict(h.to_dict())
    assert h2.total == h.total
    probe = {"connected": "2026-06-08 09:30:00"}
    assert h2.score(probe) == h.score(probe)


def test_hora_invalida_devuelve_cero():
    h = HourHistogram()
    h.fit(_sesiones_hora([(13, 5)]))
    assert h.score({"connected": "fecha-invalida"}) == 0.0
    assert h.score({}) == 0.0


# --- SerialFrequency: penalizacion por dispositivo poco visto ----------------

def test_dispositivo_nunca_visto_es_maximo():
    f = SerialFrequency()
    f.fit([{"serial": "CONOCIDO"}] * 5)
    assert f.score({"serial": "DESCONOCIDO"}) == 1.0


def test_dispositivo_frecuente_baja_su_rareza():
    f = SerialFrequency()
    # 'A' es el mas frecuente (referencia), 'B' aparece menos -> mas raro que A
    f.fit([{"serial": "A"}] * 10 + [{"serial": "B"}] * 2)
    rar_a = f.score({"serial": "A"})
    rar_b = f.score({"serial": "B"})
    assert rar_a == 0.0          # el mas frecuente: rareza minima
    assert 0.0 < rar_b <= 1.0    # menos frecuente: algo de rareza
    assert rar_b > rar_a


def test_sin_serial_o_sin_datos_es_maximo():
    f = SerialFrequency()
    assert f.score({"serial": ""}) == 1.0       # sin serial
    assert f.score({"serial": "X"}) == 1.0      # modelo sin entrenar


def test_frecuencia_serializa_y_restaura():
    f = SerialFrequency()
    f.fit([{"serial": "A"}] * 3 + [{"serial": "B"}])
    f2 = SerialFrequency.from_dict(f.to_dict())
    assert f2.score({"serial": "A"}) == f.score({"serial": "A"})
    assert f2.total == f.total


# --- MahalanobisModel: desviacion multivariable ------------------------------

def test_mahalanobis_sin_ajuste_es_cero():
    m = MahalanobisModel()
    assert m.score_vector(np.array([13.0, 30.0, 1.0])) == 0.0


def test_mahalanobis_pocas_muestras_no_ajusta():
    m = MahalanobisModel()
    m.fit([np.array([1.0, 2.0, 3.0]), np.array([1.1, 2.1, 3.1])])  # <3
    assert m.mean is None
    assert m.score_vector(np.array([99.0, 99.0, 99.0])) == 0.0


def test_mahalanobis_outlier_puntua_mas_que_centro():
    m = MahalanobisModel()
    rng = np.random.default_rng(0)
    # Nube compacta alrededor de (13, 30, 1)
    vecs = [np.array([13.0, 30.0, 1.0]) + rng.normal(0, 0.5, 3)
            for _ in range(30)]
    m.fit(vecs)
    centro = m.score_vector(np.array([13.0, 30.0, 1.0]))
    outlier = m.score_vector(np.array([3.0, 600.0, 90.0]))
    assert outlier > centro
    assert 0.0 <= outlier <= 1.0    # saturado y normalizado


def test_mahalanobis_serializa_y_restaura():
    m = MahalanobisModel()
    vecs = [np.array([13.0, 30.0, 1.0]) + np.array([i * 0.1, i * 0.2, i * 0.05])
            for i in range(5)]
    m.fit(vecs)
    m2 = MahalanobisModel.from_dict(m.to_dict())
    v = np.array([14.0, 35.0, 2.0])
    assert abs(m2.score_vector(v) - m.score_vector(v)) < 1e-9


# --- session_features: extraccion del vector de caracteristicas --------------

def test_session_features_calcula_vector():
    v = session_features(
        {"connected": "2026-06-08 13:30:00",
         "disconnected": "2026-06-08 14:00:00"},
        last_seen_for_serial="2026-06-06 13:30:00")
    assert v is not None
    assert v[0] == 13.5            # hora con fraccion
    assert v[1] == 30.0           # duracion en minutos
    assert v[2] == 2.0            # dias desde la ultima vez


def test_session_features_sin_conexion_es_none():
    assert session_features({"connected": None}) is None
    assert session_features({}) is None
