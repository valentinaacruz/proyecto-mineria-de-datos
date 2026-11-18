# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow", "matplotlib", "geopandas"]
# ///
"""Fase 2.2 (descripción) y 2.4 (calidad) de los Conteos Censales y de su cobertura por ECEG y cartografía.

Uso:  uv run src/fase2/03_describir_calidad.py      (requiere 02_construir_bases.py)
Salidas: resultados/fase2/tablas/*.csv, resultados/fase2/fig/*.png y resultados/fase2/calidad_resumen.json
"""
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import ELECCIONES, ENTIDADES, PROC, RAW, carpeta, participacion  # noqa: E402
from graficas import CAT, CMAP_SEQ, GRIS, TEXTO_2, guardar, plt  # noqa: E402

TAB, FIG = carpeta("fase2", "tablas"), carpeta("fase2", "fig")
R = {}  # resumen numérico para el reporte


def anotar(clave, valor):
    R[clave] = valor
    print(f"  {clave}: {valor}")


sec = pd.read_parquet(PROC / "ccpc_seccion.parquet")
sec[["LN", "SV", "NV", "NS"]] = sec[["LN", "SV", "NV", "NS"]].astype("float64")  # Int64 → float para cálculos y figuras
lec = pd.read_csv(TAB / "lectura_archivos.csv")
nac = sec.groupby("AELEC")[["LN", "SV", "NV", "NS"]].sum()
nac["p"] = participacion(nac)
sec["p"] = participacion(sec)
sec["r"] = sec.p - sec.AELEC.map(nac.p)          # participación relativa al nacional (proporción)
sec["ns_share"] = sec.NS / sec.LN

# ---------------------------------------------------------------- A. Volumen
print("A. volumen")
vol = []
for anio in ELECCIONES:
    with zipfile.ZipFile(RAW / "ccpc" / f"ccpc_{anio}.zip") as zf:
        csv = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
        vol.append({"eleccion": anio, "archivos_csv": len(csv), "mb_sin_comprimir": sum(i.file_size for i in csv) / 1e6,
                    "mb_comprimido": (RAW / "ccpc" / f"ccpc_{anio}.zip").stat().st_size / 1e6})
vol = pd.DataFrame(vol).set_index("eleccion").join(lec.groupby("anio").agg(filas=("filas", "sum")))
vol = vol.join(sec.groupby("AELEC").agg(secciones=("sid", "nunique"), municipios=("MPIOCVE", lambda s: 0)))
vol["municipios"] = sec.assign(m=sec.EDOCVE * 1000 + sec.MPIOCVE).groupby("AELEC").m.nunique()
vol = vol.join(nac[["LN", "SV", "NV", "NS"]])
vol.to_csv(TAB / "volumen_ccpc.csv")
anotar("archivos_csv", int(vol.archivos_csv.sum()))
anotar("gb_sin_comprimir", round(vol.mb_sin_comprimir.sum() / 1e3, 2))
anotar("filas_crudas", int(vol.filas.sum()))

# ---------------------------------------------------------------- B. Diccionario de datos de los CCPC
print("B. diccionario")
crudo = pd.read_csv(TAB / "lectura_archivos.csv")
desc = {
    "AELEC": "Año de la elección", "FELECCION": "Fecha de la jornada electoral",
    "EDOCVE": "Clave INE de entidad federativa", "EDONOM": "Nombre de la entidad",
    "MPIOCVE": "Clave INE de municipio (no coincide siempre con la del INEGI)", "MPIONOM": "Nombre del municipio",
    "SECCION": "Sección electoral en el año correspondiente (numerada dentro de cada entidad)",
    "TIPOSEC": "Tipo de sección en el año: U urbana, M mixta, R rural",
    "DEF": "Distrito electoral federal (marco DERFE 2021; en 2024, marco 2023)",
    "DEL": "Distrito electoral local (marco DERFE 2021; en 2024, marco 2023)",
    "SEXO": "0 hombres, 1 mujeres, 2 no binario (solo 2024)", "EDAD": "Años cumplidos el día de la elección",
    "LN": "Lista nominal de los cuadernillos de las casillas", "SV": "Registros con marca de voto",
    "NV": "Registros sin marca de voto",
    "NS": "Registros no especificados (cuadernillo sin marcas, no disponible, solicitado por autoridad jurisdiccional o página faltante)",
}
dic = []
for c, d in desc.items():
    fila = {"campo": c, "descripcion_oficial": d}
    if f"vacio_{c}" in crudo:
        fila["celdas_vacias"] = int(crudo[f"vacio_{c}"].sum())
        fila["celdas_no_numericas"] = int(crudo[f"no_numerico_{c}"].sum())
    dic.append(fila)
