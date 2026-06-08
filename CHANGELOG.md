# CHANGELOG

## [2026-06-09b] — Corrección de fuga de conexiones SQLite

### Corregido
- **Las conexiones a la base de datos no se cerraban**: el patrón
  `with get_connection() as conn` solo gestionaba la transacción (comportamiento
  nativo de `sqlite3`), dejando la conexión abierta. En la ejecución prolongada
  del monitor (consultas cada 1–30 s) esto acumulaba conexiones sin liberar (se
  manifestaba como 334 `ResourceWarning` en la batería de pruebas). `get_connection`
  pasa a ser un gestor de contexto propio que cierra siempre la conexión (commit
  si no hay excepción, rollback si la hay). Mejora también el acceso concurrente
  desde los hilos de interfaz, monitor y análisis. No requirió cambios en los
  puntos de uso.

## [2026-06-09] — Organización de informes y arranque robusto

### Modificado
- **Los informes se guardan en `informes/`** (carpeta dedicada, creada bajo
  demanda) en lugar de la raíz del proyecto. Centralizado en `reports_dir()`
  (`reporting/report_generator.py`) y aplicado a las exportaciones HTML y JSON.
  Los informes acumulados se han movido a esa carpeta y se añade `informes/` al
  `.gitignore`.
- **Arranque robusto**: `main.py` envuelve la inicialización en un manejo de
  excepciones. Si el arranque falla (BD inaccesible, dependencia ausente, etc.)
  se registra el traceback en el log y se muestra un diálogo de error al
  usuario, en vez de cerrar en silencio. El registro se ancla a la carpeta del
  proyecto para que su ruta no dependa del directorio de trabajo.

### Interno
- `.gitignore` ampliado (informes, `.venv/`, `.pytest_cache/`).

## [2026-06-08b] — Bloqueo inmediato de discos externos fijos (UAS)

### Corregido
- **Discos externos por adaptador UAS escapaban al bloqueo rápido**: el sistema
  los presenta como unidades `FIXED` (no extraíbles), por lo que el chequeo
  rápido (~1 s), que solo miraba unidades `REMOVABLE`, no reaccionaba a ellos; el
  bloqueo Zero Trust se aplicaba únicamente en el ciclo completo (hasta ~30 s
  después). Ahora el chequeo rápido detecta también unidades `FIXED` que
  aparezcan tras el arranque, de modo que un SSD/HDD externo se bloquea en menos
  de un segundo, igual que un pendrive. Las unidades presentes al iniciar el
  monitor (disco del sistema y discos internos) forman parte del conjunto
  conocido y no disparan reacción.
- **La sesión y el bloqueo podían atribuirse al dispositivo equivocado**: se
  resolvía con «el primer dispositivo de almacenamiento del registro», criterio
  arbitrario cuando hay varios. Ahora el dispositivo se identifica por la **letra
  de unidad** recién montada (vía estado en vivo), con respaldo al más reciente
  del registro si no se logra resolver.

### Interno
- `get_storage_drives` en `acquisition/fast_usb.py` (REMOVABLE + FIXED, con
  marca `removable`); `get_removable_drives` se mantiene por compatibilidad.
- `_resolve_drive_device` en `monitoring/monitor_cycle.py`: resolución por letra
  reutilizada por la apertura de sesión y la política (una sola consulta en
  vivo por inserción).
- `_is_real_serial` reescrita con precedencia explícita (mismo comportamiento).
- Tests nuevos: `test_fast_usb_policy.py` (detección FIXED y resolución por
  letra) y casos UAS en `test_live_state.py`.

## [2026-06-08] — Severidad fija, rareza horaria por vecindad y discos UAS

### Modificado
- **Bandas de severidad fijas por score**: alta >0,75; media [0,5; 0,75];
  baja <0,5. Antes dependían de un margen relativo al umbral, lo que provocaba
  que un mismo score pudiera caer en niveles distintos (p. ej. 0,68 «media» y
  0,67 «baja»). Ahora un score siempre significa el mismo nivel. El umbral de
  configuración sigue decidiendo si la alerta llega a generarse.
