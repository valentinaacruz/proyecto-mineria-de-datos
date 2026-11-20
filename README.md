# Trayectorias de participación electoral en México (2009–2024)

Proyecto final de Minería de Datos. Segmentación de secciones electorales por su trayectoria de participación, con la metodología CRISP-DM y los Conteos Censales de Participación Ciudadana del INE.

Equipo: Cruz Mendoza Valentina Ayelen, Nava Villavicencio Abraham, Negrete Mancera Leonardo y Pérez Bustamante José Julian.

## Estado por fase

| Fase CRISP-DM | Documento | Estado |
|---|---|---|
| 1. Comprensión del negocio | [`docs/fase1_comprension_negocio.md`](docs/fase1_comprension_negocio.md) | Versión 3 (19-nov-2026): referencia de T3 ajustada; pendiente la consulta con el profesor y el calendario |
| 2. Comprensión de los datos | [`docs/fase2_comprension_datos.md`](docs/fase2_comprension_datos.md) · notebook [`notebooks/fase2_comprension_datos.ipynb`](notebooks/fase2_comprension_datos.ipynb) | Borrador 1 para revisión del equipo |
| 3. Preparación de los datos | [`docs/fase3_preparacion_datos.md`](docs/fase3_preparacion_datos.md) | Borrador 2 (19-nov-2026): universo de 5 de 6 confirmado y T3 ajustado; deja listo el contrato para la fase 4 (§6) |
| 4. Modelado | Plantilla [`src/fase4/plantilla_modelo.py`](src/fase4/plantilla_modelo.py) | Acordado: un modelo por integrante y un ensamble al final; falta asignar los modelos |
| 5–6 | — | Por planear |

## Estructura

```
docs/                 documentos de cada fase
notebooks/            la misma fase calculada paso a paso desde los datos crudos, con gráficas y explicaciones
src/comun.py          rutas y definiciones compartidas (participación, elecciones, bandas de edad)
src/graficas.py       estilo y paleta de las figuras
src/modelado.py       contrato común de la fase 4: entradas, evaluación T1–T5, entrega y lectura de modelos
src/fase2/            scripts de la fase 2, numerados en orden de ejecución
src/fase3/            scripts de la fase 3 (selección, limpieza, variables, contexto, formato e insumos de la fase 4)
src/fase4/            un script por modelo, copiado de plantilla_modelo.py
resultados/fase2/     tablas (csv), figuras (png) y resúmenes (json) que cita el documento de la fase 2
resultados/fase3/     ídem para la fase 3
resultados/fase4/modelos/  la entrega de cada modelo (particiones, métricas y ficha); de aquí lee el ensamble
data/raw/             descargas oficiales (no se versiona; se regenera con 01_descargar.py)
data/processed/       bases de trabajo en Parquet (no se versiona; se regenera con 02_construir_bases.py)
```

## Cómo reproducir

Requiere [uv](https://docs.astral.sh/uv/). Cada script declara sus dependencias, así que no hay que crear entornos a mano. Desde la raíz del repositorio:

```
uv run src/fase2/01_descargar.py
uv run src/fase2/02_construir_bases.py
uv run src/fase2/03_describir_calidad.py
uv run src/fase2/04_explorar.py
uv run src/fase2/05_comparar_coneval.py

uv run src/fase3/01_seleccionar_limpiar.py
uv run src/fase3/02_construir_variables.py
uv run src/fase3/03_integrar_contexto.py
uv run src/fase3/04_formatear.py
uv run src/fase3/05_preparar_modelado.py
```

La fase 3 deja la tabla analítica, las matrices para el modelado y los insumos fijos de evaluación en `data/processed/fase3/` (menos de 10 segundos en total).

**Fase 4 (un modelo por integrante).** Copia `src/fase4/plantilla_modelo.py` como `src/fase4/<tu_modelo>.py`, reescribe `ajustar()` y córrelo con `uv run src/fase4/<tu_modelo>.py`. Para probar rápido sin guardar nada, agrega `--prueba`. Las reglas y su porqué están en la [§6 de la fase 3](docs/fase3_preparacion_datos.md#6-preparación-para-el-modelado-en-paralelo-y-el-ensamble).

Los notebooks hacen los mismos cálculos desde cero (descargan los datos si faltan), explicados paso a paso. La ejecución completa de la fase 2 tarda unos 15 minutos:

```
uv run --with jupyter --with pandas --with pyarrow --with openpyxl --with matplotlib --with jinja2 \
       --with geopandas --with scikit-learn --with requests jupyter lab notebooks/
```
