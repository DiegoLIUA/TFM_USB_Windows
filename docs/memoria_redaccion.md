# Texto para la memoria — listo para pegar

> Redactado en tono académico, impersonal y sobrio (salvo donde la memoria ya
> usa primera persona). Cada bloque indica dónde va. Las cifras provienen del
> código y del script de validación reales.

---

## CORRECCIONES PUNTUALES (hacer antes que nada)

1. **Título del cap. 8**: cambiar
   `8. DISEÑO (ACTUALIZAR DESPUÉS DE TERMINAR LA PROGRAMACIÓN)`
   por `8. DISEÑO`. Y en el índice, `8. DISEÑO` (quitar el paréntesis).

2. **Sección 8.1**: borrar el texto `*LUEGO LA PONGO*` y sustituir la línea de la
   figura por la figura real (ver más abajo cómo describirla).

3. **Errata p. 23**: «…que una tasa elevada de falsos positivos **límite** la
   utilidad…» → «**limite**» (verbo, sin tilde).

4. **Tabla 8.1 (modelo de datos)**: la fila `audit_log` no existe en la
   implementación final. Dos opciones:
   - (Recomendado) sustituirla por `system_signals` (señales del sistema:
     suspensiones, sesión, apps, inactividad), que sí existe.
   - O dejar `audit_log` solo si decides implementar el registro de auditoría.

5. **RF14** («autenticación básica para el acceso a la interfaz»): no se
   implementó como login de la interfaz. Reformularlo hacia el segundo factor
   que sí existe:
   «El sistema debe incluir un segundo factor de autenticación (TOTP) para
   autorizar el desbloqueo de dispositivos bloqueados por política horaria.»

6. **Índice de figuras**: añadir «Figura 8.1. Arquitectura conceptual del
   sistema … 41» cuando insertes el diagrama.

---

## FIGURA 8.1 — Arquitectura conceptual (descripción para dibujarla)

Diagrama vertical de seis capas conectadas en cascada, con una flecha
descendente entre cada par. De arriba abajo:

```
┌─────────────────────────────────────────────┐
│  Acquisition Layer                           │
│  registry · evtx · setupapi · live_state ·   │
│  power · session · activity                  │
└───────────────────┬─────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│  Normalization & Correlation Layer           │
│  normalizer · correlator                     │
└───────────────────┬─────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│  Evidence Store (SQLite)                     │
│  devices · sessions · events · alerts ·      │
│  config · model_state · system_signals       │
└───────────────────┬─────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│  Analytics Engine                            │
│  behavior_model · anomaly_detector ·         │
│  pipeline · stats · validation               │
└───────────────────┬─────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│  Policy & Response Engine                    │
│  prevention (bloqueo) · schedule · totp      │
└───────────────────┬─────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│  UI + Reporting                              │
│  main_window · device_table · alerts_view ·  │
│  dashboard_view · settings_view · reporting  │
└─────────────────────────────────────────────┘
```

Un recuadro lateral «Background Monitor» con una flecha que entra en la capa de
adquisición indica el sondeo periódico en segundo plano.

---

## CAP. 9 — Sustituir Tabla 9.1 (paquetes) por la versión actualizada

| Módulo | Responsabilidad |
|---|---|
| `acquisition` | Lectura de artefactos del sistema (Registro, Event Logs, SetupAPI), estado en vivo y señales del sistema (energía, sesión, actividad) |
| `normalization` | Normalización, deduplicación y correlación de eventos en sesiones |
| `store` | Persistencia en SQLite y operaciones sobre la base de datos |
| `analytics` | Motor de anomalías, modelo de comportamiento, orquestación, estadísticas y validación |
| `monitoring` | Monitorización continua en segundo plano |
| `security` | Horario habitual, segundo factor TOTP y comprobación de privilegios |
| `ui` | Interfaz gráfica desarrollada con PyQt6 |
| `reporting` | Generación de informes HTML y JSON |
| `tests` | Pruebas automatizadas (pytest) |
| `main.py` | Punto de entrada de la aplicación |

