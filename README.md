# Trayectorias de participación electoral en México (2009–2024)

Proyecto final de Minería de Datos. Segmentación de secciones electorales por su trayectoria de participación, con la metodología CRISP-DM y los Conteos Censales de Participación Ciudadana del INE.

Equipo: Cruz Mendoza Valentina Ayelen, Nava Villavicencio Abraham, Negrete Mancera Leonardo y Pérez Bustamante José Julian.

## Estado por fase

| Fase CRISP-DM | Documento | Estado |
|---|---|---|
| 1. Comprensión del negocio | [`docs/fase1_comprension_negocio.md`](docs/fase1_comprension_negocio.md) | Versión 2: umbrales fijados; pendiente la consulta con el profesor y el calendario |
| 2. Comprensión de los datos | [`docs/fase2_comprension_datos.md`](docs/fase2_comprension_datos.md) | Borrador 1 para revisión del equipo |
| 3–6 | — | Por planear |

## Estructura

```
docs/                 documentos de cada fase
src/comun.py          rutas y definiciones compartidas (participación, elecciones, bandas de edad)
src/graficas.py       estilo y paleta de las figuras
src/fase2/            scripts de la fase 2, numerados en orden de ejecución
resultados/fase2/     tablas (csv), figuras (png) y resúmenes (json) que cita el documento de la fase 2
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
```
