# Revisión de coherencia entre capítulos

Análisis cruzado de la memoria contra el código real y entre capítulos.
Clasificado por gravedad. Cada punto indica el capítulo afectado y la acción.

---

## 🔴 INCOHERENCIAS QUE HAY QUE CORREGIR

### C1. Stack tecnológico (Tabla 8.2) desactualizado
**Dónde:** cap. 8.3, Tabla 8.2.
**Problema:** la tabla no refleja las dependencias reales del proyecto.
- **Falta**: `pyotp` (segundo factor), `qrcode` (QR del TOTP), `matplotlib`
  (dashboard), `pytest` (pruebas), `psutil` (actividad).
- **Sobra / inexacto**: `PyInstaller` aparece como empaquetado, pero el proyecto
  no se empaqueta con PyInstaller (no hay `.spec` ni referencia). O se elimina, o
  se marca como "previsto, no aplicado".
**Acción:** sustituir la Tabla 8.2 por la versión corregida de abajo.

### C2. RF14 contradice lo implementado
**Dónde:** cap. 7.2 (RF14) y cap. 9.
**Problema:** RF14 dice "autenticación básica para el acceso a la interfaz". No
existe login de la interfaz. Lo que sí existe es el segundo factor TOTP para
desbloquear dispositivos. Ya señalado en la redacción; aquí se confirma que es
una incoherencia de requisito, no solo de redacción.
**Acción:** reformular RF14 (ver propuesta en memoria_redaccion.md, corrección 5).

### C3. Tabla 8.1 (modelo de datos) no coincide con la BD real
**Dónde:** cap. 8.2, Tabla 8.1.
**Problema:** la tabla lista `audit_log`, que no existe en el código. Y omite
`system_signals`, que sí existe y es central para la monitorización.
**BD real:** devices, sessions, events, alerts, config, model_state,
system_signals (7 tablas).
**Acción:** quitar `audit_log` y añadir `system_signals`.

### C4. RF6 (informes HTML y JSON) — coherente, pero el diseño solo menciona HTML
**Dónde:** cap. 7.2 (RF6 pide HTML+JSON) vs cap. 8.4 (diseño de interfaz solo
habla de exportar en HTML).
**Problema:** el requisito y la implementación contemplan HTML y JSON, pero el
diseño de la interfaz (8.4) solo menciona HTML. Inconsistencia menor de diseño.
**Acción:** en 8.4, añadir "y JSON" donde menciona la exportación de informes.

### C5. Lectura de Event Logs (.evtx): expectativa vs realidad  ✅ INVESTIGADO
**Dónde:** caps. 4.2.2, 7.2 (RF1), 9.2/9.3.
**Hallazgos tras verificación en el equipo real:**

1. **Bug de dependencia (CORREGIDO en código).** El `requirements.txt` declaraba
   `python-evtx`, pero el código importa `from evtx import PyEvtxParser`, que
   pertenece a OTRO paquete (`evtx`, binding de Rust). Son librerías distintas
   con el mismo propósito. Por eso el sistema mostraba siempre «python-evtx no
   disponible» y nunca leía eventos. Además, en Windows ambos paquetes colisionan
   (`evtx` vs `Evtx`, el sistema de ficheros no distingue mayúsculas). **Acción
   aplicada:** `requirements.txt` corregido a `evtx>=0.8.0`; instalado el paquete
   correcto; mensaje de log corregido.

2. **El canal DriverFrameworks-UserMode NO existe en el Windows 11 de pruebas.**
   Solo están disponibles los canales *Kernel-PnP* y *UserPnp*. El código ya los
   contempla, pero la memoria (4.2.2) solo cita DriverFrameworks.

3. **La lectura de .evtx requiere privilegios de administrador.** Verificado: sin
   elevación, el acceso a `C:\Windows\System32\winevt\Logs\*.evtx` devuelve
   *Acceso denegado* (ni siquiera se pueden copiar). Con la librería ya instalada,
   el `import` funciona, pero la lectura falla por permisos. **Acción aplicada:**
   el reader ahora captura `PermissionError` y emite un aviso claro («requiere
   ejecutar como administrador») en lugar de un error genérico; el sistema degrada
   a Registro + SetupAPI (coherente con RF15).

**Acción en la MEMORIA:**
- En **4.2.2**, añadir la frase propuesta (sección de textos) sobre Kernel-PnP
  como alternativa a DriverFrameworks.
- En **9.3 o en limitaciones (11.2)**, documentar que la lectura de Event Logs
  requiere privilegios de administrador y que, sin ellos, el sistema opera en
  modo degradado con Registro y SetupAPI. Esto es una limitación honesta y
  coherente con el riesgo «variaciones en artefactos de Windows» (Tabla 2.1) y
  con RF15.