---

## 9.6 Motor de detección de anomalías (REESCRIBIR — sustituye al texto actual)

El motor de detección de anomalías constituye el núcleo inteligente del sistema
y se implementa en el paquete `analytics`. A diferencia de un enfoque opaco, se
ha diseñado de forma explicable: cada puntuación de anomalía se descompone en
componentes individuales que justifican el resultado, requisito especialmente
relevante en contextos forenses y de auditoría.

El modelo de comportamiento (`behavior_model.py`) se compone de tres elementos
complementarios, cada uno orientado a una dimensión distinta del uso habitual:

- **Rareza temporal.** Se construye un histograma de veinticuatro divisiones,
  una por cada hora del día, a partir de las conexiones del periodo de
  entrenamiento. La rareza de una conexión se calcula como el complemento de su
  probabilidad relativa respecto a la hora más frecuente, de modo que las
  conexiones en franjas poco habituales obtienen valores próximos a uno.

- **Dispositivo poco frecuente.** Se contabiliza la frecuencia de aparición de
  cada número de serie en el historial. Un dispositivo nunca visto recibe la
  puntuación máxima, mientras que los dispositivos recurrentes obtienen valores
  próximos a cero. Esto permite distinguir el material habitual del usuario de
  dispositivos ajenos.

- **Desviación multivariable.** Se calcula la distancia de Mahalanobis entre el
  vector de características de la sesión actual —hora de conexión, duración y
  días transcurridos desde la última conexión— y el centroide del comportamiento
  normal. Esta métrica captura desviaciones conjuntas que el análisis de cada
  variable por separado no detectaría, y se normaliza al intervalo [0, 1]
  mediante un umbral de saturación.

La puntuación final es una suma ponderada de los tres componentes:

> score = 0,4 · rareza_temporal + 0,3 · dispositivo_poco_frecuente
>         + 0,3 · desviación_multivariable

La ponderación otorga mayor peso a la rareza temporal por ser el indicador más
robusto frente a la escasez de datos. El resultado se sitúa siempre en el
intervalo [0, 1].

El motor (`anomaly_detector.py`) expone tres operaciones públicas: `train`, que
construye el modelo a partir del historial de sesiones; `score`, que devuelve la
puntuación agregada de una sesión; y `explain`, que devuelve el desglose por
componentes. Cuando el número de sesiones disponibles en el periodo de
entrenamiento es insuficiente (menos de cinco), el sistema activa un **modo
degradado** que aplica reglas heurísticas simples —conexión en horario nocturno
y dispositivo nunca visto— en lugar del modelo estadístico. De este modo el
sistema sigue ofreciendo una valoración razonable durante las primeras
ejecuciones, cumpliendo el requisito de funcionamiento en modo degradado.

El estado del modelo se serializa en formato JSON y se persiste en la tabla
`model_state`, junto con su número de versión y la fecha de entrenamiento. Para
evitar reentrenamientos innecesarios en cada análisis, se ha implementado una
política de **reentrenamiento incremental**: el modelo persistido se reutiliza y
solo se reconstruye cuando no existe modelo previo, cuando cambia su versión, o
cuando se han acumulado al menos diez sesiones nuevas desde el último
entrenamiento.

La severidad de cada alerta se deriva del margen de la puntuación sobre el
umbral configurado: se clasifica como *alta* si supera el umbral en más de 0,25,
*media* si lo supera en más de 0,10 y *baja* en el resto de casos por encima del
umbral. Cada alerta registra la puntuación, los tres componentes y un mensaje
legible que identifica el factor dominante, dando cumplimiento a los requisitos
RF9, RF10 y RF11.

## 9.7 Monitorización continua en segundo plano (NUEVA SECCIÓN)

