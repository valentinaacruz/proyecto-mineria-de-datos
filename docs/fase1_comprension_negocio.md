# Fase 1 de CRISP-DM: comprensión del negocio

**Proyecto:** Trayectorias de participación electoral en México: segmentación de secciones electorales 2009–2024
**Equipo:** Cruz Mendoza Valentina Ayelen · Nava Villavicencio Abraham · Negrete Mancera Leonardo · Pérez Bustamante José Julian
**Versión:** borrador 3 (19 de noviembre de 2026). Las secciones marcadas con ⚑ requieren decisión del equipo.

| Versión | Cambios |
|---|---|
| 1 | Primer borrador |
| 2 | Se fijan los umbrales T1–T7 (v1) y la regla para ajustarlos; se adopta el ECEG 2020 como fuente de contexto; la elección entre el Índice de Rezago Social y la medición de pobreza pasa a la fase 2 |
| 3 (19-nov-2026) | **T3:** la referencia de las 32 entidades se sustituye por los estados agrupados en el mismo número de grupos (k regiones). Razón del método, no de un resultado: comparar 4–7 grupos con 32 mezcla la calidad de la tipología con el número de grupos. Las 32 entidades explican el 22% y el 29% de la participación relativa de 2021 y 2024; agrupadas en 4 a 7 regiones, entre 7% y 15%. Se decidió antes de correr los modelos del equipo; el problema se notó en la prueba técnica de la plantilla, pero las cifras que lo justifican no dependen de ningún modelo. Detalle en la fase 3, §7 |

Este documento sigue las cuatro tareas de la fase 1 de CRISP-DM 1.0 (Chapman et al., 2000): determinar los objetivos del negocio (§1), evaluar la situación (§2), determinar los objetivos de minería de datos (§3) y producir el plan del proyecto (§4).

---

## 1. Objetivos del negocio

### 1.1 Antecedentes

El Instituto Nacional Electoral (INE), a través de la Dirección Ejecutiva de Capacitación Electoral y Educación Cívica (DECEyEC), diseña las acciones de educación cívica y promoción de la participación. Desde 2009 la DECEyEC publica los **Conteos Censales de Participación Ciudadana (CCPC)**. Se construyen con las marcas de «votó» en los cuadernillos de la lista nominal y dicen, para cada sección electoral, sexo y edad, cuántas personas de la lista nominal votaron, cuántas no y cuántas no se capturaron.

La participación nacional, calculada con los CCPC, sigue un ciclo marcado por el tipo de elección:

| Elección | Tipo | Lista nominal (M) | Participación* | Participación cruda** | Sin captura (NS) | Secciones |
|---|---|---|---|---|---|---|
| 2009 | Intermedia | 77.5 | 44.1% | 43.0% | 2.4% | 64,934 |
| 2012 | Presidencial | 76.5 | 62.1% | 61.9% | 0.2% | 65,599 |
| 2015 | Intermedia | 83.6 | 47.1% | 44.2% | 6.1% | 68,362 |
| 2018 | Presidencial | 89.1 | 62.4% | 58.1% | 6.8% | 68,408 |
| 2021 | Intermedia | 93.5 | 51.8% | 49.6% | 4.3% | 68,812 |
| 2024 | Presidencial | 98.3 | 59.7% | 55.8% | 6.4% | 70,751 |

\* Votantes / (votantes + no votantes): excluye los registros sin captura. \*\* Votantes / lista nominal. Cifras calculadas con el panel procesado de los CCPC; en la fase 2 se validarán contra las cifras publicadas por el INE.

El problema que motiva el proyecto es que los análisis habituales resumen la participación con un promedio por estado o municipio y en una sola elección. Dos secciones con el mismo promedio pueden tener historias distintas: una estable y otra que se desploma en cada intermedia, o una que mejora y otra que se deteriora. Para la planeación de la educación cívica importa saber **qué tipo de comportamiento** hay en cada lugar, no solo **dónde** se vota poco.

**Trabajo previo del equipo.** En el Hackathon INE 2026 se trabajó con los mismos datos (Reto 1, perfiles ciudadanos; Reto 2, predicción, exploratorio). Los hallazgos siguientes condicionan este proyecto y se toman como punto de partida, no como resultados de este trabajo:

