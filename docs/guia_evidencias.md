# Guía de captura de evidencias para la defensa

Cómo generar un escenario forense creíble con la aplicación y qué capturas tomar
para la memoria y la demostración. Pensado para ejecutarse en los días previos a
la defensa.

> **Importante antes de empezar:** lanza la aplicación **como administrador**
> (clic derecho → «Ejecutar como administrador» sobre la terminal o el acceso
> directo). Sin privilegios, la lectura de Event Logs queda deshabilitada y el
> sistema opera en modo degradado (solo Registro + SetupAPI).
>
> Comando recomendado desde la carpeta del proyecto:
> `..\.venv\Scripts\python.exe main.py`

---

## FASE A — Construir el comportamiento «normal» (varios días antes)

Objetivo: que el modelo aprenda una línea base de uso habitual. Cuantos más días
y más sesiones, más fiable será la detección posterior.

1. Abre la aplicación y ve a la pestaña **Ajustes**.
   - Genera un **secreto TOTP** y escanéalo con tu app autenticadora (Google
     Authenticator, Authy…). Lo necesitarás en la Fase B.
   - Define un **horario habitual** realista (por defecto 08:00–22:00, L-V).
     De momento NO actives el bloqueo (deja la casilla de enforce desmarcada).
2. En la barra superior, deja el modo en **aprendizaje** (no genera alertas).
3. Durante 1–2 semanas, usa tus USB habituales con normalidad: conéctalos en
   horario de día, varias veces. Cada día:
   - Pulsa **Analizar**, o
   - Pulsa **Iniciar monitor** y déjalo corriendo en segundo plano.
4. En la pestaña **Dispositivos**, marca como **Confiable** (casilla) los USB que
   reconozcas como tuyos. Estos no generarán alertas.

> Atajo si no dispones de días: puedes acelerar el aprendizaje conectando y
> desconectando tus USB habituales varias veces en horario laboral durante una
> misma jornada, dándole a Analizar entre cada conexión. No es lo ideal, pero
> genera suficientes sesiones para entrenar el modelo (mínimo 5 reales).

---

## FASE B — Provocar las anomalías (día de capturar evidencias)

Una vez existe la línea base, cambia el modo a **monitorizacion** y reproduce los
tres escenarios. Cada uno demuestra un componente distinto del motor.

### Escenario 1 — Anomalía temporal (hora poco habitual)
- En **Ajustes**, fija un horario habitual estrecho, por ejemplo 09:00–14:00,
  y guarda.
- Conecta un USB **conocido** fuera de esa franja (p. ej. a las 16:00).
- Pulsa **Analizar**. En la pestaña **Alertas** debe aparecer una alerta cuyo
  desglose muestre un valor alto en `hora` y bajo en `disp`.

### Escenario 2 — Dispositivo desconocido
- Consigue un USB que el sistema **nunca haya visto** (uno prestado).
- Conéctalo en horario normal y pulsa **Analizar**.
- La alerta debe mostrar un valor alto en `disp` (dispositivo poco visto).

### Escenario 3 — Anomalía combinada + bloqueo con TOTP
- En **Ajustes**, activa la casilla de **bloqueo fuera de horario** (enforce) y
  fija un horario que NO incluya la hora actual.
- Cambia el modo a **estricto**.
- Inicia el **monitor** y conecta un USB **desconocido**.
- Debe dispararse el **bloqueo** y aparecer el **diálogo de desbloqueo TOTP**.
  Introduce el código de tu app autenticadora para reactivarlo.

> Alternativa sin esperar a una hora concreta: para forzar que «ahora» sea fuera
> de horario, basta con configurar en Ajustes una franja muy estrecha que no
> contenga la hora actual (p. ej. si son las 16:00, pon 09:00–10:00).

---

## FASE C — Generar los artefactos para la memoria

1. En **Dispositivos**, pulsa **Exportar HTML** y **Exportar JSON**. Guarda
   ambos: irán como muestra en un anexo.
2. Ejecuta los scripts de validación y rendimiento y guarda su salida:
   - `..\.venv\Scripts\python.exe -m analytics.validation`
   - `..\.venv\Scripts\python.exe -m analytics.benchmark`
   - `..\.venv\Scripts\python.exe -m pytest tests\ -v`
3. Toma las capturas de pantalla listadas más abajo.

---

## LISTA DE CAPTURAS DE PANTALLA NECESARIAS

Marca cada una cuando la tengas. Indica en qué capítulo de la memoria va.

| # | Captura | Dónde colocarla |
|---|---|---|
| 1 | Ventana principal completa con la tabla de **Dispositivos** poblada (tipos y estados reales: almacenamiento, bluetooth, HID…) | Cap. 9 (Implementación) o anexo |
| 2 | Tabla con el filtro **«Solo conectados ahora»** activado | Cap. 9.5 |
| 3 | Vista **Experto** mostrando las columnas técnicas (serial, VID, PID, fuentes) | Cap. 9.5 |
| 4 | Pestaña **Alertas** con al menos una alerta y su **desglose por componentes** (hora/disp/maha) | Cap. 9.6 |
| 5 | Pestaña **Estadísticas** (dashboard) con las cuatro gráficas | Cap. 9.9 |
| 6 | Pestaña **Ajustes**: horario habitual + **código QR del TOTP** | Cap. 9.8 |
| 7 | **Diálogo de desbloqueo TOTP** al bloquear un dispositivo | Cap. 9.8 |
| 8 | Aviso de **privilegios** al arrancar sin administrador (opcional, ilustra la limitación) | Cap. 11.2 (limitaciones) |
| 9 | Fragmento del **informe HTML** exportado | Cap. 9 o anexo |
| 10 | Salida de consola de **validación** (tabla precisión/recall) | Cap. 10.3 |
| 11 | Salida de consola de **benchmark** (tiempos RNF1/RNF2) | Cap. 10 (rendimiento) |
| 12 | Salida de **pytest** con los 25 tests en verde | Cap. 10.1 |

> Recomendación: numera las figuras en la memoria de forma coherente
> (Figura 9.1, 9.2…) y añade un pie de figura con «(Fuente: elaboración propia)».
> Recuerda actualizar el «Índice de figuras» con todas ellas.

---

## CONSEJOS PARA LA DEFENSA

- Lleva el escenario ya preparado: no improvises conexiones de USB en directo si
  puedes evitarlo. Ten las capturas y, si haces demo en vivo, ensáyala antes.
- Ten a mano la respuesta a «¿esto funciona con datos reales?»: sí, sobre tu
  propio historial USB; las métricas de precisión/recall son sobre datos
  sintéticos como prueba de concepto del motor.
- Si te preguntan por el bloqueo físico: es real (Disable-PnpDevice) pero
  requiere administrador; sin él, el bloqueo es lógico y el TOTP igual se exige.
- Reconoce tú primero las limitaciones (datos sintéticos, evidencia indirecta,
  dependencia de Windows, privilegios). Da más solidez que ocultarlas.