- **Rareza horaria (`hour_rarity`) por vecindad**: el histograma de 24 bins ya
  no evalúa solo el bin exacto, sino su entorno (ventana ±2 h con kernel
  triangular). Así una hora contigua al pico de actividad hereda densidad y deja
  de marcarse como rara aunque nunca se haya registrado una conexión en ese bin
  concreto. Esto corrige que las 12:35 puntuaran 0,88 teniendo el pico en las
  13:00 dentro del horario habitual.
- **Detección de discos externos por adaptador UAS**: los SSD/HDD externos con
  adaptador USB-SCSI se identifican ahora como `almacenamiento` con su
  capacidad. Estos discos se presentan a Windows como `InterfaceType=SCSI` (no
  USB), por lo que se capturan por `MediaType='External hard disk media'` (que
  los distingue del disco interno, que es `Fixed`). El tipo y la capacidad se
  cruzan por **VID_PID** —obtenido del dispositivo USB padre—, identificador
  estable frente al serial de enumeración SCSI (corto, p. ej. «6»), que se
  descarta por no ser fiable y poder colisionar con otros dispositivos PnP.
- **Duración media de almacenamiento**: se descartan las sesiones de duración
  nula o insignificante (<1 min); la media refleja el tiempo de uso efectivo
  cuando el dispositivo está realmente conectado, no el promedio sobre todo el
  periodo de observación.

### Interno
- `HourHistogram._smoothed_density` (difusión por vecindad) en
  `analytics/behavior_model.py`.
- Constante `_MIN_SESSION_MIN` en `analytics/stats.py`.
- Cruce por serial en `_parse_live_data` (`acquisition/live_state.py`) y entrada
  `scsiadapter` en `_CLASS_TYPE_MAP`.
- Tests de severidad actualizados a las nuevas bandas fijas.

## [2026-06-07c] — Política de control de acceso USB (modelo Zero Trust)

### Modificado
- **Nueva política de seguridad en modo estricto**: solo se permiten libremente
  los dispositivos marcados como de confianza dentro del horario habitual.
  Cualquier dispositivo NO confiable (aunque sea en horario) y cualquier
  dispositivo (confiable o no) fuera del horario habitual se bloquea y exige
  segundo factor (TOTP). Todos los dispositivos son no confiables por defecto
  hasta que el usuario los marque desde la aplicación.
- En modo monitorización, esta política genera alertas sin bloquear.
- La política se aplica ahora a **todos los dispositivos USB** (no solo de
  almacenamiento): el almacenamiento se detecta en ~1 s (chequeo rápido) y el
  resto en el ciclo completo (intervalo configurable).
- El desglose de la alerta refleja la causa: `device_rarity` alto cuando es por
  dispositivo no confiable, `hour_rarity` alto cuando es fuera de horario.

### Interno
- Refactor de `monitoring/monitor_cycle.py`: lógica de reacción unificada en
  `_react_to_devices` / `_evaluate`, reutilizada por el chequeo rápido y el
  ciclo completo.

## [2026-06-07b] — Duración de sesiones USB y dashboard ajustado

### Añadido
- **Registro de duración de sesiones de almacenamiento**: el monitor en segundo
  plano abre una sesión al montarse una unidad USB y la cierra al retirarse,
  registrando la hora de desconexión (`open_drive_session` / `close_drive_session`).
  Esto permite medir cuánto tiempo permanece conectado cada dispositivo.
- **Gráfica de duración media de uso** en el panel de estadísticas: muestra los
  tres dispositivos de almacenamiento más usados con su duración media de sesión
  (`analytics.stats.avg_duration_top_storage`).
- El generador de alertas demo crea además sesiones con duración, para poblar la
  nueva gráfica en las capturas.

### Eliminado
- Gráfica «Tipos de dispositivos conectados» del dashboard (sustituida por la de
  duración media).

## [2026-06-07] — Margen de tolerancia horaria y generador de alertas demo

### Añadido
- **Zona de tolerancia en el horario habitual** (`security.schedule.is_anomalous_schedule`):
  una inserción solo se considera anómala si ocurre fuera del horario ampliado
  por un margen configurable (por defecto 2 h a cada lado). Ejemplo: horario
  10:00–15:00 con margen 2 h ⇒ se tolera 08:00–17:00; fuera de ahí es anómalo.
  El margen es ajustable desde Ajustes. Reduce los falsos positivos en torno a
  los límites de la jornada.