- La participación tiene una fuerte estructura geográfica: la autocorrelación espacial (I de Moran, 8 vecinos) es de 0.68 a 0.76 en las seis elecciones. En 2021 el estado explica 22% de la varianza entre secciones y el municipio, 65%.
- La escolaridad casi no se relaciona con la abstención (Spearman 0.03). Las secciones rurales votan más que las urbanas (abstención 2021: 40.7% frente a 47.5%).
- Tres rasgos de la sección son **persistentes**: el nivel de participación relativo al nacional, la brecha de género y la brecha de jóvenes. Su correlación entre ventanas sin elecciones en común (2009–2015 frente a 2018–2024) es de 0.5 a 0.7.
- La **intermitencia** (votar en presidenciales y no en intermedias) **no es persistente** por territorio: correlación de 0.28 en secciones y de 0.07 en municipios entre ventanas. Es un fenómeno nacional.
- Los datos forman un **continuo**: al agrupar los tres rasgos con K-means (k = 5), la silueta fue de 0.232, frente a 0.221 en datos simulados sin grupos con la misma covarianza. Las fronteras entre grupos dependían del algoritmo (ARI de K-means frente a Ward: 0.34).

La diferencia con el Reto 1 es el objeto de agrupamiento. Aquí se agrupan **trayectorias de seis elecciones** y sus variables de forma. En el Reto 1 se agruparon tres rasgos promedio, y la trayectoria solo se usó para describir. Ni los perfiles del Reto 1 ni sus estrategias se reutilizan; sí se reutilizan el código de procesamiento y las pruebas de robustez (§4.3).

### 1.2 Objetivos del negocio

**Objetivo principal.** Dar a quienes planean la educación cívica una **tipología de trayectorias de participación** por sección que permita diseñar estrategias diferenciadas según el tipo de comportamiento, y no solo según el nivel.

Preguntas de negocio que la tipología debe responder:

1. ¿Qué tipos de trayectoria de participación existen entre 2009 y 2024, y cuánta lista nominal representa cada uno?
2. ¿Dónde se concentran (estado y municipio)?
3. ¿Qué características demográficas y territoriales distinguen a cada tipo?
4. ¿Qué estrategia de promoción del voto sugiere cada tipo? Por ejemplo, para la elección intermedia de 2027.

**Partes interesadas**

| Parte | Rol | Qué necesita del proyecto |
|---|---|---|
| DECEyEC (INE) | Usuario principal | Tipos con nombre claro, peso en la lista nominal y estrategia sugerida |
| Juntas Locales y Distritales del INE | Usuario operativo | Perfil de cada sección y composición por municipio |
| Profesor del curso | Evaluador | Aplicación documentada de CRISP-DM, rigor y reproducibilidad |
| Equipo | Ejecutor | Plan claro, criterios fijados de antemano |

El INE no es cliente real del proyecto: es el usuario hipotético que orienta las decisiones.

### 1.3 Criterios de éxito del negocio

| # | Criterio | Cómo se verifica |
|---|---|---|
| N1 | Entre 4 y 7 perfiles, cada uno con nombre descriptivo, descripción de no más de tres líneas y peso en la lista nominal | Ficha por perfil |
| N2 | Los perfiles se distinguen en algo accionable: cada uno sugiere una estrategia distinta | Tabla perfil → objetivo, mensaje y canal; si dos perfiles llevan la misma estrategia, se fusionan |
| N3 | Nombres comprensibles para alguien que no participó en el análisis | **Prueba de nombre ciego:** una persona ajena recibe las curvas de cada grupo sin nombre y debe asociarlas con los nombres propuestos; éxito si acierta al menos 80% |
| N4 | Resultados utilizables a nivel municipal | Base sección → perfil y mapa municipal de composición |
| N5 | Interpretación responsable | Ningún perfil se describe en términos de personas ni se presenta como irregularidad electoral |
| N6 | Reproducible | El repositorio regenera todas las cifras desde los datos públicos |

---

## 2. Evaluación de la situación

### 2.1 Inventario de recursos

**Personas:** cuatro integrantes. Del Hackathon INE 2026 se cuenta con experiencia previa con los CCPC y con un pipeline de procesamiento probado.

**Datos**

