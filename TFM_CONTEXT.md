# TFM_CONTEXT.md

## Propósito de este archivo
Recoge el estado vivo del TFM: decisiones tomadas, contenidos aprobados, arquitectura, planificación y próximos pasos.  
Las reglas de comportamiento y estilo de Claude están en `CLAUDE.md`.

---

# 1. Datos generales

**Título:** Sistema inteligente de análisis forense y prevención de uso anómalo de dispositivos USB en Windows  
**Tipo:** Proyecto de análisis forense y desarrollo de software  
**Áreas:** Ciberseguridad defensiva · Informática forense · Detección de anomalías · Seguridad en sistemas Windows  
**Estado actual:** Fase documental y de definición estructural

---

# 2. Idea central del proyecto

Desarrollar una herramienta para Windows capaz de:
- analizar el uso histórico de dispositivos USB
- reconstruir evidencias forenses relacionadas con dichos dispositivos
- modelar patrones normales de uso del usuario
- detectar comportamientos anómalos
- generar alertas e informes
- aplicar, opcionalmente, medidas preventivas configurables

Enfoque: combina **análisis forense digital** y **prevención activa basada en detección de anomalías**.

---

# 3. Motivación del usuario

- Eligió este tema entre más de 15 propuestas.
- Encaja con su objetivo profesional: dedicarse a la **ciberseguridad defensiva**.
- Intereses concretos: monitorización, análisis forense, detección de anomalías, protección de sistemas.
- El proyecto demuestra competencias técnicas alineadas con ese perfil.

---

# 4. Alcance técnico

**SO objetivo:** Windows 11  
**Fuentes de datos:**
- Registro de Windows
- Event Logs
- SetupAPI logs
- otros metadatos relevantes del sistema o perfil de usuario

**Limitaciones fijas:**
- Solo Windows (no Linux ni macOS)
- "Archivos copiados" → siempre indicio forense, no prueba absoluta
- Sistema inteligente realista para 14–15 semanas de desarrollo
- Alcance controlado para garantizar núcleo funcional sólido

---

# 5. Índice oficial del TFM

- Portada
- Citas
- Agradecimientos
- Resumen
- Motivación, justificación y objetivo general
- 1. INTRODUCCIÓN
- 2. Estudio de viabilidad
  - 2.1. DAFO
  - 2.2. Lean Canvas
  - 2.3. Análisis de riesgos
- 3. Planificación
- 4. Estado del arte
- 5. Objetivos
- 6. METODOLOGÍA
  - 6.X Tecnologías
- 7. DISEÑO
- 8. IMPLEMENTACIÓN
- 9. EXPERIMENTACIÓN Y RESULTADOS
- 10. CONCLUSIONES
  - 10.1. Cumplimiento de Objetivos
  - 10.2. Limitaciones identificadas
  - 10.3. Trabajo futuro
- 11. BIBLIOGRAFÍA

---

# 6. Textos ya aprobados

## 6.1 Resumen aprobado

Este trabajo presenta el diseño y desarrollo de una herramienta para sistemas Windows orientada al análisis forense y la detección de usos anómalos de dispositivos USB. La propuesta parte de la necesidad de disponer de mecanismos que no solo permitan reconstruir de forma retrospectiva el historial de conexión de memorias y dispositivos extraíbles, sino también identificar comportamientos sospechosos a partir de los patrones habituales de uso del usuario. Para ello, el sistema recopila y correlaciona distintos artefactos del sistema operativo, como entradas del registro, eventos del sistema y otros metadatos relevantes, con el fin de generar una cronología de actividad y evidencias interpretables. Sobre esta base, se incorpora un módulo de análisis de comportamiento capaz de establecer un modelo de uso normal y detectar desviaciones significativas, tales como conexiones en horarios inusuales, utilización de dispositivos no habituales o patrones de uso atípicos. Como respuesta, la herramienta puede generar alertas, elaborar informes forenses y aplicar medidas preventivas configurables, como el bloqueo temporal del dispositivo. De este modo, el proyecto combina análisis forense digital y prevención activa en una solución unificada.

## 6.2 Motivación (ideas clave aprobadas)
- El usuario eligió este tema entre más de 15 propuestas.
- Le encaja profesionalmente: quiere dedicarse a la ciberseguridad defensiva.
- El proyecto combina análisis forense, monitorización, tratamiento de evidencias y detección de comportamientos anómalos.
- Sirve para demostrar competencias técnicas alineadas con su perfil profesional.