- **Generador de alertas de demostración** (`generar_alertas_demo.py`): inyecta
  alertas variadas (severidad baja/media/alta, scores y desgloses distintos)
  calculadas por el motor real, útil para capturas de la memoria. Reversible con
  `--limpiar` (las alertas demo se marcan con el prefijo «[DEMO]»).
- Tests del margen de tolerancia. Total: 30 tests.

## [2026-06-06d] — Ajustes de UI y exportación de informes por pestaña

### Modificado
- El selector de vista **Básico/Experto** se sitúa centrado bajo el título y
  solo se muestra en la pestaña «Dispositivos» (no aparece en Alertas,
  Estadísticas ni Ajustes, donde no tiene efecto).
- Los textos de la tabla de **Alertas** se muestran centrados.

### Añadido
- **Exportación de informes según la pestaña activa**: los botones «Exportar
  HTML» y «Exportar JSON» generan un informe de dispositivos o de alertas según
  la pestaña en la que se encuentre el usuario. Nuevas funciones
  `generate_alerts_html_report` y `generate_alerts_json_report` en
  `reporting/report_generator.py`. Los botones se habilitan según haya datos en
  la pestaña correspondiente.

## [2026-06-06c] — Horario habitual calculado desde la actividad

### Añadido
- **Cálculo automático del horario habitual** (`analytics.stats.compute_usual_schedule`):
  deriva la franja horaria de uso a partir de las señales de actividad
  observadas, descartando horas con actividad residual. Nuevo botón «Calcular
  desde mi actividad» en Ajustes, que rellena la franja para revisarla y
  guardarla. Cierra el círculo del aprendizaje: el horario deja de fijarse de
  forma arbitraria y pasa a derivarse del comportamiento real del usuario.
- Tests del cálculo de horario (`tests/test_stats_schedule.py`). Total: 28 tests.

## [2026-06-06b] — Fin del bucle de re-bloqueo tras desbloqueo TOTP

### Corregido
- **Bucle de re-bloqueo**: tras desbloquear un dispositivo con TOTP, el monitor
  lo volvía a detectar como nuevo y lo bloqueaba de inmediato. Ahora se mantiene
  una lista en memoria de seriales desbloqueados durante la sesión
  (`analytics/prevention._session_unlocked`); el monitor no vuelve a alertar ni
  bloquear esos dispositivos hasta que se cierra la aplicación.

### Notas
- Los dispositivos marcados como **de confianza** ya no generan alerta ni se
  bloquean (comportamiento confirmado y cubierto por la nueva comprobación).

## [2026-06-06] — Bloqueo rápido de USB y comando PowerShell corregido

### Corregido
- **Comando de bloqueo roto por el carácter «&»**: el InstanceId
  (`VID_xxxx&PID_yyyy`) rompía la línea de PowerShell, por lo que el bloqueo
  fallaba incluso con privilegios de administrador. Ahora el identificador se
  pasa por variable de entorno (`$env:PNP_TARGET`), evitando la interpolación.
- El diálogo de desbloqueo TOTP muestra el **nombre** del dispositivo en lugar
  del número de serie.

### Añadido
- **Detección rápida de USB** (`acquisition/fast_usb.py`): enumera las unidades
  extraíbles montadas mediante WinAPI (~0,1 s, sin PowerShell).
- **Monitor de doble ritmo** (`monitoring/monitor.py`): un chequeo rápido cada
  segundo detecta la inserción de pendrives y reacciona de inmediato (alerta y,
  en modo estricto, bloqueo), mientras que el ciclo completo de señales se
  mantiene en su intervalo configurable. Reduce el tiempo de reacción ante una
  inserción de ~30 s a ~1-2 s.

## [2026-06-05c] — Correcciones de alerta de horario, hora local y elevación admin

### Corregido
- **Alerta por horario incompleta**: ahora incluye el `device_id` (muestra
  nombre y serial en la tabla), severidad *alta*, motivo con acentuación
  correcta y desglose coherente (`hora=1.00 | disp=0.00 | maha=0.00`), usando
  las mismas claves de componentes que el resto de alertas.
- **Hora en UTC**: los timestamps usaban `datetime('now')` (UTC). Se corrige a
  hora local en el esquema y, además, `insert_alert` fija el timestamp local
  explícito (válido también en bases de datos preexistentes).
- **Bloqueo en estricto no construía el InstanceId**: se pasaba vendor_id y
  product_id vacíos, por lo que el identificador del dispositivo salía vacío.
  Ahora se recuperan de la base de datos antes de bloquear.