- En **8.3 (stack)**, la fila de Event Logs debe decir `evtx` (no `python-evtx`).

---

## 🟡 COHERENCIA INTERNA A REFORZAR (no son errores, mejoran la solidez)

### C6. El cap. 8 (Diseño) no anticipa funcionalidades que sí se implementaron
**Dónde:** cap. 8 completo.
**Observación:** el diseño describe 6 capas y el motor de anomalías, pero no
menciona: monitorización en segundo plano, segundo factor TOTP, horario
habitual, lista de confianza, dashboard ni comprobación de privilegios. Como el
capítulo 9 (implementación) sí los desarrolla, conviene que el diseño los
anticipe, aunque sea brevemente, para que no parezcan añadidos sin planificar.
**Acción sugerida:** añadir un párrafo corto al final de 8.1 o 8.5 mencionando
que la capa de respuesta incorpora prevención con segundo factor y que se prevé
un módulo de monitorización continua. (Texto propuesto abajo.)

### C7. Trazabilidad de requisitos en Conclusiones  ✅ RNF1/RNF2 YA MEDIDOS
**Dónde:** cap. 11.1 vs cap. 7.2.
**Observación:** la redacción de 11.1 cubre los objetivos secundarios, pero no
hace un repaso explícito requisito a requisito.

**DECISIÓN DEL AUTOR: la tabla de rendimiento NO se incluye en la memoria.**
Motivo: el benchmark mide el coste de puntuar 1.095 sesiones ya almacenadas, no
el procesamiento de «un año de actividad» real; presentarlo como prueba de RNF1
resultaría engañoso. Por coherencia y honestidad, RNF1 y RNF2 se tratan como
**requisitos no verificados formalmente**, igual que RNF3.

El script `analytics/benchmark.py` se conserva en el repositorio como
herramienta de medición interna, pero sus cifras NO se presentan como
cumplimiento cuantitativo de RNF1/RNF2 en la memoria.

**Requisitos que conviene matizar (no verificados formalmente):**
  - **RNF1/RNF2** (rendimiento < 30 s / < 3 s): el procesamiento del modelo es
    ligero, pero no se ha realizado una medición representativa sobre un volumen
    real de actividad. Declararlos como no verificados formalmente en 11.2.
  - **RF14** (login de interfaz): no implementado como tal; sustituido por el 2FA
    de desbloqueo de dispositivos. Declararlo así en 11.1/11.2.
  - **RNF3** (precisión identificación ≥95 %): la identificación por número de
    serie y VID/PID es exacta cuando los artefactos están presentes, pero no se
    ha cuantificado como porcentaje sobre un conjunto etiquetado. Mejor
    presentarlo como «identificación exacta sobre los artefactos disponibles» en
    lugar de afirmar el 95 %.
**Acción sugerida:** en 11.2 (limitaciones) reconocer que RNF1, RNF2 y RNF3 no se
han verificado con métricas formales, y matizar RF14.

### C8. Cap. 10 menciona "pruebas de integración" — verificar alcance
**Dónde:** cap. 10.1 (redacción nueva).
**Observación:** se mencionan pruebas de integración. En el repositorio, la suite
`tests/` es fundamentalmente unitaria y de pipeline (reentreno, validación). El
flujo completo se ha verificado de forma manual/headless, no con un test de
integración automatizado dedicado.
**Acción sugerida:** o se matiza que la integración se validó de forma manual
sobre el equipo de pruebas, o se rebaja la afirmación a "comprobaciones de
integración del flujo". No afirmar una batería de tests de integración que no
está en el repositorio.

---

## 🟢 COHERENCIA CORRECTA (no tocar)

- **Objetivos (cap. 5) ↔ Requisitos (cap. 7) ↔ Implementación (cap. 9).** La
  trazabilidad objetivo→RF está bien planteada y se cumple en el código.
- **Estado del arte (cap. 4) ↔ Propuesta.** La tabla 4.2 posiciona el trabajo en
  el hueco identificado (forense + comportamiento + anomalías + prevención), y el
  sistema implementado cubre las cuatro columnas. Coherente.
- **Riesgos (Tabla 2.1) ↔ Realidad.** Los riesgos previstos (falsos positivos,
  datos insuficientes, variabilidad de Windows, alcance) se corresponden con las
  decisiones tomadas (modo degradado, umbral configurable, alcance Windows 11).
  Muy coherente; incluso puedes referenciarlo en conclusiones.
- **Metodología (cap. 6) ↔ Desarrollo.** El enfoque incremental (MVP forense →
  IA+prevención) coincide con cómo se construyó realmente. El uso de Git y
  CHANGELOG.md es real.
