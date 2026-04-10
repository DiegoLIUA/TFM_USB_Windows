"""
Generación de informes HTML a partir de los datos de dispositivos USB.
Utiliza Jinja2 para renderizar la plantilla.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

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
        <th>Número de serie</th>
        <th>Vendor ID</th>
        <th>Product ID</th>
        <th>Primera conexión</th>
        <th>Última conexión</th>
        <th>Fuentes</th>
      </tr>
    </thead>
    <tbody>
      {% for dev in devices %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ dev.friendly_name }}</td>
        <td><code>{{ dev.serial }}</code></td>
        <td>{{ dev.vendor_id or '—' }}</td>
        <td>{{ dev.product_id or '—' }}</td>
        <td>{{ dev.first_seen or '—' }}</td>
        <td>{{ dev.last_seen or '—' }}</td>
        <td>{{ dev.sources or 'registro' }}</td>
      </tr>
      {% else %}
      <tr><td colspan="8">No se encontraron dispositivos.</td></tr>
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