### Añadido
- **Elevación automática a administrador** (`security/privileges.relaunch_as_admin`):
  al arrancar, la aplicación solicita privilegios mediante UAC para que el
  bloqueo físico de dispositivos funcione. Se puede omitir con `--no-admin`
  (desarrollo o capturas).
- El diálogo de desbloqueo TOTP avisa cuando el bloqueo se ha aplicado solo de
  forma lógica por falta de privilegios de administrador.
- Helper `get_device_by_serial` en `store/database.py`.

## [2026-06-05b] — Alerta por horario, modos simplificados y migración de BD

### Añadido
- **Alerta por inserción fuera de horario**: en modo monitorización, conectar un
  USB fuera del horario habitual genera una alerta (severidad media) sin
  bloquear. En modo estricto, además, se bloquea el dispositivo.
- **Migración de esquema sin pérdida de datos** (`store/database._apply_migrations`):
  al iniciar, se añaden con ALTER TABLE las columnas que falten en una base de
  datos preexistente. Ya no es necesario borrar `tfm_usb.db` al evolucionar el
  esquema.

### Modificado
- **Modos de operación simplificados**: se elimina la casilla «enforce» del
  horario, que se solapaba con el modo estricto. Ahora el comportamiento queda
  unívoco: aprendizaje (nada), monitorización (alerta), estricto (alerta +
  bloqueo). El horario solo define la franja; la reacción la determina el modo.
- `security/schedule.py`: `set_schedule` mantiene el parámetro `enforce` por
  compatibilidad pero ya no condiciona el bloqueo.

## [2026-06-05] — Verificación TOTP, capacidad persistente, icono y modo estricto

### Añadido
- **Verificación del segundo factor (TOTP) en dos fases**: tras generar el
  secreto se muestra el QR y un campo para introducir el código; al validarlo,
  el QR y el secreto se ocultan y la vista pasa a "✓ TOTP configurado y
  verificado". El estado se persiste (`totp.verified`).
- **Icono de aplicación personalizable** (`ui/app_icon.py`): carga
  `assets/app_icon.png` para la ventana y la barra de tareas (con AppUserModelID
  en Windows). Degrada al icono por defecto si el fichero no existe.
- Columna `capacity` en la tabla `devices`.

### Corregido
- **Bloqueo por horario respeta el modo de operación**: solo se aplica en modo
  estricto. En aprendizaje y monitorización ya no se bloquea ningún dispositivo
  por inserción fuera de horario.
- **Capacidad persistente**: la capacidad de un USB de almacenamiento se guarda
  en la base de datos y se conserva cuando el dispositivo se desconecta, en
  lugar de quedar vacía. `upsert_device` preserva la capacidad anterior si la
  nueva lectura viene vacía.

## [2026-06-01] — Corrección dependencia evtx y medición de rendimiento

### Corregido
- **Dependencia de Event Logs**: `requirements.txt` declaraba `python-evtx`, pero
  el código importa el paquete `evtx` (binding de Rust). Eran librerías distintas
  y en Windows colisionan entre sí. Corregido a `evtx>=0.8.0`.
- `acquisition/evtx_reader.py`: mensaje de log corregido (ya no menciona
  «python-evtx») y manejo explícito de `PermissionError`, informando de que la
  lectura de Event Logs requiere ejecutar la aplicación como administrador. Sin
  privilegios, el sistema degrada a Registro + SetupAPI (RF15).

### Añadido
- `analytics/benchmark.py`: medición reproducible de rendimiento (RNF1 y RNF2)
  sobre un conjunto sintético equivalente a un año de actividad (1.095 sesiones).
  Resultados: análisis completo ~0,28 s (< 30 s exigidos); reacción
  detección→respuesta ~0,02 s (< 3 s exigidos). Ambos requisitos cumplidos.

## [2026-05-29d] — Rendimiento del monitor, reentreno inteligente y validación

### Mejorado
- **Monitor con muestreo diferenciado** (`monitoring/monitor_cycle.py`)
  - La actividad/idle (barata y volátil) se muestrea en cada ciclo
  - Los Event Logs de power/session (costosos vía PowerShell) solo se releen
    cada `HISTORIC_EVERY` (10) ciclos. Reduce ~⅔ las invocaciones de PowerShell
  - El hilo pasa el índice de ciclo a `run_cycle`