- **RF12 (tres modos) y RF13 (bloqueo en estricto).** Implementados y coherentes.
- **RF6 (HTML+JSON).** Ambos formatos existen.
- **RNF8 (integridad por hash).** SHA-256 real en eventos y señales.
- **Restricciones (7.4): solo Windows, evidencia indirecta.** Respetadas en todo
  el documento y en el código.

---

## TEXTOS PROPUESTOS

### Tabla 8.2 corregida (stack tecnológico)

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3 |
| Interfaz | PyQt6 |
| Base de datos | SQLite |
| Registro Windows | python-registry / acceso nativo (winreg) |
| Event Logs | python-evtx (con degradación si no está disponible) |
| Estado en vivo | WMI / PowerShell |
| Análisis numérico | numpy, scipy, pandas |
| Gráficas | matplotlib |
| Segundo factor | pyotp (TOTP) + qrcode |
| Actividad del sistema | psutil / WinAPI (ctypes) |
| Informes | Jinja2 (HTML) + JSON |
| Pruebas | pytest |
| Control de versiones | Git |
| Bloqueo temporal | Disable/Enable-PnpDevice (PowerShell) |

> Nota: se ha retirado PyInstaller, ya que el empaquetado en ejecutable no se ha
> abordado en este alcance.

### Párrafo para añadir al final de 8.5 (anticipar prevención y monitor)

«Más allá del cálculo de la puntuación, la capa de respuesta se diseña para
operar en tres modos —aprendizaje, monitorización y estricto— y para incorporar
medidas preventivas configurables. Entre ellas se contempla el bloqueo temporal
de un dispositivo cuando su inserción se produce fuera del horario habitual de
uso, condicionando su reactivación a un segundo factor de autenticación.
Asimismo, se prevé un módulo de monitorización continua que, ejecutándose en
segundo plano, capture señales del sistema y reaccione a la conexión de nuevos
dispositivos sin necesidad de un análisis manual.»

### Frase para añadir en 4.2.2 (Event Logs, tras citar DriverFrameworks)

«Conviene señalar que la disponibilidad de este canal puede variar entre
versiones y configuraciones de Windows; en ausencia del registro
*DriverFrameworks-UserMode*, los canales *Kernel-PnP* ofrecen información
equivalente sobre la configuración y gestión de dispositivos, lo que permite
mantener la reconstrucción cronológica.»

### Rendimiento (RNF1/RNF2): NO se incluye tabla en la memoria

Decisión del autor (justificada): el benchmark mide el coste de puntuar 1.095
sesiones ya almacenadas, no el procesamiento de un año de actividad real, por lo
que presentarlo como prueba de RNF1 sería engañoso. RNF1 y RNF2 se tratan como
no verificados formalmente (ver texto de 11.2 más abajo).

### Texto para 11.1/11.2 sobre requisitos parcialmente cubiertos

«Algunos requisitos no funcionales no se han verificado mediante métricas
formales. Los requisitos de rendimiento (RNF1 y RNF2) no se han evaluado sobre un
volumen de actividad representativo, si bien la naturaleza ligera del modelo
—basado en un histograma, un conteo de frecuencias y una operación matricial de
dimensión reducida— hace previsible un coste de procesamiento contenido. La
precisión en la identificación de dispositivos (RNF3) es exacta sobre los
artefactos disponibles, aunque no se ha cuantificado como porcentaje sobre un
conjunto etiquetado independiente. El requisito RF14 se ha reorientado: en lugar
de una autenticación de acceso a la interfaz, se ha implementado un segundo
factor (TOTP) que protege la reactivación de dispositivos bloqueados, por
considerarse una medida de seguridad más alineada con el objetivo de prevención
del sistema. Finalmente, la lectura de los registros de eventos (.evtx) requiere
privilegios de administrador; en su ausencia, el sistema mantiene su
funcionamiento apoyándose en el Registro y en SetupAPI, conforme al requisito de
operación en modo degradado (RF15).»

---

## RESUMEN DE ACCIONES SOBRE EL CÓDIGO (ya aplicadas en esta sesión)

1. `requirements.txt`: `python-evtx` → `evtx>=0.8.0` (paquete correcto).
2. `acquisition/evtx_reader.py`: mensaje de log corregido y manejo explícito de
   `PermissionError` con aviso de «requiere administrador».
3. `analytics/benchmark.py` (nuevo): herramienta interna de medición de tiempos.
   Sus cifras NO se presentan en la memoria como cumplimiento de RNF1/RNF2 (ver
   decisión arriba); se conserva como utilidad de medición del repositorio.
4. Suite de tests: sigue en verde (25/25) tras los cambios.