dic = pd.DataFrame(dic)
dic["tipo"] = dic.campo.map(lambda c: "texto" if c in ("FELECCION", "EDONOM", "MPIONOM", "TIPOSEC") else "entero")
dic.loc[dic.campo == "EDAD", "rango_observado"] = f"{int(crudo.edad_min.min())}–{int(crudo.edad_max.max())}"
dic.to_csv(TAB / "diccionario_ccpc.csv", index=False)

# ---------------------------------------------------------------- C. Validación contra cifras publicadas
print("C. validación externa")
publicado = {(2012, "Nacional"): 62.1, (2018, "Nacional"): 62.4, (2024, "Nacional"): 59.7,
             (2024, "Yucatán"): 71.4, (2024, "Baja California"): 47.0}
ent = sec.groupby(["AELEC", "EDOCVE"])[["SV", "NV"]].sum()
ent["p"] = participacion(ent)
val = []
for (anio, ambito), pub in publicado.items():
    calc = nac.p[anio] if ambito == "Nacional" else ent.p[(anio, {v: k for k, v in ENTIDADES.items()}[ambito])]
    val.append({"eleccion": anio, "ambito": ambito, "publicado_pct": pub, "calculado_pct": round(100 * calc, 2),
                "diferencia_pp": round(100 * calc - pub, 2)})
val = pd.DataFrame(val)
val.to_csv(TAB / "validacion_publicadas.csv", index=False)
print(val.to_string(index=False))
anotar("validacion_max_dif_pp", float(val.diferencia_pp.abs().max()))
nac_out = nac.assign(participacion_pct=100 * nac.p, participacion_cruda_pct=100 * nac.SV / nac.LN, ns_pct=100 * nac.NS / nac.LN)
nac_out.drop(columns="p").round(2).to_csv(TAB / "nacional_por_eleccion.csv")

# ---------------------------------------------------------------- D. Registros no especificados (NS)
print("D. NS")
ns_ent = (sec.groupby(["EDOCVE", "AELEC"])[["NS", "LN"]].sum().pipe(lambda d: 100 * d.NS / d.LN).unstack())
ns_ent.index = ns_ent.index.map(ENTIDADES)
ns_ent.round(2).to_csv(TAB / "ns_entidad_eleccion.csv")
fig, ax = plt.subplots(figsize=(6.2, 8.4))
im = ax.imshow(ns_ent.values, cmap=CMAP_SEQ, aspect="auto", vmin=0, vmax=max(20, np.nanmax(ns_ent.values)))
ax.set_xticks(range(len(ns_ent.columns)), ns_ent.columns)
ax.set_yticks(range(len(ns_ent)), ns_ent.index, fontsize=8)
ax.grid(False)
for i in range(ns_ent.shape[0]):
    for j in range(ns_ent.shape[1]):
        v = ns_ent.values[i, j]
        ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6.5, color="white" if v > 10 else TEXTO_2)
ax.set_title("Registros no especificados (% de la lista nominal)")
fig.colorbar(im, ax=ax, shrink=0.5, label="% NS")
guardar(fig, FIG / "f01_ns_entidad_eleccion.png")

cortes = [-0.001, 0, 0.05, 0.2, 0.5, 0.9999, 1.0]
etiq = ["0%", "0–5%", "5–20%", "20–50%", "50–<100%", "100%"]
sec["ns_bin"] = pd.cut(sec.ns_share, cortes, labels=etiq)
ns_bins = sec.groupby(["AELEC", "ns_bin"], observed=False).size().unstack()
ns_bins.to_csv(TAB / "ns_distribucion_secciones.csv")
anotar("secciones_eleccion_ns_100pct", int((sec.ns_share >= 0.9999).sum()))
anotar("secciones_eleccion_ns_mas_20pct", int((sec.ns_share > 0.2).sum()))

