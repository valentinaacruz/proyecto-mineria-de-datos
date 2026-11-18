# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow", "matplotlib"]
# ///
"""Fase 3.1-3.2 · Selección del universo de secciones y limpieza de la trayectoria de participación.

Decisiones (docs/fase3_preparacion_datos.md §1-§2, con la evidencia de la fase 2):
  - Participación ajustada SV / (SV + NV) y relativa al nacional de cada elección, en puntos porcentuales (pp).
  - Celda sección × elección FALTANTE si la sección no aparece ese año (incluido el hueco de 2012) o si su NS es
    100% (SV + NV = 0). Las celdas con NS alto pero < 100% se conservan: la fase 2 mostró que el NS no sesga (§4.3).
  - Universo: secciones que existen en 2024, están en el marco 2021 (ECEG y cartografía), tienen al menos 5 de 6
    elecciones válidas y lista nominal >= 200 en todas las elecciones en que aparecen.
  - Imputación de la celda faltante con un modelo aditivo de dos vías: r[s,e] = a[s] + b[municipio, e], ajustado por
    mínimos cuadrados alternados. b usa el municipio si tiene >= 5 secciones válidas en esa elección; si no, la entidad.
    Se valida ocultando celdas conocidas y se compara con alternativas más simples.
  - Ventana 2009-2018 (para el criterio T3 de la fase 1): se imputa por separado, sin usar 2021 ni 2024.

Uso:  uv run src/fase3/01_seleccionar_limpiar.py      (requiere los Parquet de src/fase2/02_construir_bases.py)
Salidas: data/processed/fase3/trayectorias.parquet; resultados/fase3/tablas/{cascada_universo, faltantes_por_eleccion,
         validacion_imputacion}.csv; resultados/fase3/fig/g01_cascada_universo.png, g02_validacion_imputacion.png
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import ELECCIONES, PROC, carpeta, participacion  # noqa: E402
from graficas import CAT, GRIS, TEXTO_2, guardar, plt  # noqa: E402

MIN_VALIDAS = 5          # elecciones válidas de 6
MIN_LN = 200             # lista nominal mínima en cada elección en que aparece la sección
MIN_SECC_MUNICIPIO = 5   # secciones válidas para estimar el efecto municipio × elección
VENTANA_T3 = [2009, 2012, 2015, 2018]
SEMILLA = 20261118

OUT = PROC / "fase3"
OUT.mkdir(parents=True, exist_ok=True)
TAB, FIG = carpeta("fase3", "tablas"), carpeta("fase3", "fig")
R = {}


def anotar(clave, valor):
    R[clave] = valor
    print(f"  {clave}: {valor}")


# ---------------------------------------------------------------- Participación relativa por sección × elección
sec = pd.read_parquet(PROC / "ccpc_seccion.parquet")
sec[["LN", "SV", "NV", "NS"]] = sec[["LN", "SV", "NV", "NS"]].astype("float64")
nac = sec.groupby("AELEC")[["SV", "NV"]].sum()
nac["p"] = participacion(nac)
sec["r"] = 100 * (participacion(sec) - sec.AELEC.map(nac.p))
sec.loc[sec.SV + sec.NV == 0, "r"] = np.nan                       # NS = 100%: participación no definida
anotar("participacion_nacional_pct", {int(a): round(100 * float(v), 2) for a, v in nac.p.items()})

r = sec.pivot_table(index="sid", columns="AELEC", values="r", dropna=False)[list(ELECCIONES)]
ln = sec.pivot_table(index="sid", columns="AELEC", values="LN")[list(ELECCIONES)]
s24 = sec[sec.AELEC == 2024].set_index("sid")
eceg = pd.read_parquet(PROC / "eceg2020.parquet", columns=["sid"]).sid
ln24_total = s24.LN.sum()

# ---------------------------------------------------------------- 3.1 Selección: cascada de criterios
pasos = [
    ("Todas las secciones de los conteos 2009–2024", pd.Series(True, index=r.index)),
    ("Existe en 2024", r.index.isin(s24.index)),
    ("Está en el marco 2021 (ECEG y cartografía)", r.index.isin(eceg)),
    (f"Al menos {MIN_VALIDAS} de 6 elecciones con participación definida", r.notna().sum(axis=1) >= MIN_VALIDAS),
    (f"Lista nominal ≥ {MIN_LN} en todas las elecciones en que aparece", ln.min(axis=1) >= MIN_LN),
]
casc, dentro = [], pd.Series(True, index=r.index)
for nombre, cond in pasos:
    dentro &= np.asarray(cond)
    ids = dentro[dentro].index
    casc.append({"criterio": nombre, "secciones": int(dentro.sum()),
                 "LN_2024_millones": round(float(s24.LN.reindex(ids).sum()) / 1e6, 2),
                 "pct_LN_2024": round(100 * float(s24.LN.reindex(ids).sum()) / ln24_total, 2)})
casc = pd.DataFrame(casc)
casc["excluidas"] = (-casc.secciones.diff()).fillna(0).astype(int)
casc.to_csv(TAB / "cascada_universo.csv", index=False)
print(casc.to_string(index=False))
U = dentro[dentro].index
anotar("universo_secciones", int(len(U)))
anotar("universo_pct_LN_2024", float(casc.pct_LN_2024.iloc[-1]))
# Referencia: exigir las seis elecciones válidas (sin imputar)
seis = r.loc[U].notna().all(axis=1)
anotar("universo_con_6_validas", int(seis.sum()))
anotar("pct_LN_2024_con_6_validas", round(100 * float(s24.LN.reindex(seis[seis].index).sum()) / ln24_total, 2))

ru = r.loc[U].astype("float64")
mun = (s24.EDOCVE.astype("int64") * 1000 + s24.MPIOCVE.astype("int64")).reindex(U)   # municipio INE en 2024
ent = s24.EDOCVE.astype("int64").reindex(U)

causa = pd.DataFrame(index=U, columns=list(ELECCIONES), dtype=object)
causa[:] = ""
presente = ln.loc[U].notna()
causa = causa.mask(~presente, "no aparece").mask(presente & ru.isna(), "NS 100%")
falt = pd.DataFrame({a: causa[a].value_counts() for a in ELECCIONES}).drop(index="", errors="ignore").fillna(0).astype(int)
falt.loc["total"] = falt.sum()
falt.to_csv(TAB / "faltantes_por_eleccion.csv")
print(falt.to_string())
anotar("secciones_con_una_celda_imputada", int(ru.isna().any(axis=1).sum()))
anotar("faltantes_2012_no_aparece", int(falt.loc["no aparece", 2012]) if "no aparece" in falt.index else 0)


# ---------------------------------------------------------------- 3.2 Limpieza: imputación de dos vías
def ajustar(m: pd.DataFrame, grupos: pd.Series, iteraciones: int = 30):
    """Mínimos cuadrados alternados de r[s,e] = a[s] + b[g,e] con celdas faltantes. Devuelve a (por sección) y la
    matriz B (b del grupo de cada sección, con la forma de m)."""
    a = m.mean(axis=1)
    for _ in range(iteraciones):
        b = m.sub(a, axis=0).groupby(grupos).mean()
        B = pd.DataFrame(b.reindex(grupos.values).values, index=m.index, columns=m.columns)
        a = (m - B).mean(axis=1)
    return a, B


def imputar(m: pd.DataFrame) -> pd.DataFrame:
    """Valor esperado a[s] + b[municipio, e]; b de la entidad donde el municipio tiene < MIN_SECC_MUNICIPIO válidas."""
    a_m, B_m = ajustar(m, mun.reindex(m.index))
    _, B_e = ajustar(m, ent.reindex(m.index))
    n_val = m.notna().groupby(mun.reindex(m.index)).sum()
    N = pd.DataFrame(n_val.reindex(mun.reindex(m.index).values).values, index=m.index, columns=m.columns)
    return B_m.where(N >= MIN_SECC_MUNICIPIO, B_e).add(a_m, axis=0)


# Validación: ocultar una celda al azar en 20% de las secciones completas y predecirla
rng = np.random.default_rng(SEMILLA)
completas = ru.index[ru.notna().all(axis=1)]
ocultas = rng.choice(completas, size=len(completas) // 5, replace=False)
anios = rng.choice(list(ELECCIONES), size=len(ocultas))
fila, col = ru.index.get_indexer(ocultas), ru.columns.get_indexer(anios)
arr = ru.to_numpy(copy=True)
verdad = arr[fila, col].copy()
arr[fila, col] = np.nan
m_val = pd.DataFrame(arr, index=ru.index, columns=ru.columns)
pres_cols = [a for a in ELECCIONES if a in (2012, 2018, 2024)]
inter_cols = [a for a in ELECCIONES if a not in pres_cols]
mismo_tipo = np.where(np.isin(anios, pres_cols), m_val[pres_cols].mean(axis=1).loc[ocultas], m_val[inter_cols].mean(axis=1).loc[ocultas])
candidatos = {
    "Promedio de la sección": m_val.mean(axis=1).loc[ocultas].values,
    "Promedio de la sección, mismo tipo de elección": mismo_tipo,
    "Sección + entidad × elección": ajustar(m_val, ent)[1].add(ajustar(m_val, ent)[0], axis=0).values[fila, col],
    "Sección + municipio × elección (elegido)": imputar(m_val).values[fila, col],
}
val = []
for nombre, pred in candidatos.items():
    e = pred - verdad
    val.append({"metodo": nombre, "celdas": len(e), "RMSE_pp": round(float(np.sqrt(np.mean(e ** 2))), 2),
                "MAE_pp": round(float(np.mean(np.abs(e))), 2), "sesgo_pp": round(float(e.mean()), 2)})
elegido = candidatos["Sección + municipio × elección (elegido)"]
for a in ELECCIONES:
    k = anios == a
    e = elegido[k] - verdad[k]
    val.append({"metodo": f"  elegido, solo {a}", "celdas": int(k.sum()), "RMSE_pp": round(float(np.sqrt(np.mean(e ** 2))), 2),
                "MAE_pp": round(float(np.mean(np.abs(e))), 2), "sesgo_pp": round(float(e.mean()), 2)})
val = pd.DataFrame(val)
val.to_csv(TAB / "validacion_imputacion.csv", index=False)
print(val.to_string(index=False))
anotar("imputacion_RMSE_pp", {v.metodo: v.RMSE_pp for v in val.itertuples() if not v.metodo.startswith("  ")})

# Imputación definitiva (seis elecciones) y de la ventana 2009-2018 (sin información de 2021 ni 2024)
esperado = imputar(ru)
tray = ru.where(ru.notna(), esperado)
imp = ru.isna()
rv = ru[VENTANA_T3]
ok_v = rv.notna().sum(axis=1) >= len(VENTANA_T3) - 1          # al menos 3 de 4 válidas en la ventana
tray_v = rv.where(rv.notna(), imputar(rv[ok_v]).reindex(rv.index))
tray_v[~ok_v] = np.nan
anotar("ventana_2009_2018_secciones", int(ok_v.sum()))

out = pd.DataFrame(index=U)
out.index.name = "sid"
for a in ELECCIONES:
    out[f"r_{a}"] = tray[a]
for a in ELECCIONES:
    out[f"imputado_{a}"] = imp[a]
out["n_imputadas"] = imp.sum(axis=1).astype("int8")
for a in VENTANA_T3:
    out[f"rv_{a}"] = tray_v[a]          # trayectoria de la ventana 2009-2018, imputada solo con esa ventana
out.reset_index().to_parquet(OUT / "trayectorias.parquet", index=False)
print("trayectorias", out.shape)

# ---------------------------------------------------------------- Figuras
fig, ax = plt.subplots(figsize=(7.6, 3.2))
y = np.arange(len(casc))[::-1]
ax.barh(y, casc.secciones, color=CAT[0], height=0.6)
for yy, s, p in zip(y, casc.secciones, casc.pct_LN_2024):
    ax.text(s + 600, yy, f"{s:,}  ·  {p:.1f}% LN 2024", va="center", fontsize=8, color=TEXTO_2)
ax.set_yticks(y, casc.criterio, fontsize=8)
ax.set_xlim(0, casc.secciones.max() * 1.38)
ax.xaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
ax.grid(axis="y", visible=False)
ax.set_title("Selección del universo: secciones que quedan tras cada criterio")
guardar(fig, FIG / "g01_cascada_universo.png")

fig, ax = plt.subplots(figsize=(6.6, 2.6))
v = val[~val.metodo.str.startswith("  ")].iloc[::-1]
colores = [CAT[0] if "elegido" in m else GRIS for m in v.metodo]
ax.barh(v.metodo, v.RMSE_pp, color=colores, height=0.55)
for i, x in enumerate(v.RMSE_pp):
    ax.text(x + 0.1, i, f"{x:.2f} pp", va="center", fontsize=8, color=TEXTO_2)
ax.set_xlim(0, v.RMSE_pp.max() * 1.25)
ax.set_xlabel("Error (RMSE) al predecir celdas conocidas ocultadas, pp")
ax.tick_params(axis="y", labelsize=8)
ax.grid(axis="y", visible=False)
ax.set_title("Validación de la imputación")
guardar(fig, FIG / "g02_validacion_imputacion.png")

(carpeta("fase3") / "seleccion_resumen.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str))
print("listo")