- **Reentreno inteligente del detector** (`analytics/pipeline.py`)
  - `load_or_train_detector` reutiliza el modelo persistido y solo reentrena si:
    se fuerza, no hay modelo, la versión cambió, o llegaron ≥10 sesiones nuevas
  - Antes se reentrenaba en cada análisis; ahora se aprovecha `model_state`
  - Nuevo getter `AnomalyDetector.n_sessions()`

### Añadido
- **Validación experimental** (`analytics/validation.py`, ejecutable con
  `python -m analytics.validation`)
  - Genera sesiones sintéticas (normal + anomalías inyectadas)
  - Calcula precisión, recall, F1, accuracy y matriz de confusión para varios
    umbrales — material directo para el capítulo de Resultados
- Tests nuevos (`tests/test_pipeline_validation.py`): reentreno inteligente
  y métricas de validación. Total: 25 tests.

## [2026-05-29c] — Allowlist, dashboard, detección de admin y tests

### Añadido
- **Allowlist de dispositivos de confianza**
  - Columna `trusted` en la tabla `devices` y helpers `set_device_trusted` /
    `get_trusted_serials`
  - Los dispositivos marcados como confiables NO generan alertas ni se bloquean
    por horario (en `analytics/pipeline.py` y `monitoring/monitor_cycle.py`)
  - Columna "Confiable" con casilla en la tabla de dispositivos; el cambio se
    persiste al instante
- **Dashboard de estadísticas** (`ui/dashboard_view.py`, pestaña "Estadísticas")
  - Gráficas matplotlib: actividad por hora, suspensiones por día, apps más
    usadas y distribución de tipos de USB
  - `analytics/stats.py`: agregaciones sobre `system_signals` y `devices`
- **Detección de privilegios** (`security/privileges.py`)
  - Avisa al arrancar si la app no tiene permisos de administrador y qué
    funciones (bloqueo físico) quedarán limitadas
- **Suite de tests automatizados** (`tests/`, pytest — 20 tests)
  - Motor de anomalías (rango del score, componentes, modo degradado,
    persistencia, severidad)
  - Horario habitual (franjas, días, cruce de medianoche) y TOTP
  - Normalización y deduplicación de dispositivos
  - Persistencia: allowlist, upsert MIN/MAX de fechas, señales idempotentes

### Modificado
- `store/models.py`: columna `trusted` en `devices`
- `ui/main_window.py`: pestaña Estadísticas, aviso de privilegios, allowlist
- `requirements.txt`: `matplotlib`, `pytest`

## [2026-05-29b] — Correcciones de detección, tipos reales y mejoras de UI

### Corregido
- **Detección de tipo y estado**: el sistema solo conocía dispositivos de
  almacenamiento (registro USBSTOR). Ahora `acquisition/live_state.py` enumera
  TODOS los USB presentes (bluetooth, cámara, HID, pantalla, etc.) con su tipo
  real derivado de la clase PnP de Windows.
- **Estado "desconectado" erróneo**: los dispositivos conectados ahora
  (no almacenamiento) salían como desconectados porque no entraban al pipeline.
  `ui/analysis_worker.py` fusiona los dispositivos en vivo con el histórico.
- **Tipo siempre "almacenamiento"**: ahora cada dispositivo muestra su tipo
  correcto (bluetooth, cámara, entrada HID, almacenamiento…).
- **Seriales de instancia falsos**: valores cortos como '5'/'6' (números de
  instancia, no seriales) se tratan como sintéticos (`VIDPID_xxxx_yyyy`) para
  evitar colisiones que ocultaban dispositivos.
- **Columna Fuentes**: muestra "tiempo real" para dispositivos detectados en
  vivo y "registro/evtx/setupapi" para los obtenidos de artefactos forenses.
- **pyotp ausente cerraba la app**: instalado en ambos intérpretes y el botón
  de generar TOTP ahora muestra un mensaje claro en vez de fallar.

### Añadido
- **Vista Básico/Experto** (selector exclusivo en la cabecera): en modo básico
  se ocultan las columnas técnicas (Nº serie, Vendor ID, Product ID, Fuentes);
  en experto se muestran todas. La preferencia se persiste (`ui.view`).

