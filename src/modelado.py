"""Contrato común de la fase 4: cada integrante prueba un modelo de agrupamiento y después se combinan en un ensamble.

Por qué existe este módulo (docs/fase3_preparacion_datos.md §6):
  - Las etiquetas de un agrupamiento son arbitrarias (el «grupo 2» de K-means no es el «grupo 2» de Ward). Para
    combinarlas, todas las particiones deben cubrir las mismas 60,934 secciones, en el mismo orden.
  - Para elegir los mejores modelos, todos se miden con los criterios T1-T5 de la fase 1 calculados igual, sobre la
    misma muestra, las mismas réplicas bootstrap y los mismos datos nulos.
  - El ensamble necesita también las particiones de cada modelo en esas réplicas y en la ventana 2009-2018, para medir
    su propia estabilidad (T2) y validez temporal (T3) sin volver a correr los modelos de los demás.

Uso (ver src/fase4/plantilla_modelo.py):
    from modelado import cargar_entrada, evaluar_modelo, guardar_modelo
    def ajustar(X: np.ndarray, k: int, semilla: int) -> np.ndarray: ...   # etiquetas 0..k-1, una por renglón de X
    res = evaluar_modelo(ajustar, "forma")
    guardar_modelo("kmeans_forma", res, autor="...", algoritmo="K-means", parametros={...})

Requiere los archivos de data/processed/fase3/ (src/fase3/01-05).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from comun import PROC, RES

FASE3 = PROC / "fase3"
MODELOS = RES / "fase4" / "modelos"
K_RANGO = (4, 5, 6, 7)          # fase 1, criterio N1: entre 4 y 7 perfiles
N_MUESTRA = 8_000               # secciones para silueta y Davies-Bouldin (cálculo cuadrático)
N_REPLICAS = 20                 # T2: réplicas bootstrap por municipios
N_NULOS = 20                    # T1: réplicas normales multivariantes con la misma covarianza
SEMILLA = 20261118
UMBRAL_T2 = 0.60                # fase 1, §3.3
UMBRAL_T4 = 5.0                 # % de la lista nominal por grupo
UMBRAL_T5 = 0.10                # η² del log de la lista nominal

# Entradas disponibles: nombre → (archivo de la serie completa, archivo de la ventana 2009-2018, columnas)
ENTRADAS = {
    "forma": ("matriz_forma", "matriz_forma_2009_2018",
              ["z_nivel", "z_vaiven", "z_tendencia", "z_log_volatilidad", "z_brecha_joven", "z_brecha_genero"]),
    "forma_sin_nivel": ("matriz_forma", "matriz_forma_2009_2018",
                        ["z_vaiven", "z_tendencia", "z_log_volatilidad", "z_brecha_joven", "z_brecha_genero"]),
    "trayectoria_centrada": ("trayectoria_centrada", "trayectoria_centrada_2009_2018", None),
}


# ---------------------------------------------------------------- Datos
def tabla() -> pd.DataFrame:
    """Tabla analítica completa (60,934 secciones × 83 columnas), indexada por sid en el orden canónico."""
    return pd.read_parquet(FASE3 / "tabla_analitica.parquet").set_index("sid")


def cargar_entrada(nombre: str, ventana: bool = False) -> pd.DataFrame:
    """Matriz de entrada de un modelo, indexada por sid en el orden canónico. ventana=True: versión 2009-2018 (T3)."""
    completa, vent, cols = ENTRADAS[nombre]
    df = pd.read_parquet(FASE3 / f"{vent if ventana else completa}.parquet").set_index("sid")
    df = df.drop(columns="peso_LN_2024")
    if cols is not None:
        df = df[cols]
    orden = pd.read_parquet(FASE3 / "tabla_analitica.parquet", columns=["sid"]).sid
    assert df.index.equals(pd.Index(orden)), "el orden de las secciones no coincide con la tabla analítica"
    return df.astype("float64")


def muestra(n: int = N_MUESTRA) -> np.ndarray:
    """Posiciones (0..60,933) de las n secciones de la muestra fija de evaluación. Las muestras son anidadas."""
    m = pd.read_parquet(FASE3 / "modelado_muestra.parquet")
    return np.sort(m.posicion.to_numpy()[m.orden.to_numpy() < n])


def replicas(n: int = N_REPLICAS) -> list[np.ndarray]:
    """T2: por réplica, las posiciones de las secciones de los municipios remuestreados con reemplazo. Un municipio que
    sale dos veces aporta sus secciones dos veces (bootstrap verdadero)."""
    b = pd.read_parquet(FASE3 / "modelado_bootstrap.parquet")
    return [b.loc[b.replica == r, "posicion"].to_numpy() for r in range(1, n + 1)]


def nulo(X: np.ndarray, i: int) -> np.ndarray:
    """T1: datos sin grupos con la misma media y covarianza que X (normal multivariante), semilla fija por réplica."""
    rng = np.random.default_rng(SEMILLA + 1000 + i)
    return rng.multivariate_normal(X.mean(axis=0), np.cov(X, rowvar=False), size=len(X))


# ---------------------------------------------------------------- Métricas
def eta2(y: np.ndarray, etiquetas: np.ndarray) -> float:
    """Proporción de la varianza de y entre grupos (η², equivalente al R² con indicadoras de grupo)."""
    y = pd.Series(y)
    medias = y.groupby(etiquetas).transform("mean")
    return float(((medias - y.mean()) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def internas(X: np.ndarray, etiquetas: np.ndarray, pos: np.ndarray, distancia: Callable | None = None) -> dict:
    """Silueta y Davies-Bouldin sobre la muestra. distancia(A) -> matriz n×n permite otra métrica (p. ej. DTW)."""
    from sklearn.metrics import davies_bouldin_score, silhouette_score
    Xs, ls = X[pos], etiquetas[pos]
    if len(np.unique(ls)) < 2:
        return {"silueta": np.nan, "davies_bouldin": np.nan}
    sil = silhouette_score(distancia(Xs), ls, metric="precomputed") if distancia else silhouette_score(Xs, ls)
    return {"silueta": float(sil), "davies_bouldin": float(davies_bouldin_score(Xs, ls))}


def _ari(a, b) -> float:
    from sklearn.metrics import adjusted_rand_score
    return float(adjusted_rand_score(a, b))


@dataclass
class Resultado:
    entrada: str
    particiones: pd.DataFrame                    # sid × columnas k4..k7, ventana_k*, boot_k*_r* (−1 = fuera de la réplica)
    metricas: pd.DataFrame                       # un renglón por k con T1-T5 y métricas internas
    k_elegido: int | None
    nota_k: str
    segundos: float
    extra: dict = field(default_factory=dict)


def evaluar_modelo(ajustar: Callable[[np.ndarray, int, int], np.ndarray], entrada: str, k_rango=K_RANGO,
                   n_replicas: int = N_REPLICAS, n_nulos: int = N_NULOS, distancia: Callable | None = None,
                   verbose: bool = True) -> Resultado:
    """Corre el modelo y lo evalúa con los criterios T1-T5 de la fase 1, igual para todos los integrantes.

    ajustar(X, k, semilla) debe devolver una etiqueta entera por renglón de X. Puede ajustar con una submuestra (p. ej.
    Ward) siempre que asigne grupo a TODOS los renglones. Número de ajustes por k: 1 + n_replicas + n_nulos + 1.
    """
    t0 = time.time()
    T = tabla()
    X = cargar_entrada(entrada).to_numpy()
    Xv = cargar_entrada(entrada, ventana=True).to_numpy()
    F = cargar_entrada("forma").to_numpy()                       # espacio común para comparar modelos
    pos = muestra()
    reps = replicas(n_replicas)
    ln, log_ln = T.LN_2024.to_numpy(float), T.log_LN_2024.to_numpy()
    obj = {a: (T[f"r_{a}"].to_numpy(), ~T[f"imputado_{a}"].to_numpy()) for a in (2021, 2024)}
    r2_ent = {a: eta2(y[m], T.entidad.to_numpy()[m]) for a, (y, m) in obj.items()}
    rng = np.random.default_rng(SEMILLA)
    part = pd.DataFrame(index=T.index)
    filas = []
    for k in k_rango:
        def log(msg):
            if verbose:
                print(f"  k={k} {msg} ({time.time() - t0:.0f} s)", flush=True)
        e = np.asarray(ajustar(X, k, SEMILLA)).astype(int)
        assert e.shape == (len(X),) and e.min() >= 0, "ajustar debe devolver una etiqueta >= 0 por renglón"
        part[f"k{k}"] = e
        fila = {"k": k, "grupos": int(len(np.unique(e)))}
        peso = pd.Series(ln).groupby(e).sum() / ln.sum() * 100
        fila["T4_min_pct_LN"] = round(float(peso.min()), 2)
        fila["T5_eta2_logLN"] = round(eta2(log_ln, e), 4)
        fila.update({f"{m}_propio": round(v, 4) for m, v in internas(X, e, pos, distancia).items()})
        fila.update({f"{m}_comun": round(v, 4) for m, v in internas(F, e, pos).items()})
        log("partición completa")
        # T1: silueta frente a datos nulos con la misma covarianza
        sil_nulo = []
        for i in range(n_nulos):
            Xn = nulo(X, i)
            sil_nulo.append(internas(Xn, np.asarray(ajustar(Xn, k, SEMILLA)).astype(int), pos, distancia)["silueta"])
        if n_nulos:
            fila["T1_silueta_nulo_p95"] = round(float(np.nanpercentile(sil_nulo, 95)), 4)
            fila["T1_cumple"] = bool(fila["silueta_propio"] > fila["T1_silueta_nulo_p95"])
        log("T1 nulos")
        # T2: estabilidad con réplicas bootstrap por municipios
        aris = []
        for r, p in enumerate(reps, start=1):
            eb = np.asarray(ajustar(X[p], k, SEMILLA + r)).astype(int)
            uni, primero = np.unique(p, return_index=True)          # una etiqueta por sección (la primera aparición)
            col = np.full(len(X), -1)
            col[uni] = eb[primero]
            part[f"boot_k{k}_r{r:02d}"] = col
            aris.append(_ari(eb[primero], e[uni]))
        if reps:
            fila["T2_ARI_medio"] = round(float(np.mean(aris)), 4)
            fila["T2_cumple"] = bool(fila["T2_ARI_medio"] >= UMBRAL_T2)
        log("T2 bootstrap")
        # T3: grupos formados con 2009-2018 → R² de la participación relativa observada de 2021 y 2024
        ev = np.asarray(ajustar(Xv, k, SEMILLA)).astype(int)
        part[f"ventana_k{k}"] = ev
        for a, (y, m) in obj.items():
            r2 = eta2(y[m], ev[m])
            azar = np.mean([eta2(y[m], rng.permutation(ev[m])) for _ in range(20)])
            fila[f"T3_R2_{a}"], fila[f"T3_R2_{a}_azar"], fila[f"T3_R2_{a}_entidades"] = round(r2, 4), round(float(azar), 4), round(r2_ent[a], 4)
        fila["T3_cumple"] = bool(all(fila[f"T3_R2_{a}"] > max(fila[f"T3_R2_{a}_azar"], fila[f"T3_R2_{a}_entidades"]) for a in obj))
        fila["T4_cumple"] = bool(fila["T4_min_pct_LN"] >= UMBRAL_T4)
        fila["T5_cumple"] = bool(fila["T5_eta2_logLN"] < UMBRAL_T5)
        log("T3 ventana")
        filas.append(fila)
    met = pd.DataFrame(filas)
    # Regla de elección de k de la fase 1 (§3.3): entre los k que cumplen T2 y T4, el de mejor T3
    met["T3_R2_medio"] = met[["T3_R2_2021", "T3_R2_2024"]].mean(axis=1).round(4)
    ok = met[met.get("T2_cumple", True) & met.T4_cumple]
    if len(ok):
        k_el, nota = int(ok.sort_values("T3_R2_medio").k.iloc[-1]), "regla de la fase 1: cumple T2 y T4, mejor T3"
    else:
        k_el, nota = None, "ningún k cumple T2 y T4: el modelo no tiene k elegido (se reporta igual)"
    return Resultado(entrada, part.astype("int8"), met, k_el, nota, round(time.time() - t0, 1))


# ---------------------------------------------------------------- Entrega
def guardar_modelo(nombre: str, res: Resultado, autor: str, algoritmo: str, parametros: dict, notas: str = "") -> Path:
    """Escribe resultados/fase4/modelos/<nombre>/ con particiones.csv.gz, metricas.csv y ficha.json (se versionan)."""
    carpeta = MODELOS / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    validar_particiones(res.particiones)
    res.particiones.reset_index().to_csv(carpeta / "particiones.csv.gz", index=False, compression="gzip")
    res.metricas.to_csv(carpeta / "metricas.csv", index=False)
    ficha = {"nombre": nombre, "autor": autor, "algoritmo": algoritmo, "entrada": res.entrada, "parametros": parametros,
             "semilla": SEMILLA, "k_elegido": res.k_elegido, "nota_k": res.nota_k, "segundos": res.segundos,
             "n_replicas": max(sum(c.startswith(f"boot_k{k}_") for c in res.particiones.columns) for k in K_RANGO),
             "notas": notas}
    (carpeta / "ficha.json").write_text(json.dumps(ficha, indent=1, ensure_ascii=False))
    print(f"guardado en {carpeta}")
    return carpeta


def validar_particiones(p: pd.DataFrame) -> None:
    orden = pd.read_parquet(FASE3 / "tabla_analitica.parquet", columns=["sid"]).sid
    assert p.index.equals(pd.Index(orden, name=p.index.name)), "las particiones deben cubrir las 60,934 secciones en orden"
    for k in K_RANGO:
        if f"k{k}" in p:
            assert p[f"k{k}"].min() >= 0, f"k{k} tiene secciones sin grupo"


def leer_modelos() -> dict[str, dict]:
    """Para el ensamble: {nombre: {"ficha", "metricas", "particiones"}} de todos los modelos entregados."""
    out = {}
    for c in sorted(MODELOS.glob("*/ficha.json")):
        d = c.parent
        out[d.name] = {"ficha": json.loads(c.read_text()), "metricas": pd.read_csv(d / "metricas.csv"),
                       "particiones": pd.read_csv(d / "particiones.csv.gz").set_index("sid")}
    return out


def concordancia(particiones: dict[str, np.ndarray]) -> pd.DataFrame:
    """T7: ARI entre pares de particiones (mismo orden de secciones)."""
    n = list(particiones)
    return pd.DataFrame([[_ari(particiones[a], particiones[b]) for b in n] for a in n], index=n, columns=n).round(3)
