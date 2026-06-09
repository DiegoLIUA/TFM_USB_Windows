"""
Tests del formato de fechas para presentacion (formatting.fecha_es): conversion
del formato interno ISO (aaaa-mm-dd) al espanol (dd-mm-aaaa) sin alterar valores
que no son fechas reconocibles.
"""

import pytest

from formatting import fecha_es


@pytest.mark.parametrize("entrada,esperado", [
    ("2026-06-08 13:37:09", "08-06-2026 13:37:09"),  # fecha con hora
    ("2026-06-08", "08-06-2026"),                     # solo fecha
    ("2026-12-31 23:59:59", "31-12-2026 23:59:59"),   # fin de ano
    ("2026-01-01", "01-01-2026"),                      # inicio de ano
])
def test_convierte_iso_a_espanol(entrada, esperado):
    assert fecha_es(entrada) == esperado


@pytest.mark.parametrize("entrada", [
    "", "—", "texto cualquiera", "no-es-fecha", "08/06/2026",
])
def test_valores_no_iso_se_dejan_intactos(entrada):
    assert fecha_es(entrada) == entrada


def test_none_devuelve_cadena_vacia():
    assert fecha_es(None) == ""


def test_no_altera_orden_de_dia_y_mes():
    # Dia y mes distintos para descartar confusiones: 03 (dia) y 11 (mes).
    assert fecha_es("2026-11-03") == "03-11-2026"
