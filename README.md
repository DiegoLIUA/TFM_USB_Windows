# TFM — Sistema inteligente de análisis forense y prevención de uso anómalo de dispositivos USB en Windows

Herramienta de escritorio en Python/PyQt6 para Windows que:

- Lee el historial de dispositivos USB desde el Registro de Windows
- Almacena los datos en SQLite
- Muestra la información en una interfaz gráfica
- Genera informes HTML básicos
- (Fase futura) Detecta comportamientos anómalos mediante modelado estadístico

## Requisitos

- Windows 10/11
- Python 3.13+

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
python main.py
```

## Estructura del proyecto

```
TFM_USB_Windows/
├── main.py              # Punto de entrada
├── requirements.txt     # Dependencias
├── acquisition/         # Lectura de artefactos del sistema
├── normalization/       # Normalización y correlación de eventos
├── store/               # Base de datos SQLite
├── analytics/           # Motor de detección de anomalías (en desarrollo)
├── ui/                  # Interfaz gráfica PyQt6
└── reporting/           # Generación de informes HTML
```

## Nota sobre datos

En sistemas sin dispositivos USB registrados o sin acceso al Registro, la aplicación opera
en modo demo con datos simulados debidamente identificados como `[DEMO]`.

---

*Proyecto académico — TFM de Ciberseguridad*
