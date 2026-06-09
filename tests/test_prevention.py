"""
Tests de la capa de prevencion (analytics.prevention): validacion estricta de
identificadores frente a inyeccion, construccion de InstanceId, gestion de
desbloqueos de sesion y decision de bloqueo en modo estricto.

No se ejercita el bloqueo fisico real (Disable/Enable-PnpDevice requiere admin y
PowerShell); se valida la logica que decide y prepara ese bloqueo, que es donde
estan las garantias de seguridad.
"""

import pytest

from analytics import prevention


# --- Validacion de InstanceId (defensa frente a inyeccion de comandos) -------

@pytest.mark.parametrize("valido", [
    r"USB\VID_0781&PID_558C\MSFT30313831363833343030343034",
    r"USB\VID_abcd&PID_1234\ABC-123_xyz",
    r"USB\VID_FFFF&PID_0000\A",
])
def test_instance_id_valido_se_acepta(valido):
    assert prevention._validate_instance_id(valido) == valido


@pytest.mark.parametrize("malicioso", [
    "USB\\VID_0781&PID_558C\\ser; Remove-Item C:\\ -Recurse",  # inyeccion shell
    "USB\\VID_0781&PID_558C\\$(calc.exe)",                     # subexpresion PS
    "USB\\VID_0781&PID_558C\\ser`nport",                       # backtick PS
    "USB\\VID_0781&PID_558C\\ser ial",                         # espacio
    "USB\\VID_ZZZZ&PID_558C\\serial",                          # VID no hex
    "USB\\VID_0781&PID_558C\\",                                # serial vacio
    "HID\\VID_0781&PID_558C\\serial",                          # prefijo no USB
    "",                                                         # vacio
    "USB\\VID_0781&PID_558C\\" + "x" * 80,                     # serial muy largo
])
def test_instance_id_malicioso_se_rechaza(malicioso):
    assert prevention._validate_instance_id(malicioso) is None


def test_build_instance_id_normaliza_y_valida():
    dev = {"vendor_id": "0781", "product_id": "558c", "serial": "ABC123"}
    # VID/PID se pasan a mayusculas; el formato resultante es el canonico.
    assert prevention._build_instance_id(dev) == r"USB\VID_0781&PID_558C\ABC123"


@pytest.mark.parametrize("dev", [
    {"vendor_id": "078", "product_id": "558C", "serial": "ABC"},    # VID corto
    {"vendor_id": "0781", "product_id": "ZZZZ", "serial": "ABC"},   # PID no hex
    {"vendor_id": "0781", "product_id": "558C", "serial": "a;b"},   # serial sucio
    {"vendor_id": "", "product_id": "", "serial": ""},              # vacio
])
def test_build_instance_id_rechaza_componentes_invalidos(dev):
    assert prevention._build_instance_id(dev) == ""


# --- Gestion de desbloqueos de sesion ----------------------------------------

def test_desbloqueo_de_sesion_marca_y_limpia():
    prevention.clear_session_unlocked()
    assert prevention.is_session_unlocked("SN1") is False
    prevention.mark_unlocked("SN1")
    assert prevention.is_session_unlocked("SN1") is True
    # Un serial vacio no se registra
    prevention.mark_unlocked("")
    assert prevention.is_session_unlocked("") is False
    prevention.clear_session_unlocked()
    assert prevention.is_session_unlocked("SN1") is False


def test_unlock_device_sin_instancia_es_noop():
    # Sin InstanceId no hay nada que reactivar: se considera exito sin tocar PnP.
    assert prevention.unlock_device("") is True
    assert prevention.unlock_device(None) is True


# --- Decision de bloqueo en modo estricto ------------------------------------

def test_no_bloquea_fuera_de_modo_estricto(temp_db):
    from store.anomaly_store import set_config
    set_config("anomaly.mode", "monitorizacion")
    alerts = [{"device_id": 1, "severity": "alta", "score": 0.9}]
    devices = [{"id": 1, "serial": "SN1", "vendor_id": "0781",
                "product_id": "558C"}]
    assert prevention.maybe_block_devices(alerts, devices) == []


def test_solo_bloquea_severidad_alta(temp_db):
    from store.anomaly_store import set_config
    set_config("anomaly.mode", "estricto")
    set_config("prevention.physical_block", "false")  # solo bloqueo logico
    alerts = [
        {"device_id": 1, "severity": "media", "score": 0.6},
        {"device_id": 2, "severity": "alta", "score": 0.9},
    ]
    devices = [
        {"id": 1, "serial": "SN_MEDIA", "vendor_id": "0781", "product_id": "558C"},
        {"id": 2, "serial": "SN_ALTA", "vendor_id": "0781", "product_id": "558C"},
    ]
    blocked = prevention.maybe_block_devices(alerts, devices)
    assert len(blocked) == 1
    assert blocked[0]["serial"] == "SN_ALTA"
    # Bloqueo logico: sin admin no se marca como fisico
    assert blocked[0]["physical"] is False


def test_bloqueo_se_persiste_en_historial(temp_db):
    from store.anomaly_store import set_config, get_config
    import json
    set_config("anomaly.mode", "estricto")
    set_config("prevention.physical_block", "false")
    alerts = [{"device_id": 1, "severity": "alta", "score": 0.95}]
    devices = [{"id": 1, "serial": "SN1", "vendor_id": "0781",
                "product_id": "558C"}]
    prevention.maybe_block_devices(alerts, devices)
    log = json.loads(get_config("prevention.block_log", "[]"))
    assert any(r.get("serial") == "SN1" for r in log)
