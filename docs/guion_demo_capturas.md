# Guion de demostración y capturas para la memoria

Orden exacto de pasos para recorrer toda la funcionalidad de la aplicación y
obtener capturas con contenido real. Cada paso indica QUÉ hacer, QUÉ verás y QUÉ
capturar (con el número de figura sugerido).

> **Preparación previa (importante):**
> 1. Ten a mano **2 pendrives USB**: uno que uses habitualmente («el tuyo») y
>    otro distinto que el sistema no haya visto («el desconocido»). Si solo
>    tienes uno, sirve, pero el escenario de «dispositivo desconocido» queda
>    menos claro.
> 2. Lanza la app **como administrador** para que lea Event Logs:
>    abre PowerShell como administrador, ve a la carpeta del proyecto y ejecuta
>    `..\.venv\Scripts\python.exe main.py`
> 3. Si quieres empezar desde cero, borra `tfm_usb.db` antes de arrancar.

---

## BLOQUE 1 — Vista general y detección de dispositivos

**Paso 1.1** — Conecta tu pendrive habitual. Abre la app. Pulsa **Analizar**.
- Verás la pestaña **Dispositivos** poblada: tu pendrive (tipo
  «almacenamiento», con capacidad y estado «Conectado»), más los dispositivos
  internos (bluetooth, cámara, HID).
- 📷 **CAPTURA 1** → ventana principal completa con la tabla poblada.
  *(Figura: «Vista principal de la aplicación con los dispositivos detectados».)*

**Paso 1.2** — En la barra de filtros, marca **«Solo conectados ahora»**.
- La tabla se reduce a los dispositivos presentes en este momento.
- 📷 **CAPTURA 2** → tabla filtrada por conectados.
  *(Figura: «Filtrado de dispositivos conectados en el momento del análisis».)*

**Paso 1.3** — En la cabecera, cambia el selector de vista a **Experto**.
- Aparecen las columnas técnicas: Nº de serie, Vendor ID, Product ID, Fuentes.
- 📷 **CAPTURA 3** → tabla en modo experto con las columnas técnicas.
  *(Figura: «Vista experta con identificadores y fuentes de cada dispositivo».)*

---

## BLOQUE 2 — Configuración (Ajustes)

**Paso 2.1** — Ve a la pestaña **Ajustes**. En la sección de segundo factor,
pulsa **«Generar nuevo secreto TOTP»**. Aparecerá el código QR.
- Escanéalo con tu app autenticadora (Google Authenticator / Authy). Lo usarás
  en el Bloque 4.
- 📷 **CAPTURA 4** → pestaña Ajustes con el QR del TOTP visible.
  *(Figura: «Configuración del segundo factor de autenticación (TOTP)».)*

**Paso 2.2** — En la sección de horario habitual, deja una franja realista
(p. ej. 08:00–22:00, L-V) y, de momento, NO marques el bloqueo. Guarda.
- *(Opcional)* 📷 captura del panel de horario si quieres ilustrar 9.8.

---

## BLOQUE 3 — Aprendizaje y detección de anomalías

**Paso 3.1** — Cambia el modo a **aprendizaje**. Conecta y desconecta tu
pendrive habitual varias veces en horario de día, dando a **Analizar** entre
medias, para que el modelo acumule sesiones «normales». Marca tu pendrive como
**Confiable** (casilla en la tabla).

**Paso 3.2** — Cambia el modo a **monitorizacion**. Ahora provoca una anomalía:
- **Anomalía de hora**: en Ajustes pon una franja estrecha que NO incluya la
  hora actual (si son las 16:00, pon 09:00–10:00) y guarda. Conecta tu pendrive
  habitual y pulsa **Analizar**.
- **Anomalía de dispositivo**: conecta el pendrive **desconocido** y pulsa
  **Analizar**.

**Paso 3.3** — Ve a la pestaña **Alertas**.
- Verás las alertas generadas, con su severidad (color), score y, sobre todo, el
  **desglose por componentes** (hora / dispositivo / multivariable).
