"""
Generación de informes HTML y JSON a partir de los datos de dispositivos USB.
Utiliza Jinja2 para renderizar la plantilla HTML.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Carpeta donde se guardan los informes generados, fuera de la raiz del
# proyecto para no ensuciarla. Se crea bajo demanda.
_REPORTS_DIRNAME = "informes"


def reports_dir() -> Path:
    """Devuelve (creandola si hace falta) la carpeta de informes del proyecto."""
    d = Path(__file__).resolve().parent.parent / _REPORTS_DIRNAME
    d.mkdir(exist_ok=True)
    return d

_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Informe Forense USB — {{ generated_at }}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; color: #222; }
    h1   { color: #1a3a5c; }
    h2   { color: #2c5f8a; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
    table { border-collapse: collapse; width: 100%; margin-top: 16px; }
    th, td { border: 1px solid #bbb; padding: 8px 12px; text-align: left; }
    th   { background: #1a3a5c; color: #fff; }
    tr:nth-child(even) { background: #f4f7fb; }
    .footer { margin-top: 40px; font-size: 0.85em; color: #777; }
    .badge-demo { display: inline-block; background: #e07b00; color: #fff;
                  padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
  </style>
</head>
<body>
  <h1>Informe Forense de Dispositivos USB</h1>
  <p>Generado: <strong>{{ generated_at }}</strong> &nbsp;
     Total de dispositivos: <strong>{{ devices | length }}</strong></p>

  <h2>Dispositivos detectados</h2>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Nombre del dispositivo</th>
        <th>Tipo</th>
        <th>Capacidad</th>
        <th>Número de serie</th>
        <th>Vendor ID</th>
        <th>Product ID</th>
        <th>Primera conexión</th>
        <th>Última conexión</th>
        <th>Estado</th>
        <th>Fuentes</th>
      </tr>
    </thead>
    <tbody>
      {% for dev in devices %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ dev.friendly_name }}</td>
        <td>{{ dev.device_type or 'almacenamiento' }}</td>
        <td>{{ dev.capacity or '—' }}</td>
        <td><code>{{ dev.serial }}</code></td>
        <td>{{ dev.vendor_id or '—' }}</td>
        <td>{{ dev.product_id or '—' }}</td>
        <td>{{ dev.first_seen or '—' }}</td>
        <td>{{ dev.last_seen or '—' }}</td>
        <td>{{ 'Conectado' if dev.connected else 'Desconectado' }}</td>
        <td>{{ dev.sources or 'registro' }}</td>
      </tr>
      {% else %}
      <tr><td colspan="11">No se encontraron dispositivos.</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <p class="footer">
    Sistema inteligente de análisis forense USB — TFM &nbsp;|&nbsp;
    Nota: los datos marcados con [DEMO] son simulados y no corresponden a actividad real.
  </p>
</body>
</html>
"""


def generate_html_report(
    devices: List[Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Genera un informe HTML y lo guarda en output_path."""
    try:
        from jinja2 import Template
    except ImportError:
        logger.error("Jinja2 no instalado. No se puede generar el informe.")
        raise

    template = Template(_TEMPLATE)
    html = template.render(
        devices=devices,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    output_path.write_text(html, encoding="utf-8")
    logger.info("Informe HTML generado en: %s", output_path)
    return output_path


def generate_json_report(
    devices: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Genera un informe JSON con dispositivos y alertas."""
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "devices":      _serializable(devices),
        "alerts":       _serializable(alerts),
        "device_count": len(devices),
        "alert_count":  len(alerts),
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Informe JSON generado en: %s", output_path)
    return output_path


def _serializable(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convierte filas con tipos sqlite/json embebido a dict puro."""
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        comp = d.get("components")
        if isinstance(comp, str):
            try:
                d["components"] = json.loads(comp)
            except json.JSONDecodeError:
                pass
        out.append(d)
    return out


_ALERTS_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Informe de Alertas USB — {{ generated_at }}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; color: #222; }
    h1   { color: #1a3a5c; }
    table { border-collapse: collapse; width: 100%; margin-top: 16px; }
    th, td { border: 1px solid #bbb; padding: 8px 12px; text-align: center; }
    th   { background: #1a3a5c; color: #fff; }
    tr:nth-child(even) { background: #f4f7fb; }
    .alta  { color: #c0392b; font-weight: bold; }
    .media { color: #d97400; font-weight: bold; }
    .baja  { color: #7d6608; font-weight: bold; }
    .footer { margin-top: 40px; font-size: 0.85em; color: #777; }
  </style>
</head>
<body>
  <h1>Informe de Alertas de Anomalías USB</h1>
  <p>Generado: <strong>{{ generated_at }}</strong> &nbsp;
     Total de alertas: <strong>{{ alerts | length }}</strong></p>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Fecha</th><th>Dispositivo</th><th>Serial</th>
        <th>Severidad</th><th>Score</th><th>Motivo</th><th>Desglose</th>
      </tr>
    </thead>
    <tbody>
      {% for a in alerts %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ a.timestamp or '—' }}</td>
        <td>{{ a.friendly_name or '—' }}</td>
        <td><code>{{ a.serial or '—' }}</code></td>
        <td class="{{ a.severity }}">{{ (a.severity or '').upper() }}</td>
        <td>{{ '%.2f' % (a.score or 0) }}</td>
        <td>{{ a.reason or '—' }}</td>
        <td>{{ a.breakdown or '—' }}</td>
      </tr>
      {% else %}
      <tr><td colspan="8">No se han registrado alertas.</td></tr>
      {% endfor %}
    </tbody>
  </table>
  <p class="footer">
    Sistema inteligente de análisis forense USB — TFM
  </p>
</body>
</html>
"""


def _alert_breakdown(components: Any) -> str:
    """Texto legible del desglose de componentes de una alerta."""
    if isinstance(components, str):
        try:
            components = json.loads(components)
        except (json.JSONDecodeError, TypeError):
            return ""
    if not isinstance(components, dict):
        return ""
    return (f"hora={components.get('hour_rarity', 0):.2f} | "
            f"disp={components.get('device_rarity', 0):.2f} | "
            f"maha={components.get('mahalanobis', 0):.2f}")


def generate_alerts_html_report(
    alerts: List[Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Genera un informe HTML de alertas y lo guarda en output_path."""
    from jinja2 import Template
    rows = []
    for a in alerts:
        d = dict(a)
        d["breakdown"] = _alert_breakdown(a.get("components"))
        rows.append(d)
    html = Template(_ALERTS_TEMPLATE).render(
        alerts=rows,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    output_path.write_text(html, encoding="utf-8")
    logger.info("Informe de alertas HTML generado en: %s", output_path)
    return output_path


def generate_alerts_json_report(
    alerts: List[Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Genera un informe JSON solo de alertas."""
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "alerts":       _serializable(alerts),
        "alert_count":  len(alerts),
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Informe de alertas JSON generado en: %s", output_path)
    return output_path
