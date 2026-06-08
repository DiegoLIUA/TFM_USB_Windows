# Guía de uso — TFM USB Windows

Sistema inteligente de análisis forense USB para Windows 11.
Detecta dispositivos conectados (histórico y actual), correlaciona artefactos
de tres fuentes (Registro, Event Logs, SetupAPI) y aplica un motor de
anomalías explicable por componentes.

---

## 1. Requisitos

- Windows 11 (probado en 10.0.26200)
- Python 3.13
- Permisos de usuario estándar (admin solo si quieres bloqueo físico de dispositivos)

### Instalación de dependencias

```bash
cd TFM_USB_Windows
pip install -r requirements.txt
```

Dependencias clave: `PyQt6`, `python-evtx`, `numpy`, `scipy`, `Jinja2`.

> Si `python-evtx` no se instala correctamente la app sigue funcionando,
> simplemente se omite la lectura de Event Logs y se usa Registro + SetupAPI.

---

## 2. Arranque

```bash
python main.py
```

La primera ejecución crea `tfm_usb.db` (SQLite) con el esquema completo.
Si modificas el esquema, borra ese fichero antes de relanzar.

> **Importante**: si vienes de una versión anterior, borra `tfm_usb.db` porque
> el esquema ha cambiado (nueva tabla `system_signals`).

---

## 2.bis Monitorización continua y segundo factor (TOTP)

A partir de esta versión la app puede vigilar el equipo en segundo plano sin
necesidad de pulsar "Analizar" cada cierto tiempo.

### Monitor en segundo plano

- Pulsa **"Iniciar monitor"** (botón inferior). El indicador de la barra de
  estado pasa a "Monitor: activo".
- Mientras la ventana está abierta, cada N segundos (configurable en Ajustes,
  por defecto 30) el sistema:
  - Detecta USBs recién conectados.
  - Captura señales: suspensiones/reanudaciones, logon/logoff, app en primer
    plano y tiempo de inactividad.
  - Si hay un horario habitual activo y se inserta un USB fuera de él, lo
    **bloquea** y exige un código TOTP para reactivarlo.
- El monitor se detiene solo al cerrar la app.

### Configurar el horario habitual

En la pestaña **Ajustes → Horario habitual de uso**:

1. Define la franja (Desde / Hasta) y marca los días de la semana permitidos.
2. Marca **"Bloquear inserciones de USB fuera de este horario"** para activar el
   enforcement (si no, solo es informativo).
3. Guarda.

### Configurar el segundo factor (TOTP)

En **Ajustes → Segundo factor (TOTP)**:

1. Pulsa **"Generar nuevo secreto TOTP"**.
2. Copia el enlace `otpauth://` que aparece y añádelo a tu app autenticadora
   (Google Authenticator, Authy, Microsoft Authenticator…). Puedes convertir el
   enlace en QR con cualquier generador o pegarlo manualmente.
3. A partir de ese momento, cualquier USB insertado fuera de horario mostrará un
   diálogo que pide el código de 6 dígitos para desbloquearlo.

> El bloqueo físico real (`Disable-PnpDevice` / `Enable-PnpDevice`) requiere
> ejecutar la app como **administrador**. Sin admin, el bloqueo queda registrado
> de forma lógica y el diálogo TOTP sigue apareciendo.

---

## 3. Interfaz

La ventana principal tiene varias pestañas (Dispositivos, Alertas, Ajustes):

### 3.1 Selector de modo (arriba)

| Modo            | Comportamiento                                              |
|-----------------|-------------------------------------------------------------|
| `aprendizaje`   | Acumula sesiones y entrena el modelo. **No genera alertas.** |
| `monitorizacion`| Genera alertas si el score supera el umbral.                |
| `estricto`      | Genera alertas + intenta bloquear dispositivos de severidad **alta**. |

El modo se persiste en la tabla `config`. Al cambiarlo, el siguiente análisis
aplica el nuevo modo automáticamente.

### 3.2 Pestaña "Dispositivos"

Tabla con todos los USB detectados (históricos + conectados ahora). Columnas:

- **Nombre**, **Tipo** (almacenamiento, HID, audio, hub…), **Capacidad**
- **Serial**, **Vendor ID**, **Product ID**
- **Primera conexión**, **Última conexión**
- **Estado** (Conectado / Desconectado)
- **Fuentes** (registro, evtx, setupapi)

Filtros disponibles en la barra superior:

- Rango de fechas (desde / hasta)
- Búsqueda por serial o nombre
- Checkbox **"Solo conectados ahora"** — muestra únicamente USBs presentes en el momento del análisis

### 3.3 Pestaña "Alertas"

Tabla de alertas generadas por el motor de anomalías:

- **Fecha**, **Dispositivo**, **Serial**
- **Severidad** (baja / media / alta — coloreada)
- **Score** (0.0 – 1.0)
- **Motivo** (componente dominante)
- **Desglose** (`hora=X.XX | disp=X.XX | maha=X.XX`)

Filtros propios por rango de fechas y nombre/serial del dispositivo.

### 3.4 Botones inferiores

- **Analizar** — ejecuta el pipeline completo (adquisición, correlación, scoring)
- **Exportar HTML** — informe HTML con plantilla Jinja2
- **Exportar JSON** — informe JSON con dispositivos + alertas + componentes

---

## 4. Flujo recomendado de uso

### Primera vez

1. Lanza la app (`python main.py`).
2. Deja el modo en **`aprendizaje`** (predeterminado).
3. Pulsa **Analizar**. El sistema lee tu historial USB y entrena el modelo.
4. Conecta y desconecta USBs durante varios días, dándole a Analizar de vez en cuando.

### Tras 7+ días con datos