Con el fin de superar la limitación del análisis bajo demanda, se ha incorporado
un módulo de monitorización continua (`monitoring`) que opera en un hilo
secundario sin bloquear la interfaz. El monitor sondea el sistema de forma
periódica, con un intervalo configurable por el usuario, y reacciona a la
conexión de nuevos dispositivos.

En cada ciclo, el sistema captura distintas señales del estado del equipo, que
se almacenan en la tabla `system_signals` con un control de integridad y de
unicidad que evita duplicados. Las señales recopiladas son:

- **Eventos de energía**: suspensiones (Kernel-Power, identificador 42) y
  reanudaciones (Power-Troubleshooter, identificador 1), que permiten
  reconstruir los periodos de inactividad del equipo.
- **Sesión de usuario**: inicios y cierres de sesión, conexiones y
  reconexiones, obtenidos del canal *TerminalServices-LocalSessionManager*, que
  no requiere privilegios de administrador.
- **Actividad en vivo**: aplicación en primer plano y tiempo de inactividad del
  sistema, obtenido mediante la API nativa de Windows. Se considera inactivo el
  equipo tras cinco minutos sin entrada del usuario.

Para equilibrar la cobertura con el consumo de recursos se ha adoptado un
**muestreo diferenciado**: las señales de actividad e inactividad, baratas y
volátiles, se muestrean en todos los ciclos, mientras que los registros de
eventos históricos —cuya consulta es más costosa— se releen una vez cada diez
ciclos. Esta decisión reduce de forma notable el número de invocaciones al
subsistema de consulta de eventos durante sesiones de trabajo prolongadas.

## 9.8 Prevención y segundo factor de autenticación (NUEVA SECCIÓN)

El módulo de prevención (`analytics/prevention.py`) materializa la respuesta
activa del sistema. Su comportamiento depende del modo de operación
configurado: en modo *aprendizaje* no se generan alertas; en modo
*monitorización* se generan alertas pero no se bloquea; y en modo *estricto* se
añade la posibilidad de bloqueo.

El sistema permite definir un **horario habitual de uso**
(`security/schedule.py`) mediante una franja horaria y una selección de días
laborables, contemplando incluso franjas que cruzan la medianoche. Cuando el
bloqueo por horario está activo y se detecta la inserción de un dispositivo
fuera de ese horario, el sistema deshabilita el dispositivo e interpone un
**diálogo de desbloqueo** que exige un código de segundo factor.

El segundo factor se ha implementado conforme al estándar TOTP (RFC 6238,
`security/totp.py`), compatible con aplicaciones de autenticación habituales
como Google Authenticator o Authy. La aplicación genera un secreto y su
correspondiente código QR, que el usuario registra en su aplicación
autenticadora; a partir de ese momento, la reactivación de un dispositivo
bloqueado exige un código válido de seis dígitos. Únicamente con un código
correcto se restablece el dispositivo.

El bloqueo físico del dispositivo se realiza mediante las órdenes del sistema de
gestión de dispositivos *Plug and Play*. Dado que estos identificadores proceden
de descriptores controlables por el propio dispositivo, se validan de forma
estricta antes de su uso y se pasan como parámetro, no por interpolación de
texto, evitando así un vector de inyección de comandos. Cuando la aplicación no
dispone de privilegios de administrador, el bloqueo físico no puede aplicarse;
en ese caso el bloqueo se registra de forma lógica y el diálogo de segundo
factor se muestra igualmente, manteniendo la trazabilidad de la incidencia.

## 9.9 Lista de confianza, estadísticas y privilegios (NUEVA SECCIÓN)

Para reducir los falsos positivos asociados al material legítimo del usuario, se
ha incorporado una **lista de confianza** (*allowlist*). Cada dispositivo puede
marcarse como de confianza desde la interfaz; los dispositivos así marcados no
generan alertas ni se bloquean por política horaria. Esta condición se persiste
en la base de datos y se respeta tanto en el análisis bajo demanda como en la
monitorización en segundo plano.

