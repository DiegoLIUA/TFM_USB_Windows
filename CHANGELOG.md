# CHANGELOG

## [2026-04-01] — MVP Forense: correlación multifuente y filtros

### Añadido
- `normalization/correlator.py`: módulo de correlación de artefactos de 3 fuentes (registro, evtx, setupapi) en sesiones coherentes
- `ui/filter_bar.py`: barra de filtros por rango de fechas y texto libre en la UI
- Columna "Fuentes" en la tabla de dispositivos y en el informe HTML
- Hash SHA-256 de integridad en cada evento insertado en la base de datos
- Extracción de Event IDs 20001/20003/2003 y VID/PID desde logs .evtx (DriverFrameworks y PnP)
- Extracción de VID/PID y número de serie desde `setupapi.dev.log`
- Funciones de consulta filtrada por rango de fechas y serial en la base de datos
- Función `insert_session()` y `get_sessions_for_device()` para persistencia de sesiones USB
- Función `get_device_sources()` para obtener las fuentes de datos de cada dispositivo

### Modificado
- `acquisition/evtx_reader.py`: parseo de XML para extraer identificadores USB y filtrar por Event IDs relevantes
- `acquisition/setupapi_reader.py`: extracción de VID/PID y serial del hardware_id
- `store/models.py`: columna `hash_sha256` en tabla `events`
- `store/database.py`: funciones de sesión, hash SHA-256, filtros y fuentes
- `ui/main_window.py`: pipeline de análisis con correlación de 3 fuentes y filtrado en memoria
- `ui/device_table.py`: columna de fuentes de datos
- `reporting/report_generator.py`: columna de fuentes en informe HTML

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
