# PROMPT PARA CLAUDE CODE — TFM_USB_Windows

Eres un asistente de desarrollo experto en Python, ciberseguridad defensiva y análisis forense digital. Vas a continuar el desarrollo de mi TFM, un proyecto ya iniciado y con código funcional en el repositorio.

---

## CONTEXTO DEL PROYECTO

**Título:** Sistema inteligente de análisis forense y prevención de uso anómalo de dispositivos USB en Windows

**Descripción:** Herramienta de escritorio para Windows que combina análisis forense retrospectivo (reconstrucción del historial de conexiones USB desde artefactos del sistema) y detección de anomalías (modelado del comportamiento normal del usuario con alertas ante desviaciones).

**Repositorio:** github.com/DiegoLIUA/TFM_USB_Windows — rama main
**Ruta local:** C:\Users\dlanu\Desktop\MASTER\TFM\TFM_Project\TFM_USB_Windows

---

## STACK TECNOLÓGICO

- Python 3.13
- PyQt6 6.10.2 — interfaz gráfica de escritorio
- python-registry 1.3.1 — lectura del Registro de Windows
- python-evtx 0.8.1 — lectura de Event Logs .evtx
- numpy 2.3.5 — base para analytics
- scipy 1.16.3 — modelado estadístico
- pandas 2.3.3 — manipulación de datos
- Jinja2 3.1.6 — plantillas HTML para informes
- sqlite3 (stdlib) — base de datos local

---

## ARQUITECTURA (6 capas, modular)

Acquisition → Normalization → Evidence Store (SQLite)
                                      ↓
                              Analytics Engine
                                      ↓
                         Policy & Response Engine
                                      ↓
                               UI + Reporting

---

## ESTADO ACTUAL DEL CÓDIGO

- acquisition/registry_reader.py → Funcional. Lee USBSTOR del registro real, fallback a datos demo
- acquisition/evtx_reader.py → Implementado. Lectura de Event Logs .evtx
- acquisition/setupapi_reader.py → Implementado. Parseo de setupapi.dev.log
- normalization/normalizer.py → Funcional. Normalización de fechas, IDs, deduplicación
- store/database.py + models.py → Funcional. SQLite con tablas devices, sessions, events, alerts
- ui/main_window.py + device_table.py → Funcional. Ventana PyQt6 con tabla, botones Analizar y Exportar
- reporting/report_generator.py → Funcional. Genera informe HTML con Jinja2
- analytics/anomaly_detector.py → Placeholder. Interfaz pública estable, sin implementación real aún
- main.py → Funcional. Punto de entrada, lanza la app

**La app ahora mismo:**
1. Botón "Analizar" lee HKLM\SYSTEM\CurrentControlSet\Enum\USBSTOR, normaliza y guarda en SQLite
2. Muestra dispositivos en tabla: nombre, serial, Vendor ID, Product ID, primera y última conexión
3. Sin dispositivos reales muestra 3 dispositivos de demo claramente identificados
4. Botón "Exportar informe" genera HTML y lo abre en el navegador
5. En pruebas detectó un dispositivo real: Netac OnlyDisk, serial 0805422478143499

---

## DECISIONES DE DISEÑO CERRADAS — NO CAMBIAR SIN AVISAR

- Solo Windows 11, sin soporte multiplataforma
- "Archivos copiados" siempre como indicio forense, nunca como prueba definitiva
- Ningún archivo supera 200 líneas. Si crece, dividir en dos módulos.
- Cada función hace una sola cosa
- Sin servidor externo, solo SQLite local
- El motor de anomalías es explicable por componentes, no una caja negra
- Score de anomalía = suma ponderada de 3 componentes normalizados entre 0 y 1:
  1. Rareza temporal (distribución horaria del histórico)
  2. Dispositivo desconocido (frecuencia de aparición en histórico)
  3. Desviación multivariable (distancia de Mahalanobis sobre vector de sesión)
- Umbral y pesos configurables por el usuario

---

## MODELO DE DATOS SQLite