| Fuente | Granularidad | Años | Estado al 17-nov-2026 | Uso |
|---|---|---|---|---|
| INE, CCPC | Sección × sexo × edad simple: lista nominal, votantes, no votantes, sin captura | 2009–2024 (6 elecciones) | **Procesados disponibles:** panel sección × elección (406,866 filas) y tabla sección × elección × sexo × 7 grupos de edad (5.7 M filas). Los zips originales ya no están en disco; el script de descarga existe | Trayectorias, perfiles por edad y sexo |
| INE-INEGI, Estadísticas Censales a Escalas Geoelectorales (ECEG) 2020 | **Sección** (227 indicadores del censo 2020) | 2020 | Procesado disponible (68,806 secciones) | **Fuente principal de contexto** (se agrega a la propuesta; decisión del equipo, v2) |
| CONEVAL, medición de pobreza municipal | Municipio | 2010, 2015, 2020 | Procesado disponible (2,486 municipios; pobreza y carencias sociales) | Contexto municipal: candidata (se decide en la fase 2) |
| CONEVAL, Índice de Rezago Social | Municipio | 2010, 2015, 2020 | **No descargado** (la propuesta lo cita) | Contexto municipal: candidata (se decide en la fase 2) |
| INEGI, Censo 2020 (ITER) | Localidad o municipio | 2020 | No descargado | Sustituido por el ECEG, que trae las mismas variables del censo a nivel de sección; el ITER solo se usaría para verificar |
| INE, marco seccional (cartografía) | Polígonos de sección, con entidad, distrito y municipio | Corte 2021 | Disponible (68,806 secciones) | Mapas; los polígonos municipales se obtienen agregando secciones |

**Software** (instalación verificada el 17-nov-2026 con Python 3.14.7 y uv 0.12.6): pandas 3.1.1, NumPy 2.5.5, scikit-learn 1.9.1, tslearn 0.10.0 (se probó K-means con DTW y banda Sakoe-Chiba), geopandas 1.2.0, matplotlib 3.11.2 y SciPy 1.18.1.

**Equipo de cómputo:** laptops personales. El volumen procesado es moderado (panel de 8 MB y tabla por edad y sexo de 26 MB en Parquet). Los ~3.5 GB de datos crudos solo se procesan una vez.

### 2.2 Requisitos, supuestos y restricciones

**Requisitos**
- Aplicar y documentar CRISP-DM fase por fase.
- Comparar al menos tres algoritmos de agrupamiento y entrenar un árbol de decisión explicativo (compromiso de la propuesta).
- Código reproducible en un repositorio.

**Supuestos**
- La marca de «votó» del cuadernillo refleja la votación en casilla de la propia sección. No incluye casillas especiales ni voto desde el extranjero.
- Los registros sin captura (NS) no dependen del comportamiento de voto. **Se verificará en la fase 2**, porque varían de 0.2% (2012) a 6.8% (2018).
- La lista nominal incluye a personas que ya no residen en la sección o que fallecieron, lo que infla la abstención donde hay emigración. Es un sesgo conocido, no corregible con estos datos.

**Restricciones**
- Solo datos públicos y agregados; no se usan datos personales.
- El censo y la cartografía están en el marco seccional de 2021. Las secciones creadas después (los conteos de 2024 tienen 70,751 secciones, frente a 68,806 del marco) no tienen polígono ni datos del censo.
- El contexto es **ecológico**: describe a la sección, no a quienes votan o no votan en ella.

### 2.3 Riesgos y contingencias