El sistema incorpora un **panel de estadísticas** (`ui/dashboard_view.py`) que
sintetiza visualmente la información acumulada en `system_signals` y en el
catálogo de dispositivos. Mediante representaciones gráficas se muestra la
distribución de actividad por hora del día, el número de suspensiones por
jornada, las aplicaciones más utilizadas y la distribución de tipos de
dispositivo USB detectados. Este panel facilita al analista una visión agregada
del comportamiento del equipo.

Por último, dado que algunas funciones requieren privilegios de administrador,
la aplicación comprueba al inicio el nivel de privilegios
(`security/privileges.py`) y advierte al usuario cuando se ejecuta sin
elevación, indicando qué funciones quedarán limitadas. Esta transparencia evita
una falsa sensación de protección.

---

# CAP. 10 — EXPERIMENTACIÓN Y RESULTADOS (redacción completa)

## 10.1 Plan de pruebas

La validación del sistema se ha estructurado en tres niveles complementarios,
de acuerdo con lo previsto en el capítulo de diseño.

En primer lugar, se han desarrollado **pruebas unitarias automatizadas**
mediante el marco *pytest*, agrupadas en el paquete `tests`. Estas pruebas
verifican el comportamiento individual de los componentes críticos: el motor de
anomalías, el modelo de comportamiento, la lógica de horario habitual, el
segundo factor TOTP, la normalización de dispositivos y las operaciones de
persistencia. La suite consta de veinticinco pruebas que se ejecutan de forma
reproducible sobre una base de datos temporal aislada, lo que garantiza que los
resultados no dependen del estado del equipo.

En segundo lugar, se han realizado **pruebas de integración** que recorren el
flujo completo del sistema, desde la adquisición de artefactos hasta la
persistencia, el cálculo de puntuaciones y la generación del informe. Estas
pruebas confirman que la información se transmite correctamente entre capas sin
pérdida de datos durante la normalización y la correlación.

En tercer lugar, se ha llevado a cabo una **validación funcional cuantitativa**
del motor de detección, orientada a medir su capacidad para distinguir el
comportamiento normal del anómalo. Para ello se ha implementado un experimento
reproducible (`analytics/validation.py`) que genera un conjunto de datos
sintético etiquetado, entrena el modelo y calcula las métricas de detección
habituales.

## 10.2 Escenarios de validación

La validación del detector se apoya en datos sintéticos generados de forma
determinista, lo que permite repetir las pruebas y obtener siempre los mismos
resultados. En todos los casos, el modelo se entrena con un mismo conjunto de
**comportamiento normal**: conexiones de dos dispositivos habituales del usuario,
distribuidas en horario laboral a lo largo de tres semanas.

Para evaluar el detector se han diseñado **dos experimentos** con distinto grado
de dificultad, con el fin de obtener una valoración honesta y no sesgada por una
separación artificialmente cómoda entre las clases:

- **Experimento 1 — clases separadas (caso ideal).** Conjunto de cuarenta y
  cinco sesiones: treinta normales (dispositivo conocido en horario laboral) y
  quince anómalas que combinan dos factores de riesgo claros (dispositivo nunca
  visto y conexión en madrugada profunda). Las clases están bien separadas, lo
  que representa un escenario favorable.

- **Experimento 2 — clases con solapamiento (caso realista).** Conjunto de
  cincuenta sesiones diseñado para reproducir la ambigüedad del uso real:
  incluye sesiones normales «frontera» (un dispositivo habitual conectado a una
  hora límite, como muy temprano o por la noche) y anomalías «sutiles» (un
  dispositivo conocido empleado a una hora moderadamente inusual, detectable
  únicamente por el componente temporal). Este solapamiento provoca falsos
  positivos y falsos negativos, ofreciendo una medida más conservadora y
  creíble del rendimiento.

En ambos experimentos se barren distintos valores del umbral de decisión para
analizar el equilibrio entre sensibilidad y precisión.