# Supuesto de la fase 1: el NS no depende del comportamiento. Si fuera aleatorio, la participación de una sección en
# una elección con mucho NS no se desviaría de su participación relativa habitual (promedio de sus otras elecciones).
n_obs = sec.groupby("sid").r.transform("count")
suma = sec.groupby("sid").r.transform("sum")
sec["desvio"] = sec.r - (suma - sec.r) / (n_obs - 1)
prueba = (sec[(n_obs >= 4) & sec.r.notna() & (sec.ns_share < 0.9999)]
          .groupby("ns_bin", observed=True).desvio.agg(["count", "mean", "median", "std"]))
prueba["ee"] = prueba["std"] / np.sqrt(prueba["count"])
prueba[["mean", "median", "std", "ee"]] *= 100   # puntos porcentuales
prueba.round(3).to_csv(TAB / "ns_prueba_supuesto.csv")
print(prueba.round(2).to_string())

# ---------------------------------------------------------------- E. Edades extremas
print("E. edades")
ne = pd.read_parquet(PROC / "ccpc_nacional_edad.parquet")
ne["grupo"] = pd.cut(ne.EDAD, [17, 89, 99, 109, 200], labels=["18–89", "90–99", "100–109", "110+"])
ed = ne.groupby(["AELEC", "grupo"], observed=True)[["LN", "SV", "NV", "NS"]].sum()
ed["participacion_pct"] = 100 * participacion(ed)
ed["pct_LN"] = 100 * ed.LN / ed.groupby(level=0).LN.transform("sum")
ed.round(3).to_csv(TAB / "edades_extremas.csv")
print(ed.round(2).to_string())
anotar("LN_100mas_2024", int(ed.loc[(2024, "100–109"), "LN"] + ed.loc[(2024, "110+"), "LN"]))

# ---------------------------------------------------------------- F. Cobertura temporal y cambios cartográficos
print("F. cobertura temporal")
pres = sec.pivot_table(index="sid", columns="AELEC", values="LN", aggfunc="sum").notna()
n_elec = pres.sum(axis=1)
patron = pres.apply(lambda f: "".join("●" if v else "·" for v in f), axis=1)
ln24 = sec[sec.AELEC == 2024].set_index("sid").LN
cob = pd.DataFrame({"secciones": n_elec.value_counts().sort_index()})
cob["LN_2024"] = ln24.groupby(n_elec).sum()
cob["pct_LN_2024"] = 100 * cob.LN_2024 / ln24.sum()
cob.to_csv(TAB / "cobertura_num_elecciones.csv")
pat = pd.DataFrame({"patron": patron, "LN24": ln24}).groupby("patron").agg(secciones=("LN24", "size"), LN_2024=("LN24", "sum"))
pat.sort_values("secciones", ascending=False).head(15).to_csv(TAB / "cobertura_patrones.csv")
anotar("secciones_universo", int(len(pres)))
anotar("secciones_6_elecciones", int((n_elec == 6).sum()))
anotar("secciones_4mas_elecciones", int((n_elec >= 4).sum()))
anotar("pct_LN2024_en_6_elecciones", round(float(cob.loc[6, "pct_LN_2024"]), 2))
anotar("pct_LN2024_en_4mas", round(float(cob.loc[cob.index >= 4, "pct_LN_2024"].sum()), 2))
primera, ultima = pres.idxmax(axis=1), pres[pres.columns[::-1]].idxmax(axis=1)
altas_bajas = pd.DataFrame({"altas (primera aparición)": primera.value_counts(), "bajas (última aparición)": ultima.value_counts()}).sort_index()
altas_bajas.to_csv(TAB / "cobertura_altas_bajas.csv")
huecos = pres.apply(lambda f: "●·" in "".join("●" if v else "·" for v in f) and "·●" in "".join("●" if v else "·" for v in f), axis=1)
anotar("secciones_con_huecos", int(huecos.sum()))  # aparecen, desaparecen y reaparecen