| # | Riesgo | Probabilidad | Señal | Contingencia |
|---|---|---|---|---|
| R1 | Los datos son un continuo y la silueta no supera 0.25 | **Alta** (0.232 en el trabajo previo) | Silueta cercana a la de un nulo sin grupos | Criterios relativos a un nulo (§3.3); reportar los grupos como partición de un continuo y apoyarse en los ejes de variación |
| R2 | Los grupos solo reflejan el nivel medio (alto, medio, bajo) y no la forma de la trayectoria | Media | La mayor parte de la varianza entre grupos está en el nivel | Agrupar también con la trayectoria centrada (sin nivel) y comparar |
| R3 | El ciclo nacional domina la trayectoria | Alta si no se corrige | Grupos que replican el patrón intermedia/presidencial | Expresar la participación relativa al promedio nacional de cada elección (propuesta, fase 3) |
| R4 | El perfil «solo presidenciales» no existe como rasgo territorial | **Alta** (r = 0.28 en el trabajo previo) | Baja correlación del vaivén entre periodos | Hipótesis H2 con prueba explícita (§3.2); si no se sostiene, se reporta como hallazgo |
| R5 | Las secciones pequeñas generan trayectorias ruidosas | Alta | Volatilidad que decrece con el tamaño | Lista nominal mínima o encogimiento hacia la media; revisar que el grupo no dependa del tamaño |
| R6 | Cambios cartográficos (secciones creadas, divididas o eliminadas) | Cierta: 62,048 secciones en las seis elecciones de 72,681 | — | Trabajar con historia suficiente y documentar en la fase 2 cuánta lista nominal queda fuera |
| R7 | NS variable entre elecciones | Cierta | Diferencia entre participación ajustada y cruda de hasta 4.3 pp (2018) | Usar la tasa ajustada; análisis de sensibilidad con la cruda |
| R8 | DTW con seis puntos fijos: puede alinear una intermedia con una presidencial | Media | Grupos de DTW con centroides desfasados | Banda Sakoe-Chiba de radio 0 o 1; comparar contra la distancia euclidiana |
| R9 | Los enlaces de descarga del INE cambian | Media | Error 404 en `download_data.py` | Los datos procesados ya existen; buscar la ruta nueva con el navegador |
| R10 | Lectura indebida (falacia ecológica o sospecha de irregularidades) | Media | — | Reglas de redacción del criterio N5 en todos los entregables |
| R11 | Reutilización de trabajo previo no autorizada en el curso | Baja | — | ⚑ Confirmar con el profesor y citar el hackathon como antecedente |

### 2.4 Terminología

| Término | Definición |
|---|---|
| Sección electoral | Unidad territorial mínima de la geografía electoral; contiene entre 100 y 3,000 electores aprox. |
| LN | Lista nominal: personas con credencial vigente inscritas en la sección |
| SV / NV / NS | Votaron / no votaron / sin captura en el cuadernillo |
| Participación (ajustada) | SV / (SV + NV) |
| Participación relativa | Participación de la sección menos la nacional de la misma elección (pp) |
| Intermedia / presidencial | Elecciones federales de 2009, 2015 y 2021 / de 2012, 2018 y 2024 |
| Trayectoria | Serie de seis valores de participación relativa de una sección |
| Variables de forma | Resúmenes de la trayectoria: nivel, sensibilidad intermedia/presidencial, tendencia, volatilidad |
| Tipo de sección | Urbana, rural o mixta, según el INE |
| Perfil o tipo | Grupo de secciones con trayectorias similares, resultado del agrupamiento |

### 2.5 Costos y beneficios

Los datos son públicos y gratuitos, y el software es libre; el costo es el tiempo del equipo. El beneficio esperado es una herramienta de focalización que no requiere datos personales y que puede actualizarse con cada nueva publicación de los CCPC (la próxima, tras la intermedia de 2027).

---

## 3. Objetivos de minería de datos

### 3.1 Objetivos

| Objetivo de negocio | Objetivo de minería de datos | Tipo de tarea |
|---|---|---|
| Preguntas 1 y 2 | **M1.** Construir una tabla analítica por sección con la trayectoria relativa de 2009 a 2024, variables de forma, participación por edad y sexo y contexto (ECEG por sección y una fuente municipal del CONEVAL) | Preparación |
| Pregunta 1 | **M2.** Agrupar las secciones con tres algoritmos: (a) K-means sobre variables de forma; (b) jerárquico aglomerativo con enlace de Ward; (c) K-means con DTW sobre la trayectoria. k entre 4 y 7 | Descripción (no supervisado) |
| Pregunta 3 | **M3.** Árbol CART que prediga el grupo con variables de contexto, con profundidad limitada para extraer reglas legibles | Clasificación (explicativa) |
| Preguntas 2 y 4 | **M4.** Describir cada grupo (curva media, edad, sexo, región, contexto) y mapear su composición municipal | Descripción |

### 3.2 Hipótesis de trabajo

