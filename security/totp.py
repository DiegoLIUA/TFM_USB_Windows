"""
Segundo factor TOTP (RFC 6238) para desbloquear dispositivos.
Compatible con Google Authenticator / Authy.
El secreto se guarda en config (totp.secret).
"""

import logging
from typing import Optional

from store.anomaly_store import get_config, set_config

logger = logging.getLogger(__name__)

_ISSUER = "TFM-USB-Monitor"
_ACCOUNT = "operador"


def is_configured() -> bool:
    """True si ya hay un secreto TOTP guardado."""
    return bool((get_config("totp.secret", "") or "").strip())


def generate_secret() -> str:
    """Genera y persiste un nuevo secreto TOTP. Devuelve el secreto base32."""
    import pyotp
    secret = pyotp.random_base32()
    set_config("totp.secret", secret)
    logger.info("Nuevo secreto TOTP generado.")
    return secret


def get_provisioning_uri(secret: Optional[str] = None) -> str:
    """URI otpauth:// para generar el QR en una app autenticadora."""
    import pyotp
    secret = secret or (get_config("totp.secret", "") or "")
    if not secret:
        return ""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=_ACCOUNT, issuer_name=_ISSUER)


def qr_png_bytes(uri: str = "") -> bytes:
    """
    Genera el QR del URI otpauth:// como PNG en memoria (bytes).
    Devuelve b'' si no hay URI o falta la libreria qrcode.
    """
    uri = uri or get_provisioning_uri()
    if not uri:
        return b""
    try:
        import io
        import qrcode
        from qrcode.image.pil import PilImage
        img = qrcode.make(uri, image_factory=PilImage)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        logger.warning("qrcode/pillow no instalado; no se puede generar el QR.")
        return b""
    except Exception as exc:
        logger.warning("Error generando QR: %s", exc)
        return b""


def verify(code: str) -> bool:
    """Valida un codigo TOTP de 6 digitos con ventana de +-1 intervalo."""
    secret = (get_config("totp.secret", "") or "").strip()
    if not secret or not code:
        return False
    try:
        import pyotp
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except Exception as exc:
        logger.warning("Error verificando TOTP: %s", exc)
        return False


def current_code() -> str:
    """Codigo TOTP actual (solo para pruebas/depuracion)."""
    secret = (get_config("totp.secret", "") or "").strip()
    if not secret:
        return ""
    import pyotp
    return pyotp.TOTP(secret).now()