### Modificado
- Filtros de fecha: formato de visualización `dd-MM-yyyy` y celdas más anchas
  (el filtrado interno sigue siendo ISO para comparaciones correctas).
- Ajustes → Horario: `HalfHourTimeEdit`, las flechas suben/bajan 30 min exactos.

## [2026-05-29] — Monitorización continua, señales del sistema, horario y 2FA

### Añadido
- **Monitorización en segundo plano** (`monitoring/monitor.py` + `monitoring/monitor_cycle.py`)
  - `BackgroundMonitor` (QThread) sondea el sistema cada N segundos (configurable)
  - Detecta USBs recién conectados, captura señales y aplica bloqueo por horario
  - Espera interrumpible con `QWaitCondition`; arranque/parada limpios
- **Captura de señales del sistema** (nuevos readers en `acquisition/`)
  - `power_reader.py`: suspensiones (Kernel-Power 42) y reanudaciones (Power-Troubleshooter 1)
  - `session_reader.py`: logon/logoff/disconnect/reconnect (TerminalServices, sin admin)
  - `activity_reader.py`: app en primer plano (Win32) + tiempo de inactividad (GetLastInputInfo)
  - `winevent.py`: helper común para Get-WinEvent
  - Tabla `system_signals` con inserción idempotente y hash SHA-256
- **Horario habitual configurable** (`security/schedule.py`)
  - Franja horaria (soporta cruce de medianoche) + días laborables seleccionables
  - `is_anomalous_time()` decide si una inserción debe bloquearse
- **Segundo factor TOTP** (`security/totp.py`, RFC 6238, compatible Google Authenticator)
  - Secreto persistido en `config`, URI otpauth:// para QR, verificación con ventana ±1
- **Bloqueo por hora anómala + desbloqueo TOTP**
  - `prevention.block_for_schedule()`: deshabilita el USB (Disable-PnpDevice) fuera de horario
  - `prevention.unlock_device()`: reactiva con Enable-PnpDevice tras validar TOTP
  - `ui/unlock_dialog.py`: diálogo modal que exige código TOTP para reactivar
- **UI renovada**
  - `ui/theme.py`: tema visual blanco/negro/gris/azul (QSS)
  - `ui/settings_view.py`: pestaña Ajustes (horario, intervalo del monitor, TOTP)
  - `ui/monitor_control.py`: control del monitor con indicador de estado en la barra
  - Columnas y filas redimensionables por el usuario (Interactive) en ambas tablas
  - Botón "Iniciar/Detener monitor" e indicador de estado permanente

### Modificado
- `store/models.py`: tabla `system_signals`
- `store/anomaly_store.py`: nuevos valores de config (monitor, schedule, totp)
- `store/signals_store.py` (nuevo): CRUD de señales del sistema
- `analytics/prevention.py`: bloqueo/desbloqueo por horario
- `ui/main_window.py`: pestaña Ajustes, control del monitor, cierre limpio del hilo
- `main.py`: aplica el tema visual al arrancar
- `requirements.txt`: `pyotp`, `psutil`

## [2026-05-05] — Motor de anomalías + prevención + exportación JSON

### Añadido
- `analytics/behavior_model.py`: modelo de comportamiento con tres componentes
  - `HourHistogram`: histograma horario de 24 bins normalizado, score = 1 - probabilidad relativa
  - `SerialFrequency`: penalización por dispositivo poco visto (nunca visto = 1.0)
  - `MahalanobisModel`: distancia de Mahalanobis al centroide sobre [hora, duración, días_desde_última]
  - Todos los componentes serializables a/desde dict
- `analytics/anomaly_detector.py`: motor de anomalías con score = 0.4·hora + 0.3·dispositivo + 0.3·mahalanobis
  - Métodos `train(sessions)`, `score(session)`, `explain(session)`
  - Modo degradado con reglas simples si hay menos de 5 sesiones
  - Persistencia JSON via `to_payload()` / `from_payload()`
  - Versión del modelo (`MODEL_VERSION`) guardada en tabla `model_state`
- `analytics/pipeline.py`: orquestación de persistencia, entrenamiento y scoring
  - Respeta el modo: aprendizaje no genera alertas, monitorización/estricto sí
  - Carga modelo persistido o entrena desde sesiones de BD