Las hipótesis de la propuesta se fijan aquí con una prueba explícita. Así se puede confirmar o descartar cada una, en lugar de solo «encontrarla».

| # | Perfil hipotético | Definición operativa | Prueba | Expectativa previa |
|---|---|---|---|---|
| H1 | Constantes | Participación relativa alta en los dos tipos de elección y baja volatilidad | Existe un grupo estable (§3.3, T2) con nivel en el cuartil superior y volatilidad en la mitad inferior | Probable |
| H2 | Solo presidenciales | Vaivén presidencial − intermedia mayor que el nacional, **y persistente** | Correlación por sección del vaivén 2009→2012 con el de 2021→2024 ≥ 0.5 (umbral de los rasgos que sí persistieron) | **Improbable** (r = 0.28 en el trabajo previo) |
| H3 | Jóvenes ausentes | Brecha de 18–34 frente a 55–74 años mayor que la nacional, persistente | Correlación de la brecha entre 2009–2015 y 2018–2024 ≥ 0.5 | Probable (0.5–0.7 en el trabajo previo) |
| H4 | Abstención crónica | Participación relativa baja en las seis elecciones | Existe un grupo estable con nivel en el cuartil inferior y sin tendencia | Probable |
| H5 | En deterioro | Caída de la participación relativa entre 2009–2015 y 2018–2024 mayor que la esperada por **regresión a la media** | Residuo negativo de la regresión del nivel 2018–2024 sobre el de 2009–2015, concentrado en un grupo | Incierta |

### 3.3 Criterios de éxito técnicos (versión 1, fijada el 17-nov-2026)

La propuesta fijó como criterio una silueta mayor que 0.25. El trabajo previo muestra que ese umbral puede fallar aunque el resultado sea útil (silueta de 0.232). Además, superarlo no prueba que haya grupos: datos simulados sin grupos dieron 0.221. Por eso se fijan criterios relativos **antes** de ver los resultados. La silueta absoluta se reporta igual, como pide la propuesta.

| # | Criterio | Métrica | Umbral (v1) | Por qué |
|---|---|---|---|---|
| T1 | Estructura más allá de un continuo | Silueta y Davies-Bouldin frente a un nulo: 20 réplicas normales multivariantes con la misma covarianza | Silueta real > percentil 95 del nulo | Separa «hay grupos» de «hay un continuo cortado» |
| T2 | Estabilidad | ARI medio entre réplicas bootstrap, remuestreando **municipios** (no secciones) | ≥ 0.60 | Remuestrear municipios respeta la dependencia espacial; el trabajo previo obtuvo 0.83 |
| T3 | Validez temporal | Grupos formados con 2009–2018 → R² de la participación relativa de 2021 y 2024 | Mayor que el de grupos al azar del mismo tamaño y que el de los 32 estados agrupados en k regiones por su nivel 2009–2018 (**v3**; en v1: que el de las 32 entidades) | Prueba que el grupo captura algo que persiste y que dice más que la geografía con el mismo número de grupos |
| T4 | Tamaño útil | Proporción de la lista nominal por grupo | Cada grupo ≥ 5% | Un grupo diminuto no justifica una estrategia |
| T5 | No es un artefacto del tamaño | η² del log de la lista nominal entre grupos | < 0.10 | Riesgo señalado en la propuesta |
| T6 | Árbol explicativo | Exactitud balanceada en validación cruzada **agrupada por entidad**; profundidad ≤ 4 | ≥ clase mayoritaria + 10 pp | La validación por entidad evita que el árbol memorice la geografía |
| T7 | Concordancia entre algoritmos | ARI entre las soluciones de los tres algoritmos | Se reporta; si < 0.3, las conclusiones se apoyan en las variables de forma, no en los cortes | Mide qué tanto dependen las fronteras del algoritmo |

**Regla de elección de k (fijada de antemano):** entre los k de 4 a 7 que cumplan T2 y T4, se elige el de mejor T3. El codo, la silueta y Davies-Bouldin se reportan como apoyo.