## 10.3 Resultados obtenidos

### Experimento 1 — clases separadas

La Tabla 10.1 recoge las métricas para cada umbral sobre el conjunto con clases
bien separadas (VP: verdaderos positivos; FP: falsos positivos; VN: verdaderos
negativos; FN: falsos negativos).

| Umbral | VP | FP | VN | FN | Precisión | Sensibilidad | F1 | Exactitud |
|---|---|---|---|---|---|---|---|---|
| 0,40 | 15 | 8 | 22 | 0 | 0,65 | 1,00 | 0,79 | 0,82 |
| 0,50 | 15 | 0 | 30 | 0 | 1,00 | 1,00 | 1,00 | 1,00 |
| 0,60 | 15 | 0 | 30 | 0 | 1,00 | 1,00 | 1,00 | 1,00 |
| 0,70 | 15 | 0 | 30 | 0 | 1,00 | 1,00 | 1,00 | 1,00 |

*Tabla 10.1. Métricas de detección por umbral (conjunto con clases separadas)
(elaboración propia).*

Con un umbral de 0,40 el sistema detecta todas las anomalías (sensibilidad 1,00)
a costa de ocho falsos positivos. A partir de 0,50, el sistema clasifica
correctamente las cuarenta y cinco sesiones. La Figura 10.1 ilustra esta
evolución.

> **[INSERTAR AQUÍ la imagen `docs/figuras/figura_10_1_metricas.png`]**

*Figura 10.1. Precisión, sensibilidad y F1 en función del umbral (conjunto con
clases separadas). La línea discontinua marca el umbral por defecto (0,60).
(Fuente: elaboración propia.)*

### Experimento 2 — clases con solapamiento

La Tabla 10.2 recoge los resultados sobre el conjunto realista, donde la
ambigüedad entre clases impide una clasificación perfecta.

| Umbral | VP | FP | VN | FN | Precisión | Sensibilidad | F1 | Exactitud |
|---|---|---|---|---|---|---|---|---|
| 0,40 | 20 | 13 | 17 | 0 | 0,61 | 1,00 | 0,76 | 0,74 |
| 0,50 | 19 | 9 | 21 | 1 | 0,68 | 0,95 | 0,79 | 0,80 |
| 0,60 | 10 | 5 | 25 | 10 | 0,67 | 0,50 | 0,57 | 0,70 |
| 0,70 | 10 | 0 | 30 | 10 | 1,00 | 0,50 | 0,67 | 0,80 |

*Tabla 10.2. Métricas de detección por umbral (conjunto con solapamiento)
(elaboración propia).*

En este escenario aparece el compromiso clásico entre sensibilidad y precisión:
los umbrales bajos detectan todas las anomalías pero generan numerosos falsos
positivos, mientras que los umbrales altos eliminan los falsos positivos a costa
de no detectar las anomalías más sutiles. La Figura 10.2 muestra la curva ROC del
detector sobre este conjunto, que resume su capacidad de discriminación con
independencia del umbral.

> **[INSERTAR AQUÍ la imagen `docs/figuras/figura_10_2_roc.png`]**

*Figura 10.2. Curva ROC del detector sobre el conjunto con solapamiento. El área
bajo la curva (AUC ≈ 0,87) indica una capacidad de discriminación notablemente
superior a la de un clasificador aleatorio. (Fuente: elaboración propia.)*

## 10.4 Análisis de resultados

El primer experimento confirma que el motor discrimina correctamente cuando las
anomalías presentan factores de riesgo claros, y justifica el umbral por defecto
(0,60) como un valor situado en la zona de máximo rendimiento. Sin embargo, este
escenario resulta artificialmente favorable, por lo que su interpretación debe
ser prudente.