5. Cambia el modo a **`monitorizacion`**.
6. Cada Analizar comprueba las sesiones nuevas contra el modelo.
7. Si una sesión supera el umbral (por defecto `0.6`), aparece una alerta en la pestaña.

### Modo estricto (opcional)

8. Solo si quieres bloqueo físico: cambia el modo a **`estricto`** y activa la
   config `prevention.physical_block` a `true` en BD.
9. Las alertas de severidad **alta** intentarán deshabilitar el dispositivo
   vía PowerShell `Disable-PnpDevice` (requiere ejecutar la app como admin).

---

## 5. Configuración avanzada

Toda la configuración se almacena en la tabla `config` (clave/valor).

| Clave                          | Por defecto      | Descripción                                      |
|--------------------------------|------------------|--------------------------------------------------|
| `anomaly.mode`                 | `aprendizaje`    | Modo de operación                                |
| `anomaly.threshold`            | `0.6`            | Umbral mínimo para generar alerta                |
| `anomaly.train_days`           | `7`              | Días de histórico usados para entrenar           |
| `prevention.physical_block`    | `false`          | Activar `Disable-PnpDevice` real                 |
| `prevention.block_log`         | `[]`             | Historial de bloqueos (JSON, último 100)         |

Para modificar manualmente:

```python
from store.anomaly_store import set_config
set_config("anomaly.threshold", "0.5")
```

---

## 6. Modelo de anomalías

El score final es una suma ponderada de tres componentes, todos en [0, 1]:

```
score = 0.4 × hour_rarity + 0.3 × device_rarity + 0.3 × mahalanobis
```

| Componente       | Mide                                                    |
|------------------|---------------------------------------------------------|
| `hour_rarity`    | Probabilidad inversa de la hora de conexión (24 bins)   |
| `device_rarity`  | Frecuencia inversa del serial en el histórico          |
| `mahalanobis`    | Distancia al centroide de [hora, duración, días_desde_última] |

**Modo degradado**: si hay menos de 5 sesiones en la ventana de entrenamiento,
el motor cae a reglas simples (hora <7h o >22h, dispositivo nunca visto).

**Severidad** según el margen sobre el umbral:

- score ≥ umbral + 0.25 → **alta**
- score ≥ umbral + 0.10 → **media**
- score ≥ umbral       → **baja**

---

## 7. Esquema de la base de datos

| Tabla         | Contenido                                                      |
|---------------|----------------------------------------------------------------|
| `devices`     | Dispositivos USB únicos (clave: `serial`)                      |
| `sessions`    | Sesiones de conexión/desconexión por dispositivo               |
| `events`      | Eventos crudos con hash SHA-256 de integridad                  |
| `alerts`      | Alertas con score, componentes y referencia a sesión           |
| `config`      | Configuración clave/valor                                       |
| `model_state` | Snapshots del modelo entrenado (versión + payload JSON)        |

---

## 8. Estructura del proyecto

```
TFM_USB_Windows/
├── main.py                      # Punto de entrada PyQt6
├── acquisition/
│   ├── registry_reader.py       # USBSTOR + USB key (cross-ref por ContainerID)
│   ├── evtx_reader.py           # Event Logs DriverFrameworks/PnP
│   ├── setupapi_reader.py       # setupapi.dev.log
│   └── live_state.py            # WMI: dispositivos conectados ahora
├── normalization/
│   ├── normalizer.py            # Normaliza fechas e IDs
│   └── correlator.py            # Correlaciona 3 fuentes en sesiones
├── store/
│   ├── models.py                # Esquema SQL
│   ├── database.py              # CRUD básico
│   └── anomaly_store.py         # Config, alertas, sesiones, model_state
├── analytics/
│   ├── behavior_model.py        # 3 componentes serializables
│   ├── anomaly_detector.py      # Motor con score/explain/train
│   ├── pipeline.py              # Orquestación de scoring + alertas
│   └── prevention.py            # Bloqueo lógico/físico opcional
├── ui/
│   ├── main_window.py           # Ventana principal con tabs
│   ├── analysis_worker.py       # Hilo de análisis (no bloquea UI)
│   ├── device_table.py          # Tabla de dispositivos
│   ├── filter_bar.py            # Barra de filtros
│   ├── alerts_view.py           # Vista de alertas
│   └── report_viewer.py         # Diálogo de informe
├── reporting/
│   └── report_generator.py      # HTML (Jinja2) + JSON
├── tfm_usb.db                   # SQLite (se crea al arrancar)
├── requirements.txt
├── CHANGELOG.md
└── GUIA_USO.md                  # (este archivo)
```

---

## 9. Solución de problemas comunes

| Síntoma                                          | Causa probable                                        |
|--------------------------------------------------|-------------------------------------------------------|
| `python-evtx no disponible` en consola           | `pip install python-evtx` (no rompe nada, es opcional) |
| Tabla vacía tras Analizar                        | Sin USBs en `HKLM\...\Enum\USBSTOR` — usa fallback simulado |
| `IntegrityError: FOREIGN KEY constraint failed`  | Esquema antiguo — borra `tfm_usb.db` y relanza        |
| Alertas siempre vacías                           | Modo en `aprendizaje` — cambia a `monitorizacion`     |
| Modelo siempre en degradado                      | Pocas sesiones (< 5 en `train_days`) — usa más tiempo |
| `Disable-PnpDevice` falla                        | Falta admin — relanza la app como administrador       |

---

## 10. Consideraciones forenses

- Los hashes SHA-256 de eventos garantizan integridad de la evidencia almacenada.
- "Archivos copiados" no es prueba directa: solo se infiere actividad por
  presencia del dispositivo y duración de sesión. Tratar siempre como **indicio**.
- El bloqueo físico (`Disable-PnpDevice`) deja huella en el registro y altera
  el estado del sistema — usar solo en entornos controlados.