- 📷 **CAPTURA 5** → pestaña Alertas con al menos una alerta y su desglose.
  *(Figura: «Alertas generadas con desglose explicable por componentes».)*
  Esta es la captura MÁS importante: demuestra la explicabilidad del motor.

---

## BLOQUE 4 — Prevención y bloqueo con TOTP (modo estricto)

**Paso 4.1** — En Ajustes, marca la casilla de **bloqueo fuera de horario** y
mantén una franja que no incluya la hora actual. Cambia el modo a **estricto**.
Pulsa **Iniciar monitor**.

**Paso 4.2** — Conecta el pendrive desconocido (o tu pendrive si solo tienes uno).
- Al detectarse fuera de horario, salta el **diálogo de desbloqueo** que pide el
  código TOTP.
- 📷 **CAPTURA 6** → diálogo de desbloqueo TOTP.
  *(Figura: «Bloqueo de dispositivo fuera de horario y solicitud de segundo
  factor».)*

**Paso 4.3** — Introduce el código de tu app autenticadora.
- *(Si la app no se ejecuta como administrador, el bloqueo es solo lógico, pero
  el diálogo aparece igual — sirve para la captura.)*

---

## BLOQUE 5 — Estadísticas (dashboard)

**Paso 5.1** — Ve a la pestaña **Estadísticas**. Si has dejado el monitor
corriendo un rato, habrá señales acumuladas.
- Verás las cuatro gráficas: actividad por hora, suspensiones por día, apps más
  usadas y tipos de dispositivo.
- 📷 **CAPTURA 7** → pestaña Estadísticas con las gráficas.
  *(Figura: «Panel de estadísticas de uso del sistema».)*

---

## BLOQUE 6 — Informes exportados

**Paso 6.1** — En la pestaña Dispositivos, pulsa **Exportar HTML**. Se abre el
informe en el visor.
- 📷 **CAPTURA 8** → fragmento del informe HTML generado.
  *(Figura: «Informe forense exportado en formato HTML».)*

**Paso 6.2** — Pulsa **Exportar JSON** y guarda el fichero. Mete una muestra
recortada en un anexo (no hace falta captura, basta el fichero).

---

## BLOQUE 7 — Evidencia de validación y pruebas (consola)

Estas no son de la app, sino de los scripts. Van muy bien en el capítulo 10.

**Paso 7.1** — Ejecuta y captura la salida de:
```
..\.venv\Scripts\python.exe -m analytics.validation
```
- 📷 **CAPTURA 9** → tabla de precisión/recall por umbral en consola.
  *(Complementa a la Figura 10.1 que ya tienes generada.)*

**Paso 7.2** — Ejecuta y captura:
```
..\.venv\Scripts\python.exe -m pytest tests\ -v
```
- 📷 **CAPTURA 10** → los 25 tests en verde.
  *(Figura: «Ejecución de la batería de pruebas automatizadas».)*

---

## RESUMEN: capturas mínimas imprescindibles

Si vas justo de tiempo, estas seis son las que NO pueden faltar:

| # | Captura | Por qué es clave |
|---|---|---|
| 1 | Tabla de dispositivos poblada | Demuestra que la herramienta funciona y detecta tipos reales |
| 5 | Alerta con desglose por componentes | Demuestra la detección **explicable** (el núcleo del TFM) |
| 6 | Diálogo de desbloqueo TOTP | Demuestra la prevención + segundo factor |
| 7 | Dashboard de estadísticas | Demuestra el análisis de comportamiento del equipo |
| 8 | Informe HTML | Demuestra el resultado forense exportable |
| 10 | pytest en verde | Demuestra rigor y validación (cap. 10) |

> Consejo: numera las figuras de forma coherente (Figura 9.1, 9.2…) según el
> capítulo donde las pongas, y añade siempre el pie «(Fuente: elaboración
> propia)». Actualiza el «Índice de figuras» con todas ellas al final.