**Regla para ajustar los umbrales.** CRISP-DM permite regresar a esta fase. Los umbrales pueden cambiar en fases posteriores con tres condiciones:
1. **Razones válidas.** El cambio se justifica por algo aprendido de los datos o del método. Por ejemplo, en la fase 2 la volatilidad de las secciones pequeñas puede resultar mayor de lo previsto, y entonces T4 o T5 tendrían que reconsiderarse.
2. **Razón inválida.** Un umbral no se ajusta solo porque una solución no lo alcanza.
3. **Registro.** Cada cambio se anota en la tabla de versiones con su fecha y su razón. En la fase 5 se reporta el resultado con los umbrales v1 y con los vigentes.

---

## 4. Plan del proyecto

### 4.1 Plan por fases

Por ahora el alcance es la fase 1 y la fase 2; las fases 3 a 6 se planearán al cerrar la fase 2. ⚑ Falta la fecha de entrega del curso para convertir semanas en fechas.

| Fase | Actividades | Entregable | Responsable |
|---|---|---|---|
| **1. Comprensión del negocio** (semana 1) | Revisar y aprobar este documento; decidir los puntos ⚑; consultar al profesor sobre la reutilización | Este documento, versión aprobada | ⚑ |
| **2. Comprensión de los datos** (semanas 2 y 3) | 2.1 Recolección: copiar los datos procesados del hackathon (CCPC, ECEG, medición de pobreza y cartografía); volver a descargar los zips de los CCPC (edad simple y verificación) y el manual; descargar el Índice de Rezago Social 2010, 2015 y 2020 | Reporte de recolección | ⚑ |
| | 2.2 Descripción: diccionario de datos, volumen y formato (comprobar los 192 archivos y ~3.5 GB de la propuesta); selección de indicadores del ECEG relevantes (escolaridad, lengua indígena, migración, servicios, conectividad, estructura por edad) | Diccionario de datos | ⚑ |
| | 2.3 Exploración: ciclo intermedia/presidencial; distribución de la participación por sección; edad × sexo; urbano/rural; mapa; trayectorias de ejemplo; primeras pruebas de persistencia (H2, H3) | Notebook y figuras | ⚑ |
| | 2.4 Calidad: faltantes y NS por elección y estado; coherencia LN = SV + NV + NS; secciones creadas o eliminadas; secciones pequeñas; cobertura del ECEG sobre las secciones de los CCPC; validación de los totales nacionales contra las cifras publicadas por el INE | Reporte de calidad | ⚑ |
| | 2.5 **Comparación del Índice de Rezago Social y la medición de pobreza** (criterios en §4.4) | Nota de decisión de la fuente municipal | ⚑ |
| 3. Preparación de los datos | Por planear | | |
| 4. Modelado | Por planear | | |
| 5. Evaluación | Por planear | | |
| 6. Despliegue | Por planear | | |

### 4.2 Evaluación inicial de herramientas y técnicas

| Necesidad | Herramienta | Comentario |
|---|---|---|
| Manejo de datos | pandas + Parquet | Formato del pipeline previo |
| K-means, Ward, CART, métricas | scikit-learn | Ward no escala a ~62 mil secciones con la matriz completa: se usará una submuestra o se aplicará sobre los centroides de un K-means fino |
| K-means con DTW | tslearn | Instalación probada en Python 3.14 |
| Mapas | geopandas + matplotlib | Cartografía en EPSG:6372 |
| Reproducibilidad | uv (dependencias declaradas en cada script) + git | Igual que en el hackathon |

### 4.3 Reutilización del trabajo previo

| Recurso (en `~/miscelaneous-projects/ine`) | Fase | Uso |
|---|---|---|
| `shared/download_data.py` | 2.1 | Descarga de los CCPC, el ECEG y la cartografía; verificar que las URL sigan vigentes |
| `shared/build_panel.py`, `reto1_perfiles/analysis/build_perfiles.py` | 2.1, 3 | Construcción del panel sección × elección y de la tabla por sexo y edad |
| `data/processed/*.parquet`, `secciones.gpkg` | 2 | Punto de partida; se regeneran con los scripts |
| `reto2_prediccion/analysis/eda.py` | 2.3 | Base para el ciclo nacional y la autocorrelación espacial |
| `reto1_perfiles/analysis/confiabilidad_rasgos.py` | 2.3 | Pruebas de persistencia (H2, H3, H5) |
| `reto1_perfiles/analysis/robustez_tipologia.py`, `elegir_k.py` | 5 | Nulo, estabilidad por municipios y validez temporal (T1–T3) |
| Perfiles y estrategias del Reto 1 | — | **No se reutilizan**: el objeto de agrupamiento es distinto |