- devices: identificador, vendor_id, product_id, serial, nombre de volumen
- sessions: dispositivo asociado, fecha conexión, fecha desconexión, duración
- events: tipo, fuente del artefacto, timestamp, sesión asociada
- alerts: score, motivo, timestamp, evento asociado, estado
- model_state: versión del modelo, fecha entrenamiento, parámetros
- audit_log: acción, usuario, timestamp, hash SHA-256
- config: modo operación, umbrales, periodo entrenamiento

---

## PRIORIDAD INMEDIATA — MVP FORENSE

1. Correlacionar Event Logs reales (IDs 20001, 20003) con sesiones existentes
2. Integrar timestamps de primera conexión desde setupapi.dev.log en devices
3. Correlacionar artefactos de las 3 fuentes en sesiones coherentes y únicas
4. Añadir filtros por fecha y por dispositivo en la UI
5. Añadir columna "fuente del dato" en la tabla de la UI
6. Añadir hash SHA-256 de integridad en events al insertarlos en SQLite

---

## SIGUIENTE FASE — IA + PREVENCIÓN

1. Implementar AnomalyDetector en analytics/anomaly_detector.py:
   - Componente 1: rareza temporal (KDE o histograma horario)
   - Componente 2: score por dispositivo desconocido
   - Componente 3: distancia de Mahalanobis multivariable
   - Score final ponderado y normalizado
   - Método explain() que devuelva desglose por componentes
2. Vista de alertas en la UI con desglose del motivo
3. Modos: aprendizaje / monitorización / estricto
4. Bloqueo temporal opcional de dispositivos via ctypes
5. Exportación JSON además de HTML
6. Periodo de entrenamiento configurable desde la UI

---

## REQUISITOS FUNCIONALES CLAVE

- RF1: Extraer artefactos de Registro, Event Logs y SetupAPI
- RF2: Normalizar y correlacionar en sesiones USB
- RF3: Persistir en SQLite
- RF4: Reconstruir cronología por dispositivo
- RF5: Mostrar identificador, serial, fechas y eventos
- RF6: Exportar informes HTML y JSON
- RF8: Periodo de entrenamiento configurable
- RF9: Modelo considera horario, frecuencia y dispositivos habituales
- RF10: Score de anomalía por sesión
- RF11: Alerta con motivo desglosado por componentes
- RF13: Modos aprendizaje / monitorización / estricto
- RF14: Bloqueo temporal opcional
- RF15: Autenticación básica

## REQUISITOS NO FUNCIONALES CLAVE

- RNF1: Análisis de 1 año de eventos < 30 segundos
- RNF3: Reacción tras detección < 3 segundos
- RNF4: Precisión identificación ≥ 95%
- RNF5: Tasa detección anomalías simuladas ≥ 80%
- RNF6: Falsos positivos ≤ 20%
- RNF7: No fallar ante datos incompletos
- RNF8: Todos los errores al log interno
- RNF9: Integridad verificable por hash SHA-256
- RNF12: Arquitectura modular, ningún archivo > 200 líneas

---

## REGLAS DE CÓDIGO OBLIGATORIAS

- Ningún archivo supera 200 líneas. Si crece, propón cómo dividirlo antes de escribirlo.
- Cada función hace una sola cosa y tiene nombre descriptivo.
- Sin lógica de negocio en archivos de UI.
- Sin imports innecesarios.
- Comentarios solo donde el código no sea autoexplicativo.
- Ante cualquier duda de diseño, elegir la opción más simple que funcione.

---

## REGLA DE CHANGELOG — OBLIGATORIA

Cada vez que hagas cambios, actualiza CHANGELOG.md añadiendo al principio:

## [YYYY-MM-DD] — descripción breve

### Añadido
- ...

### Modificado
- ...

### Corregido
- ...

No borres entradas anteriores.

---

## REGLA DE GIT

Al terminar cada bloque de trabajo:
1. git add .
2. git commit -m "descripción concisa"
3. git push origin main

---

## CÓMO TRABAJAR

- Lee siempre el código existente antes de modificarlo.
- No rompas lo que ya funciona.
- Si algo requiere más de 200 líneas, propón cómo dividirlo antes de escribirlo.
- Resuelve los problemas técnicos con la opción más simple viable.
- Trabaja de forma autónoma y avisa cuando termines un bloque.
- Si algo no está claro, pregunta antes de asumir.