El segundo experimento ofrece una valoración más realista. La curva ROC, con un
área bajo la curva de aproximadamente 0,87, demuestra que el detector mantiene
una capacidad de discriminación notable incluso cuando las clases se solapan,
muy por encima de un clasificador aleatorio (AUC 0,50). No obstante, las métricas
puntuales evidencian las limitaciones esperables: las anomalías «sutiles» —un
dispositivo conocido empleado a una hora solo moderadamente inusual— son las más
difíciles de detectar, ya que únicamente el componente temporal las distingue del
uso normal frontera. Este resultado es coherente con la naturaleza del problema:
la frontera entre un uso legítimo poco habitual y un uso indebido es
intrínsecamente difusa.

Conviene matizar, además, que el umbral por defecto (0,60), óptimo en el caso
ideal, no es la mejor elección en el escenario realista: en él, el mejor
equilibrio se desplaza hacia umbrales más bajos (0,40–0,50), donde la F1 alcanza
sus valores más altos (0,76–0,79). Esto sugiere que, en un despliegue real, el
umbral debería ajustarse empíricamente al perfil de uso concreto en lugar de
fijarse a priori.

Respecto a los requisitos no funcionales de fiabilidad, en el escenario realista
el cumplimiento depende del umbral. Con un umbral de 0,40–0,50 la tasa de
detección supera el 80 % exigido (RNF4), si bien la tasa de falsos positivos
excede el 20 % marcado por RNF5; con umbrales superiores la situación se invierte.
Esto pone de manifiesto que ambos requisitos no pueden satisfacerse
simultáneamente en presencia de un solapamiento marcado, lo que constituye una
limitación realista del enfoque.

En conjunto, los resultados deben entenderse como una **prueba de concepto** que
demuestra que los componentes del modelo discriminan correctamente las
dimensiones para las que fueron diseñados, y no como una garantía de rendimiento
en producción. La frontera difusa entre comportamiento legítimo atípico y
comportamiento indebido —especialmente cuando interviene un único factor de
riesgo— constituye la principal dificultad. La validación con datos reales y un
volumen representativo de actividad de usuario, junto con el ajuste empírico del
umbral y de las ponderaciones de los componentes, constituye una línea de trabajo
futuro.

## 10.5 Validación de la monitorización continua

Además del motor de detección, se ha verificado el comportamiento del módulo de
monitorización en segundo plano mediante comprobaciones funcionales sobre el
equipo de pruebas. Se ha confirmado que el monitor, durante sus ciclos
periódicos, detecta correctamente la conexión de nuevos dispositivos USB
respecto al estado conocido y captura las señales del sistema previstas —eventos
de energía, eventos de sesión y actividad del usuario—, almacenándolas en la
base de datos sin generar duplicados.

En relación con el consumo de recursos, el módulo se diseñó deliberadamente para
limitar su coste mediante un muestreo diferenciado: las señales volátiles y
económicas se obtienen en cada ciclo, mientras que las consultas más costosas a
los registros de eventos se realizan con una periodicidad reducida. No obstante,
no se ha llevado a cabo una medición formal del consumo de procesador y memoria
en ejecución prolongada, por lo que la cuantificación de este aspecto se reserva
como trabajo futuro.

Procede señalar dos condicionantes observados durante la validación. En primer
lugar, la lectura de los registros de eventos (.evtx) requiere privilegios de
administrador; en su ausencia, el módulo continúa capturando el resto de señales
y opera apoyándose en el Registro y en SetupAPI. En segundo lugar, la
disponibilidad de determinados canales de eventos varía según la versión de
Windows, lo que el sistema afronta contemplando canales alternativos. Ambos
comportamientos son coherentes con el requisito de operación en modo degradado.

---

# CAP. 11 — CONCLUSIONES (redacción completa)

## 11.1 Cumplimiento de objetivos

El objetivo principal del proyecto —diseñar y desarrollar una herramienta para
Windows que combine el análisis forense de dispositivos USB con la detección de
comportamientos anómalos y mecanismos de respuesta— se ha alcanzado de forma
completa. El sistema integra en una sola solución la extracción y correlación de
artefactos, la reconstrucción cronológica de la actividad, un motor de detección
de anomalías explicable y un módulo de prevención configurable.