# Hueco de 2012: secciones presentes en 2009 y 2015 pero ausentes en 2012. Si fueran cambios cartográficos no
# reaparecerían con el mismo tamaño; la hipótesis es que en 2012 los cuadernillos no capturados se omitieron
# (NS de solo 0.2% ese año) en lugar de registrarse como NS.
lnp = sec.pivot_table(index="sid", columns="AELEC", values="LN", aggfunc="sum")
hueco12 = lnp[lnp[2009].notna() & lnp[2012].isna() & lnp[2015].notna()].index
anotar("hueco_2012_secciones", int(len(hueco12)))
anotar("hueco_2012_LN_mediana_2009_2015", [float(lnp.loc[hueco12, 2009].median()), float(lnp.loc[hueco12, 2015].median())])
anotar("hueco_2012_entidades_top", sec[sec.sid.isin(hueco12) & (sec.AELEC == 2009)].EDOCVE.map(ENTIDADES).value_counts().head(5).to_dict())
r15 = sec[sec.AELEC == 2015].set_index("sid").r
anotar("hueco_2012_r2015_pp_vs_resto", [round(float(100 * r15[r15.index.isin(hueco12)].mean()), 2), round(float(100 * r15[~r15.index.isin(hueco12)].mean()), 2)])
ln_completas = (lnp[n_elec == 6].sum() / 1e6).round(2)
ln_completas.rename("LN_millones_secciones_en_6").to_csv(TAB / "ln_secciones_completas.csv")
anotar("LN_millones_secciones_en_6", {int(k): float(v) for k, v in ln_completas.items()})

fig, ax = plt.subplots(figsize=(6, 3.2))
ax.bar(cob.index.astype(str), cob.secciones, color=CAT[0], width=0.6)
for x, (s, p) in enumerate(zip(cob.secciones, cob.pct_LN_2024)):
    ax.text(x, s, f"{s:,}\n{p:.1f}% LN 2024", ha="center", va="bottom", fontsize=7.5, color=TEXTO_2)
ax.set_xlabel("Número de elecciones en que aparece la sección")
ax.set_ylabel("Secciones")
ax.set_ylim(0, cob.secciones.max() * 1.22)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
ax.grid(axis="x", visible=False)
ax.set_title("Historia disponible por sección (2009–2024)")
guardar(fig, FIG / "f02_cobertura_elecciones.png")

# ---------------------------------------------------------------- G. Consistencia de metadatos entre elecciones
print("G. metadatos")
g = sec.groupby("sid")
anotar("secciones_cambian_tipo", int((g.TIPOSEC.nunique() > 1).sum()))
anotar("secciones_cambian_municipio", int((g.MPIOCVE.nunique() > 1).sum()))
cambios_tipo = (sec.sort_values(["sid", "AELEC"]).assign(prev=lambda d: d.groupby("sid").TIPOSEC.shift())
                .dropna(subset=["prev"]).query("prev != TIPOSEC").groupby(["prev", "TIPOSEC"], observed=True).size())
cambios_tipo.rename("transiciones").to_csv(TAB / "cambios_tipo_seccion.csv")
sin_def = sec[sec.DEF.isna()]
anotar("seccion_eleccion_sin_DEF", int(len(sin_def)))
anotar("sin_DEF_ausentes_en_2021", int((~sin_def.sid.isin(sec[sec.AELEC == 2021].sid)).sum()))
anotar("seccion_eleccion_sin_DEL_2024", int(sec[(sec.AELEC == 2024) & sec.DEL.isna()].shape[0]))
anotar("entidades_sin_DEL_2024", sorted(sec[(sec.AELEC == 2024) & sec.DEL.isna()].EDOCVE.map(ENTIDADES).unique().tolist()))
tipo24 = sec[sec.AELEC == 2024].groupby("TIPOSEC", observed=True).agg(secciones=("sid", "size"), LN=("LN", "sum"))
tipo24["pct_LN"] = 100 * tipo24.LN / tipo24.LN.sum()
tipo24.to_csv(TAB / "tipo_seccion_2024.csv")

# ---------------------------------------------------------------- H. Tamaño de sección y ruido
print("H. tamaño")
q = sec[sec.AELEC == 2024].LN.quantile([0, .01, .05, .1, .25, .5, .75, .9, .95, .99, 1])
q.to_csv(TAB / "ln_cuantiles_2024.csv")
for u in (50, 100, 200, 500):
    anotar(f"secciones_2024_LN_menor_{u}", int((sec[sec.AELEC == 2024].LN < u).sum()))
