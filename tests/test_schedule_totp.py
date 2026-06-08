"""
Tests de horario habitual (franjas, dias, cruce de medianoche) y TOTP.
Usan la BD temporal porque la configuracion se persiste en config.
"""

from datetime import datetime

from security import schedule, totp


def test_franja_normal(temp_db):
    schedule.set_schedule("08:00", "22:00", [0, 1, 2, 3, 4], enforce=True)
    # Lunes 10:00 -> dentro
    assert schedule.is_within_schedule(datetime(2026, 5, 4, 10, 0)) is True
    # Lunes 03:00 -> fuera
    assert schedule.is_within_schedule(datetime(2026, 5, 4, 3, 0)) is False
    # Sabado 10:00 -> fuera (no es dia laborable)
    assert schedule.is_within_schedule(datetime(2026, 5, 9, 10, 0)) is False


def test_franja_cruza_medianoche(temp_db):
    schedule.set_schedule("22:00", "06:00", list(range(7)), enforce=True)
    assert schedule.is_within_schedule(datetime(2026, 5, 4, 23, 0)) is True
    assert schedule.is_within_schedule(datetime(2026, 5, 4, 2, 0)) is True
    assert schedule.is_within_schedule(datetime(2026, 5, 4, 12, 0)) is False


def test_anomalo_solo_si_enforce(temp_db):
    schedule.set_schedule("08:00", "22:00", [0, 1, 2, 3, 4], enforce=False)
    # 03:00 lunes esta fuera, pero enforce=False => no es anomalo
    assert schedule.is_anomalous_time(datetime(2026, 5, 4, 3, 0)) is False
    schedule.set_schedule("08:00", "22:00", [0, 1, 2, 3, 4], enforce=True)
    assert schedule.is_anomalous_time(datetime(2026, 5, 4, 3, 0)) is True


def test_totp_generar_y_verificar(temp_db):
    assert totp.is_configured() is False
    totp.generate_secret()
    assert totp.is_configured() is True
    code = totp.current_code()
    assert totp.verify(code) is True
    assert totp.verify("000000") is False


def test_totp_uri_y_qr(temp_db):
    totp.generate_secret()
    uri = totp.get_provisioning_uri()
    assert uri.startswith("otpauth://totp/")
    png = totp.qr_png_bytes(uri)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_margen_zona_tolerancia(temp_db):
    # Horario 10:00-15:00 con margen 2 h -> zona tolerada 08:00-17:00
    schedule.set_schedule("10:00", "15:00", list(range(7)), margin_h=2)
    lun = lambda h: datetime(2026, 6, 8, h, 0)  # noqa: E731 (lunes)
    # Dentro del horario: no anomalo
    assert schedule.is_anomalous_schedule(lun(12)) is False
    # En la zona de tolerancia (margen): no anomalo
    assert schedule.is_anomalous_schedule(lun(8)) is False
    assert schedule.is_anomalous_schedule(lun(16)) is False
    # Fuera del horario ampliado: anomalo
    assert schedule.is_anomalous_schedule(lun(7)) is True
    assert schedule.is_anomalous_schedule(lun(18)) is True
    assert schedule.is_anomalous_schedule(lun(3)) is True


def test_margen_cero_equivale_a_franja(temp_db):
    # Con margen 0, anomalo == fuera de la franja exacta
    schedule.set_schedule("10:00", "15:00", list(range(7)), margin_h=0)
    assert schedule.is_anomalous_schedule(datetime(2026, 6, 8, 15, 30)) is True
    assert schedule.is_anomalous_schedule(datetime(2026, 6, 8, 12, 0)) is False


def test_politica_confianza_horario(temp_db):
    """Politica Zero Trust: solo pasa el confiable dentro de horario."""
    from store.database import upsert_device, set_device_trusted
    from monitoring.monitor_cycle import _evaluate
    upsert_device({"vendor_id": "1234", "product_id": "5678", "serial": "SN1",
                   "friendly_name": "X", "device_type": "almacenamiento",
                   "first_seen": "2026-06-01 10:00:00",
                   "last_seen": "2026-06-01 10:00:00"})
    # Horario amplio: siempre dentro
    schedule.set_schedule("00:00", "23:59", list(range(7)), margin_h=0)
    # Confiable dentro de horario -> permitido (sin motivo)
    set_device_trusted("SN1", True)
    motivo, _ = _evaluate("SN1")
    assert motivo == ""
    # No confiable dentro de horario -> bloqueado por confianza
    set_device_trusted("SN1", False)
    motivo, comp = _evaluate("SN1")
    assert "no confiable" in motivo
    assert comp["device_rarity"] == 1.0