- `analytics/prevention.py`: bloqueo temporal opcional en modo estricto
  - Por defecto bloqueo lógico (registrado en config); físico vía `Disable-PnpDevice` requiere admin
- `ui/alerts_view.py`: vista de alertas con tabla, filtros por fecha y dispositivo
  - Columnas: Fecha, Dispositivo, Serial, Severidad, Score, Motivo, Desglose
  - Color por severidad (alta=rojo, media=naranja, baja=amarillo)
- `ui/analysis_worker.py`: worker de análisis separado de `main_window.py`
- Selector de modo (aprendizaje/monitorización/estricto) en la UI
- Pestañas Dispositivos / Alertas en la ventana principal
- Botón "Exportar JSON" con `generate_json_report()` que incluye dispositivos y alertas
- Tabla `config` (clave/valor) para configuración persistente
- Tabla `model_state` (versión + payload JSON + fecha de entrenamiento)
- Columnas `score`, `components` y `session_id` añadidas a `alerts`

### Modificado
- `store/models.py`: nuevas tablas `config` y `model_state`; tabla `alerts` enriquecida
- `store/database.py`: sin cambios funcionales, solo helpers movidos a `anomaly_store.py`
- `store/anomaly_store.py` (nuevo): `get_config`, `set_config`, `insert_alert`, `get_alerts`,
  `get_all_sessions`, `save_model_state`, `load_latest_model_state`
- `normalization/correlator.py`: ahora devuelve también `sessions` (sintéticas si no hay evtx)
- `ui/main_window.py`: refactor completo con tabs y selector de modo
- `requirements.txt`: numpy/scipy ya estaban presentes (utilizados ahora por el modelo)

## [2026-04-28b] — Capacidad USB, estado en vivo, timestamps corregidos

### Añadido
- `acquisition/live_state.py`: módulo de detección en vivo de dispositivos USB conectados mediante WMI/PowerShell
- Columna "Capacidad" en tabla y en informe HTML (ej. "14.8 GB")
- Columna "Estado" (Conectado/Desconectado) en tabla y en informe HTML
- Checkbox "Solo conectados ahora" en barra de filtros
- Detección de letra de unidad para dispositivos de almacenamiento conectados

### Corregido
- `store/database.py`: upsert_device usa MIN/MAX para first_seen/last_seen, preservando el timestamp más antiguo/reciente entre BD y datos nuevos
- `ui/main_window.py`: last_seen se actualiza a la hora actual al analizar si el dispositivo está conectado

### Modificado
- `ui/device_table.py`: columnas "Capacidad" y "Estado" con color verde/gris
- `ui/filter_bar.py`: checkbox de filtro por dispositivos conectados
- `ui/main_window.py`: pipeline de análisis enriquecido con estado en vivo
- `reporting/report_generator.py`: columnas "Capacidad" y "Estado" en informe HTML

## [2026-04-28] — Fix timestamps, VID/PID reales, tipo de dispositivo y encoding

### Corregido
- `acquisition/registry_reader.py`: timestamps first_seen/last_seen ahora se obtienen de `QueryInfoKey()` (antes intentaba leer Properties con permisos de admin y fallaba silenciosamente)
- `acquisition/registry_reader.py`: VID/PID reales obtenidos cruzando USBSTOR con la clave USB vía ContainerID (antes usaba el formato Ven_/Prod_ de USBSTOR que no es VID/PID)
- `acquisition/setupapi_reader.py`: detección automática de encoding (utf-8, utf-16, cp1252) en vez de asumir utf-16
- `acquisition/setupapi_reader.py`: regex adaptada al formato real de sección del log (`>>> [Device Install ... - USB\VID_xxxx&PID_xxxx\serial]`)
- `acquisition/evtx_reader.py`: rutas de logs ampliadas para incluir Kernel-PnP Device Management y UserPnp DeviceInstall

### Añadido
- Columna `device_type` en tabla `devices` y en la UI/informe (almacenamiento, HID, audio, etc.)
- Clasificación automática de tipo de dispositivo USB mediante el campo `Service` del registro

### Modificado
- `store/models.py`: columna `device_type` en esquema SQL
- `store/database.py`: `upsert_device()` incluye `device_type`
- `normalization/normalizer.py`: pasa `device_type` en normalización
- `ui/device_table.py`: columna "Tipo" en la tabla
- `reporting/report_generator.py`: columna "Tipo" en informe HTML

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