completas = sec[sec.sid.isin(n_elec[n_elec == 6].index)].copy()
completas["n_cap"] = completas.SV + completas.NV
vol_sec = completas.groupby("sid").agg(LN_med=("LN", "median"), volatilidad=("r", "std"),
                                       p_med=("p", "mean"), ncap_med=("n_cap", "median"))
vol_sec["ruido_binomial"] = np.sqrt(vol_sec.p_med * (1 - vol_sec.p_med) / vol_sec.ncap_med)
vol_sec["decil_LN"] = pd.qcut(vol_sec.LN_med, 10, labels=False) + 1
tam = vol_sec.groupby("decil_LN").agg(LN_mediana=("LN_med", "median"), volatilidad_mediana=("volatilidad", "median"),
                                      ruido_binomial_mediano=("ruido_binomial", "median"), secciones=("LN_med", "size"))
tam[["volatilidad_mediana", "ruido_binomial_mediano"]] *= 100
tam.round(2).to_csv(TAB / "volatilidad_por_tamano.csv")
print(tam.round(2).to_string())
fig, ax = plt.subplots(figsize=(6.4, 3.4))
ax.plot(tam.LN_mediana, tam.volatilidad_mediana, marker="o", color=CAT[0])
ax.plot(tam.LN_mediana, tam.ruido_binomial_mediano, marker="o", color=GRIS, linestyle="--")
ax.text(tam.LN_mediana.iloc[0], tam.volatilidad_mediana.iloc[0] + 0.45, "volatilidad observada (DE entre elecciones)", color=TEXTO_2, fontsize=8)
ax.text(tam.LN_mediana.iloc[0], tam.ruido_binomial_mediano.iloc[0] + 0.45, "ruido binomial esperado", color=TEXTO_2, fontsize=8)
ax.set_xscale("log")
ax.set_xticks([250, 500, 1000, 2000, 3000], ["250", "500", "1,000", "2,000", "3,000"])
ax.minorticks_off()
ax.set_xlabel("Lista nominal mediana de la sección (escala log; deciles)")
ax.set_ylabel("pp")
ax.set_ylim(0, 8.5)
ax.set_title("Volatilidad de la participación relativa según tamaño de la sección")
guardar(fig, FIG / "f03_volatilidad_tamano.png")

# ---------------------------------------------------------------- I. Cobertura del ECEG y de la cartografía
print("I. cobertura ECEG / cartografía")
eceg = pd.read_parquet(PROC / "eceg2020.parquet", columns=["sid", "POBTOT"])
geo = pd.read_parquet(PROC / "secciones_2021.parquet", columns=["sid"])
ccpc24 = sec[sec.AELEC == 2024][["sid", "LN"]]
completas_ids = n_elec[n_elec == 6].index
cob_ext = []
for nombre, ids in [("ECEG 2020", set(eceg.sid)), ("Cartografía 2021", set(geo.sid))]:
    for univ, s in [("secciones 2024", ccpc24), ("secciones en las 6 elecciones (LN 2024)", ccpc24[ccpc24.sid.isin(completas_ids)])]:
        m = s.sid.isin(ids)
        cob_ext.append({"fuente": nombre, "universo": univ, "secciones": len(s), "con_dato": int(m.sum()),
                        "pct_secciones": round(100 * m.mean(), 2), "pct_LN": round(100 * s.LN[m].sum() / s.LN.sum(), 2)})
cob_ext = pd.DataFrame(cob_ext)
cob_ext.to_csv(TAB / "cobertura_eceg_cartografia.csv", index=False)
print(cob_ext.to_string(index=False))
eceg_full = pd.read_parquet(PROC / "eceg2020.parquet")
nulos = eceg_full.isna().sum()
nulos = nulos[nulos > 0].sort_values(ascending=False)
anotar("eceg_columnas_con_nulos", int(len(nulos)))
anotar("eceg_secciones_pobtot_0", int((eceg_full.POBTOT == 0).sum()))
nulos.rename("nulos").to_csv(TAB / "eceg_nulos_por_columna.csv")
anotar("eceg_nulos_en_secciones_pobtot_menor_50", round(float(eceg_full[eceg_full.POBTOT < 50].isna().sum().sum() / max(1, nulos.sum())), 3))

(carpeta("fase2") / "calidad_resumen.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str))
print("listo")
