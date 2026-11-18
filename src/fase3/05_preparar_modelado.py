# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow"]
# ///
"""Fase 3.5 (continuación) · Insumos fijos para que todos los modelos de la fase 4 se evalúen igual y se puedan ensamblar.

Decisión del equipo (18-nov-2026): cada integrante prueba un modelo de agrupamiento distinto y al final se combinan en
un ensamble. Para que las particiones sean comparables y combinables (docs/fase3_preparacion_datos.md §6):
  - modelado_muestra.parquet: un orden aleatorio fijo de las 60,934 secciones. Las primeras n forman la muestra de
    evaluación (silueta y Davies-Bouldin son cuadráticos; por defecto n = 8,000). Las muestras son anidadas.
  - modelado_bootstrap.parquet: 20 réplicas bootstrap por municipios (T2), iguales para todos los modelos y para el
    ensamble. Se remuestrean municipios con reemplazo y cada uno aporta todas sus secciones, tantas veces como salga.

Uso:  uv run src/fase3/05_preparar_modelado.py      (requiere 04_formatear.py)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import PROC, carpeta  # noqa: E402

OUT = PROC / "fase3"
SEMILLA = 20261118
N_REPLICAS = 20

t = pd.read_parquet(OUT / "tabla_analitica.parquet", columns=["sid", "mun_ine", "entidad"])
rng = np.random.default_rng(SEMILLA)

orden = rng.permutation(len(t))
pd.DataFrame({"sid": t.sid, "posicion": np.arange(len(t)), "orden": np.argsort(orden)}).to_parquet(
    OUT / "modelado_muestra.parquet", index=False)

pos_mun = t.groupby("mun_ine").indices                      # municipio → posiciones de sus secciones
muns = np.array(sorted(pos_mun))
filas, tamanos = [], []
for r in range(1, N_REPLICAS + 1):
    sorteo = rng.choice(muns, size=len(muns), replace=True)
    p = np.concatenate([pos_mun[m] for m in sorteo])
    filas.append(pd.DataFrame({"replica": r, "posicion": p}))
    tamanos.append({"replica": r, "renglones": len(p), "secciones_distintas": int(len(np.unique(p))),
                    "municipios_distintos": int(len(np.unique(sorteo)))})
pd.concat(filas, ignore_index=True).astype({"replica": "int8", "posicion": "int32"}).to_parquet(
    OUT / "modelado_bootstrap.parquet", index=False)

tam = pd.DataFrame(tamanos)
resumen = {"secciones": len(t), "municipios": len(muns), "replicas": N_REPLICAS,
           "renglones_por_replica_mediana": int(tam.renglones.median()),
           "pct_secciones_distintas_por_replica_mediana": round(float(100 * tam.secciones_distintas.median() / len(t)), 1),
           "pct_municipios_distintos_por_replica_mediana": round(float(100 * tam.municipios_distintos.median() / len(muns)), 1)}
(carpeta("fase3") / "modelado_resumen.json").write_text(json.dumps(resumen, indent=1, ensure_ascii=False))
print(resumen)
print("listo")