### 4.4 Criterios para elegir la fuente municipal del CONEVAL (actividad 2.5 de la fase 2)

Hay dos candidatas, y las dos miden carencias a nivel municipal:
- **Índice de Rezago Social:** combina indicadores del censo (educación, acceso a salud, servicios y calidad de la vivienda, bienes del hogar) en un solo índice.
- **Medición de pobreza:** porcentajes de pobreza, pobreza extrema y carencias sociales. Además incorpora el **ingreso**, estimado con un modelo que combina la ENIGH y el censo.

| Criterio | Pregunta | Cómo se mide |
|---|---|---|
| C1. Cobertura | ¿Cubre todos los municipios de los CCPC, incluidos los creados después de 2010? | Proporción de municipios y de lista nominal con dato, usando la tabla de equivalencias INE-INEGI del hackathon |
| C2. Comparabilidad temporal | ¿Los tres años se pueden comparar entre sí? | Notas metodológicas del CONEVAL sobre cambios entre ediciones |
| C3. Valor añadido sobre el ECEG | ¿Aporta información que el ECEG por sección no tiene? | R² de cada fuente explicada por los indicadores del ECEG agregados al municipio. Un R² alto indica que la fuente es redundante. Se espera más redundancia en el índice, por construirse con variables del censo |
| C4. Granularidad | ¿Existe a un nivel más fino que el municipio? | Verificar si el CONEVAL publica el índice por localidad |
| C5. Interpretabilidad | ¿Se traduce en reglas claras para el árbol? | Un índice compuesto frente a porcentajes de carencias específicas |

**Regla de decisión:** se elige la fuente que cumpla C1 con al menos 98% de la lista nominal y aporte más en C3. Si ambas aportan poco sobre el ECEG, se usa solo el ECEG y la fuente municipal queda como descriptiva.

Para no adelantar el modelado, en esta comparación **no** se usa la relación de cada fuente con la participación ni con los grupos.

---

## 5. Decisiones del equipo

**Tomadas (v2, 17-nov-2026)**
- Umbrales T1–T7 y regla de elección de k: fijados como versión 1 (§3.3), con la regla para ajustarlos.
- ECEG 2020: se adopta como fuente principal de contexto por sección. Sustituye al ITER.
- Índice de Rezago Social o medición de pobreza: se decide en la fase 2 (actividad 2.5) con los criterios de §4.4.

**Tomadas (v3, 19-nov-2026)**
- T3 se compara con los estados agrupados en k regiones en lugar de con las 32 entidades (tabla de versiones y §3.3). Las 32 entidades se siguen reportando como referencia.
- Fase 4: cada integrante prueba un modelo de agrupamiento distinto y al final se combinan en un ensamble (acuerdo del 17-nov-2026; fase 3, §6).

**Pendientes** ⚑
1. Consultar con el profesor la reutilización del código y los hallazgos del hackathon.
2. Asignar responsables y fijar fechas con el calendario del curso.

## Referencias

- Chapman, P., Clinton, J., Kerber, R., Khabaza, T., Reinartz, T., Shearer, C. y Wirth, R. (2000). *CRISP-DM 1.0: Step-by-step data mining guide*. SPSS.
- Instituto Nacional Electoral (2024). *Conteos Censales de Participación Ciudadana 2009–2024* [datos abiertos]. DECEyEC.
- CONEVAL (2021). *Índice de Rezago Social 2020* (ediciones 2010 y 2015) y *Medición de la pobreza municipal 2010–2020*. Consejo Nacional de Evaluación de la Política de Desarrollo Social.
- INE-INEGI (2020). *Estadísticas Censales a Escalas Geoelectorales 2020*.
- Rousseeuw, P. J. (1987). Silhouettes: A graphical aid to the interpretation and validation of cluster analysis. *Journal of Computational and Applied Mathematics*, 20, 53–65.
- Sakoe, H. y Chiba, S. (1978). Dynamic programming algorithm optimization for spoken word recognition. *IEEE Transactions on Acoustics, Speech, and Signal Processing*, 26(1), 43–49.
