"""
Utilidades de formato para presentacion al usuario (no afectan al
almacenamiento). Centraliza la conversion de fechas del formato interno ISO
(aaaa-mm-dd) al formato espanol (dd-mm-aaaa) usado en la interfaz y en los
informes HTML.
"""

from datetime import datetime

# Formato interno usado para almacenar y parsear timestamps en toda la app.
_ISO_FMT = "%Y-%m-%d %H:%M:%S"
_ISO_FMT_DATE = "%Y-%m-%d"


def fecha_es(valor) -> str:
    """
    Convierte una fecha del formato interno (aaaa-mm-dd [HH:MM:SS]) al formato
    espanol (dd-mm-aaaa [HH:MM:SS]). Es tolerante: si el valor no es una fecha
    reconocible (vacio, guion, ya formateada, etc.) se devuelve tal cual, para
    no romper la presentacion. Solo cambia la representacion, nunca el dato
    almacenado.
    """
    if valor is None:
        return ""
    texto = str(valor).strip()
    if not texto:
        return ""
    for fmt_in, fmt_out in ((_ISO_FMT, "%d-%m-%Y %H:%M:%S"),
                            (_ISO_FMT_DATE, "%d-%m-%Y")):
        try:
            return datetime.strptime(texto, fmt_in).strftime(fmt_out)
        except (ValueError, TypeError):
            continue
    return texto  # no es una fecha ISO reconocible: se deja intacta