## 6.3 Introducción (orientación aprobada)
Debe:
- explicar el contexto del uso de dispositivos USB y su utilidad
- exponer los riesgos de seguridad asociados
- introducir la relevancia del análisis forense en Windows
- explicar que existen artefactos útiles para reconstrucción
- señalar que muchas herramientas están orientadas al análisis retrospectivo
- presentar la oportunidad de combinar reconstrucción forense y prevención activa
- no entrar todavía en detalles de implementación

---

# 7. Planificación del proyecto

| Fase | Duración | Resultado clave |
|------|----------|-----------------|
| Arranque | 2 días | Plan validado |
| Estado del arte | 1 semana | Marco teórico completo |
| Requisitos | 1 semana | Especificación clara |
| Diseño | 1 semana | Arquitectura definida |
| MVP Forense | 4 semanas | Sistema funcional |
| IA + Prevención | 4 semanas | Sistema inteligente completo |
| Pruebas | 1 semana | Validación cuantificada |
| Resultados + Ética | 1 semana | Análisis crítico |
| Memoria + Defensa | 2 semanas | Proyecto final listo |

**Distribución por semanas:**
- Semana 1 (2 días): arranque y definición
- Resto semana 1: estado del arte
- Semana 2: análisis y especificación
- Semana 3: diseño de la solución
- Semanas 4–7: MVP forense
- Semanas 8–11: sistema inteligente y prevención
- Semana 12: pruebas y validación
- Semana 13: resultados y consideraciones éticas
- Semanas 14–15: memoria final y defensa

**Enfoque:** Tradicional para fases documentales · Iterativo/incremental para implementación (MVP → ampliación → optimización)

**Hitos:**
- Hito 1: sistema forense funcional y estable
- Hito 2: sistema completo con detección de anomalías y prevención activa
- Hito final: proyecto listo para entrega y defensa

---

# 8. Criterios de éxito medibles

## Funcionales

**Extracción de evidencias USB**
- Identificación correcta de: ID del dispositivo, fecha/hora de conexión, nombre de volumen
- Precisión esperada: ≥ 95% en entorno controlado

**Reconstrucción de actividad**
- Informe estructurado con: dispositivo, cronología, eventos asociados
- Tiempo de generación: < 10 segundos para 100 eventos

**Persistencia**
- Almacenamiento en SQLite
- Integridad comprobable mediante hash o control de consistencia

## Detección de anomalías
- Periodo de entrenamiento configurable
- Modelo considera al menos: horario habitual, dispositivos frecuentes, frecuencia de uso
- Tasa de detección ≥ 80% en escenarios anómalos simulados
- Tasa de falsos positivos ≤ 20%
- Cada alerta incluye explicación del motivo

## Prevención
- Capacidad de: generar alerta, registrar evento, aplicar bloqueo temporal si activado
- Tiempo de reacción: < 3 segundos

## No funcionales
- Análisis de 1 año de eventos: < 30 segundos
- Interfaz con filtros por fecha y dispositivo
- Informe generado en 3 clics o menos
- Robustez ante registros incompletos o datos inconsistentes
- Log interno de errores
- Autenticación básica
- Almacenamiento estructurado y protegido

---

# 9. Arquitectura técnica aprobada

Arquitectura modular en 6 capas:

**1. Acquisition Layer**
- Extracción de artefactos: registro, event logs, setupapi logs, otros metadatos

**2. Normalization & Correlation Layer**
- Normalización de IDs, fechas y nombres
- Correlación de eventos en sesiones USB

**3. Evidence Store (SQLite)**
- Tablas: eventos, sesiones, dispositivos, alertas, configuración
- Hashes y auditoría básica (cadena de custodia)

**4. Analytics Engine**
- Entrenamiento del modelo
- Scoring de anomalías
- Explicación por componentes
- Versionado del modelo

**5. Policy & Response Engine**
- Acciones: alertar, pedir confirmación, bloquear temporalmente
- Modos: aprendizaje / monitorización / estricto

**6. UI + Reporting**
- Dashboard de histórico y anomalías
- Informes forenses en HTML / PDF / JSON

**Flujo principal:**  
Ingesta → Normalización → Correlación → Persistencia → Análisis → Política → Reporte/UI

---

# 10. Sistema inteligente: enfoque aprobado

**Objetivo:** Modelar el comportamiento habitual del usuario con dispositivos USB y detectar desviaciones significativas.

**Variables:**
- hora de conexión, día de la semana, frecuencia de uso
- dispositivos conocidos / desconocidos
- duración de sesión, tiempo desde la última conexión
- otros indicadores razonables

**Modelo propuesto (híbrido):**
- rareza temporal / densidad horaria
- distancia multivariable (Mahalanobis u equivalente)
- probabilidad asociada a frecuencia de dispositivos conocidos
- score final explicable por componentes

**Restricciones:** viable en TFM, explicable, sin promesas exageradas.