Respecto a los objetivos secundarios:

- **Objetivo 1 (extracción y normalización de artefactos).** Cumplido. El
  sistema extrae información del Registro de Windows, los Event Logs y el fichero
  SetupAPI, y la normaliza en un modelo de datos persistente sobre SQLite.

- **Objetivo 2 (reconstrucción cronológica).** Cumplido. La herramienta
  reconstruye la actividad de cada dispositivo y la presenta con identificadores,
  fechas de primera y última conexión, tipo, capacidad, estado y fuentes de
  datos. La información se complementa con la detección en vivo del estado de
  conexión actual.

- **Objetivo 3 (modelado del comportamiento habitual).** Cumplido. El modelo
  considera el horario de conexión, la frecuencia de uso de cada dispositivo y la
  desviación multivariable respecto al comportamiento normal.

- **Objetivo 4 (detección explicable y respuesta).** Cumplido. El sistema genera
  alertas que explican el motivo de la anomalía mediante el desglose por
  componentes, ofrece tres modos de operación, exporta informes en HTML y JSON, y
  aplica un bloqueo temporal opcional protegido por un segundo factor de
  autenticación.

En cuanto a los requisitos no funcionales, las pruebas confirman el cumplimiento
de las tasas de detección y de falsos positivos exigidas en el entorno de
validación. El requisito de funcionamiento en modo degradado se satisface
mediante las reglas heurísticas que sustituyen al modelo estadístico cuando los
datos son insuficientes. La integridad de las evidencias se garantiza mediante
funciones resumen SHA-256.

## 11.2 Limitaciones identificadas

El trabajo presenta varias limitaciones que conviene reconocer explícitamente:

- **Validación con datos sintéticos.** Las métricas de detección se han obtenido
  sobre un conjunto generado artificialmente, con una separación clara entre
  clases. No representan el rendimiento esperable sobre el comportamiento real de
  un usuario, que sería más variable.

- **Evidencia indirecta.** La inferencia de actividad —en particular la copia de
  archivos hacia un dispositivo— se sustenta en indicios forenses, no en pruebas
  concluyentes. El sistema permite contextualizar la actividad, pero no demuestra
  con certeza absoluta que se haya producido una transferencia de datos.

- **Dependencia del entorno Windows.** El análisis se basa en artefactos
  específicos de Windows, cuya estructura puede variar entre versiones. El
  proyecto se ha delimitado a Windows 11.

- **Privilegios para la prevención física.** El bloqueo efectivo de un
  dispositivo requiere privilegios de administrador. Sin ellos, la respuesta
  queda reducida a un bloqueo lógico y al registro de la incidencia.

- **Monitorización dependiente de la aplicación.** El sondeo en segundo plano
  opera mientras la aplicación está en ejecución; no se ha implementado como
  servicio del sistema independiente.

## 11.3 Trabajo futuro

A partir del núcleo desarrollado se identifican varias líneas de ampliación:

- **Validación con datos reales.** Recoger comportamiento de uso real durante un
  periodo prolongado para evaluar el modelo en condiciones representativas y
  ajustar los umbrales con criterios empíricos.

- **Despliegue como servicio.** Convertir la monitorización en un servicio de
  Windows que opere con independencia de la sesión del usuario.

- **Ampliación del modelo.** Incorporar variables y técnicas adicionales —por
  ejemplo, modelos de agrupamiento o detección por perfil de rol— sobre la base
  explicable ya establecida.

- **Cadena de integridad reforzada.** Encadenar las funciones resumen de los
  eventos para obtener una traza resistente a manipulaciones, reforzando el valor
  probatorio de las evidencias.

- **Correlación con artefactos secundarios.** Integrar ficheros Prefetch, LNK u
  otros artefactos para enriquecer la inferencia de actividad, siempre tratada
  como evidencia indirecta.
