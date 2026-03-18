# CHANGELOG

## [2026-03-17] — Estructura inicial del proyecto

### Añadido
- `main.py`: punto de entrada que lanza la aplicación PyQt6
- `requirements.txt`: dependencias del proyecto (PyQt6, python-registry, python-evtx, numpy, scipy, pandas, Jinja2)
- `README.md`: descripción básica del proyecto y estructura
- `acquisition/__init__.py`, `acquisition/registry_reader.py`: lectura de HKLM\SYSTEM\CurrentControlSet\Enum\USBSTOR con fallback a datos simulados
- `acquisition/evtx_reader.py`: lectura de Event Logs .evtx relacionados con USB
- `acquisition/setupapi_reader.py`: parseo de setupapi.dev.log para timestamps de primera conexión
- `normalization/__init__.py`, `normalization/normalizer.py`: normalización de fechas, IDs y deduplicación por número de serie
- `store/__init__.py`, `store/models.py`: esquema SQL de tablas (devices, sessions, events, alerts)
- `store/database.py`: gestión de conexión SQLite, inicialización y operaciones CRUD básicas
- `analytics/__init__.py`, `analytics/anomaly_detector.py`: placeholder del motor de anomalías con interfaz pública estable
- `ui/__init__.py`, `ui/main_window.py`: ventana principal con botones Analizar y Exportar informe, hilo secundario para adquisición
- `ui/device_table.py`: widget QTableWidget con columnas de dispositivos USB
- `ui/report_viewer.py`: diálogo de apertura y guardado del informe generado
- `reporting/__init__.py`, `reporting/report_generator.py`: generación de informes HTML con Jinja2