---

# 11. Estado del arte: directrices aprobadas

## Dos líneas obligatorias

**Línea 1 – Forense USB en Windows:**
artefactos del registro · SetupAPI · Event Logs · reconstrucción histórica · herramientas forenses de apoyo

**Línea 2 – Detección de anomalías / insider threat:**
auditoría · insider threats · modelado de comportamiento · detección de anomalías en seguridad

## Gap esperado
- Existe literatura sólida sobre reconstrucción forense USB en Windows.
- Existe literatura sobre insider threat y comportamiento anómalo.
- Pero hay poca integración entre ambas líneas.
- Faltan propuestas que combinen: reconstrucción forense USB + modelado de comportamiento normal + detección de anomalías + explicabilidad + prevención activa.

## Referencias aprobadas

**Académicas / serias:**
- Carvey y Altheide (2005) – artefactos Windows, valor forense del registro
- Alghafli, Jones y Martin (2010) – forense del registro Windows 7
- Arshad et al. (2018) – USB Storage Device Forensics para Windows 10
- Neyaz et al. (2019) – correlación Event Viewer, registro y sistema de archivos
- Collie (2013) – IconCache.db y artefactos secundarios de USB
- Collie (2016) – entornos de computación desde USB en hosts Windows
- Silowash y Lewellen, CERT/SEI (2013) – auditoría USB e insider threat
- Nellikar et al. (2010) – diferenciación por rol para detección de insiders
- Kim et al. (2019) – modelado de comportamiento y detección de anomalías

**A valorar solo si el modelo lo justifica:**
- Tabash et al. (2018) – GMM para insider threat
- Wei et al. (2021) – detección no supervisada

**Herramientas / ecosistema práctico (apoyo, no núcleo académico):**
USBDeview · USB Historian · USB Detective · KAPE · Magnet · ElcomSoft · Forensics Wiki

**Prohibido usar como referencias nucleares:** blogs genéricos, Reddit, foros, LinkedIn.

---

# 12. Estudio de viabilidad: decisiones tomadas

## DAFO
**Fortalezas:** problema real, alineación con ciberseguridad defensiva, combinación forense + anomalías, viabilidad técnica razonable  
**Debilidades:** dependencia de Windows, conclusiones como indicios, necesidad de datos, riesgo de scope creep  
**Oportunidades:** utilidad académica y profesional, base para ampliaciones, aplicación en DFIR e insider threat  
**Amenazas:** herramientas existentes, cambios futuros en Windows, falsos positivos, limitaciones de tiempo

## Lean Canvas
- **Problema:** falta de solución unificada que combine reconstrucción forense y detección de anomalías en USB
- **Usuarios:** investigadores forenses, administradores, responsables de seguridad, laboratorios
- **Propuesta de valor:** herramienta Windows que une análisis histórico, detección de anomalías y prevención
- **Ventaja diferencial:** integración de enfoques habitualmente separados

## Análisis de riesgos
Incluir: probabilidad, impacto, prevención, contingencia.  
Riesgos identificados:
- cambios en artefactos de Windows
- dificultad para demostrar copia de archivos
- falta de datos para entrenamiento
- falsos positivos
- sobrecarga del alcance
- problemas técnicos con el bloqueo temporal
- pérdida de código o documentación
- falta de tiempo
- errores en la correlación de evidencias

---

# 13. Decisiones cerradas

- Mantener DAFO, Lean Canvas y análisis de riesgos.
- Tratar la inferencia de copia de archivos siempre como indicio, nunca como prueba.
- Mantener alcance realista de 14–15 semanas.
- Separar claramente: análisis retrospectivo / detección de anomalías / prevención opcional.
- No basar estado del arte en blogs ni foros.
- Priorizar solución técnicamente defendible y realizable.

---

# 14. Estado actual de capítulos

| Capítulo | Estado |
|---|---|
| Resumen | Aprobado |
| Motivación | Ideas clave aprobadas |
| Introducción | Orientación aprobada, pendiente de redacción final |
| Estudio de viabilidad | Estructura decidida, pendiente de redacción |
| Planificación | Cerrada |
| Estado del arte | Borrador generado, en revisión |
| Objetivos | Pendiente |
| Metodología | Pendiente |
| Diseño | Pendiente |
| Implementación | Pendiente |
| Experimentación | Pendiente |
| Conclusiones | Pendiente |

---

# 15. Próximos pasos

- Revisar y cerrar el borrador del capítulo 4 (Estado del arte)
- Redactar capítulo 5 (Objetivos)
- Definir metodología
- Desarrollar diseño del sistema
- Preparar bibliografía en formato adecuado
- Revisar coherencia entre capítulos generados
