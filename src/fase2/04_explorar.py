# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow", "matplotlib", "geopandas", "scikit-learn"]
# ///
"""Fase 2.3 · Exploración de los Conteos Censales: ciclo nacional, distribución por sección, edad y sexo, tipo de
sección, estructura de las trayectorias, geografía y primeras pruebas de persistencia (hipótesis H2 y H3 de la fase 1).

Uso:  uv run src/fase2/04_explorar.py      (requiere 02_construir_bases.py)
Salidas: resultados/fase2/fig/f04-f12*.png, resultados/fase2/tablas/eda_*.csv, resultados/fase2/eda_resumen.json

Todo es exploratorio: no se filtran secciones ni se fijan umbrales (eso es de la fase 3). Las trayectorias se analizan
en las 62,048 secciones presentes en las seis elecciones con participación definida en todas.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import ELECCIONES, ENTIDADES, INTERMEDIAS, PROC, TIPO_ELECCION, carpeta, participacion  # noqa: E402
from graficas import CAT, CMAP_DIV, CMAP_SEQ, GRIS, TEXTO_2, guardar, plt  # noqa: E402

TAB, FIG = carpeta("fase2", "tablas"), carpeta("fase2", "fig")
R = {}


def anotar(clave, valor):
    R[clave] = valor
    print(f"  {clave}: {valor}")


sec = pd.read_parquet(PROC / "ccpc_seccion.parquet")
sec[["LN", "SV", "NV", "NS"]] = sec[["LN", "SV", "NV", "NS"]].astype("float64")
nac = sec.groupby("AELEC")[["LN", "SV", "NV", "NS"]].sum()
nac["p"] = participacion(nac)
sec["p"] = participacion(sec)
sec["r"] = sec.p - sec.AELEC.map(nac.p)
sec["mun"] = sec.EDOCVE.astype("int64") * 1000 + sec.MPIOCVE.astype("int64")

# Panel de trayectorias: secciones en las seis elecciones (r en puntos porcentuales)
P = sec.pivot_table(index="sid", columns="AELEC", values="r") * 100
n6 = sec.groupby("sid").AELEC.nunique()
en6 = n6[n6 == 6].index
T = P.loc[en6]
anotar("secciones_en_6", int(len(T)))
T = T.dropna().astype("float64")
anotar("secciones_en_6_con_p_definida_en_todas", int(len(T)))
meta = sec[sec.AELEC == 2024].set_index("sid")[["EDOCVE", "mun", "TIPOSEC", "LN"]]

xs = list(ELECCIONES)
tipo_txt = {a: ("P" if TIPO_ELECCION[a] == "presidencial" else "I") for a in xs}
etq_x = [f"{a}\n{tipo_txt[a]}" for a in xs]

# ---------------------------------------------------------------- f04 Ciclo nacional
print("f04 ciclo nacional")
cruda = 100 * nac.SV / nac.LN
fig, ax = plt.subplots(figsize=(6.4, 3.4))
ax.plot(xs, 100 * nac.p, color=CAT[0], marker="o", zorder=3)
ax.plot(xs, cruda, color=GRIS, marker="o", linestyle="--", zorder=2)
for a in xs:
    abajo = TIPO_ELECCION[a] == "intermedia"
    ax.annotate(f"{100 * nac.p[a]:.1f}", (a, 100 * nac.p[a]), textcoords="offset points", xytext=(-14 if abajo else 0, -4 if abajo else 7),
                ha="center", fontsize=8, color=TEXTO_2)
ax.text(2024.3, 100 * nac.p[2024], "SV / (SV+NV)", va="center", fontsize=8, color=TEXTO_2)
ax.text(2024.3, cruda[2024], "SV / LN", va="center", fontsize=8, color=TEXTO_2)
for a in INTERMEDIAS:
    ax.axvspan(a - 1.2, a + 1.2, color="#f0efec", zorder=0)
ax.set_xticks(xs, etq_x)
ax.set_xlim(2008, 2026.8)
ax.set_ylim(38, 68)
ax.set_ylabel("Participación (%)")
ax.set_title("Participación nacional: el tipo de elección marca el ciclo (I = intermedia, P = presidencial)")
guardar(fig, FIG / "f04_ciclo_nacional.png")

# ---------------------------------------------------------------- f05 Distribución por sección
print("f05 distribución")
cuant = sec.groupby("AELEC").p.quantile([.05, .25, .5, .75, .95]).unstack() * 100
cuant.round(2).to_csv(TAB / "eda_cuantiles_participacion.csv")
cuant_r = sec.groupby("AELEC").r.quantile([.05, .25, .5, .75, .95]).unstack() * 100
anotar("rango_iqr_participacion_pp", {int(a): round(float(cuant.loc[a, .75] - cuant.loc[a, .25]), 1) for a in xs})
fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.4), sharey=False)
for ax, c, titulo in [(axs[0], cuant, "Participación por sección (%)"), (axs[1], cuant_r, "Relativa al nacional (pp)")]:
    ax.fill_between(xs, c[.05], c[.95], color=CAT[0], alpha=0.15, linewidth=0)
    ax.fill_between(xs, c[.25], c[.75], color=CAT[0], alpha=0.35, linewidth=0)
    ax.plot(xs, c[.5], color=CAT[0], marker="o")
    ax.set_xticks(xs, etq_x)
    ax.set_title(titulo)
axs[0].text(2024.4, cuant.loc[2024, .95], "p95", fontsize=8, color=TEXTO_2, va="center")
axs[0].text(2024.4, cuant.loc[2024, .75], "p75", fontsize=8, color=TEXTO_2, va="center")
axs[0].text(2024.4, cuant.loc[2024, .5], "mediana", fontsize=8, color=TEXTO_2, va="center")
axs[0].text(2024.4, cuant.loc[2024, .25], "p25", fontsize=8, color=TEXTO_2, va="center")
axs[0].text(2024.4, cuant.loc[2024, .05], "p5", fontsize=8, color=TEXTO_2, va="center")
axs[1].axhline(0, color=GRIS, linewidth=1)
fig.suptitle("Distribución entre secciones: la dispersión es estable; el nivel sube y baja con el ciclo", x=0.01, ha="left",
             fontsize=10.5, fontweight="bold")
fig.tight_layout()
guardar(fig, FIG / "f05_distribucion_secciones.png")

# ---------------------------------------------------------------- f06 Edad × sexo (nacional, edad simple)
print("f06 edad y sexo")
ne = pd.read_parquet(PROC / "ccpc_nacional_edad.parquet")
ne = ne[ne.SEXO.isin([0, 1]) & ne.EDAD.between(18, 90)].groupby(["AELEC", "SEXO", "EDAD"])[["SV", "NV"]].sum()
ne["p"] = 100 * participacion(ne)
ne = ne.p.unstack("SEXO")
ne.columns = ["hombres", "mujeres"]
ne.round(2).to_csv(TAB / "eda_edad_sexo_nacional.csv")
fig, axs = plt.subplots(2, 3, figsize=(10, 5.6), sharex=True, sharey=True)
for ax, a in zip(axs.flat, xs):
    d = ne.loc[a]
    ax.plot(d.index, d.hombres, color=CAT[0], linewidth=1.8)
    ax.plot(d.index, d.mujeres, color=CAT[1], linewidth=1.8)
    ax.set_title(f"{a} · {TIPO_ELECCION[a]}", fontsize=9.5)
for ax in axs[1]:
    ax.set_xlabel("Edad")
for ax in axs[:, 0]:
    ax.set_ylabel("Participación (%)")
fig.suptitle("Participación por edad simple y sexo", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
fig.legend(["hombres", "mujeres"], loc="upper right", ncol=2, fontsize=8.5, bbox_to_anchor=(0.99, 1.0))
fig.tight_layout()
guardar(fig, FIG / "f06_edad_sexo.png")
# Discontinuidad: mayor salto de un año al siguiente entre 25 y 35 años (por sexo y elección)
salto = {int(a): {sx: {"edad": int(ne.loc[a, sx].diff().loc[25:35].idxmax()), "pp": round(float(ne.loc[a, sx].diff().loc[25:35].max()), 1)}
                  for sx in ("hombres", "mujeres")} for a in xs}
anotar("salto_edad_25_35", salto)
resumen_edad = {}
for a in xs:
    d = ne.loc[a]
    tot = d.mean(axis=1)
    resumen_edad[int(a)] = {"min_edad": int(tot.loc[18:40].idxmin()), "min_p": round(float(tot.loc[18:40].min()), 1),
                            "max_edad": int(tot.idxmax()), "max_p": round(float(tot.max()), 1),
                            "brecha_M_H_25_34": round(float((d.mujeres - d.hombres).loc[25:34].mean()), 1),
                            "p_18": round(float(tot.loc[18]), 1), "p_19_20": round(float(tot.loc[19:20].mean()), 1)}
anotar("edad", resumen_edad)

# ---------------------------------------------------------------- f07 Tipo de sección
print("f07 tipo de sección")
tip = sec.groupby(["AELEC", "TIPOSEC"], observed=True)[["SV", "NV"]].sum()
tip = (100 * participacion(tip)).unstack()
tip.round(2).to_csv(TAB / "eda_tipo_seccion.csv")
fig, ax = plt.subplots(figsize=(6.4, 3.4))
nombres = {"U": "urbana", "M": "mixta", "R": "rural"}
for c, t in zip(CAT, ["U", "M", "R"]):
    ax.plot(xs, tip[t], color=c, marker="o")
    ax.text(2024.4, tip.loc[2024, t] + {"R": 0.7, "U": -0.7, "M": 0}[t], nombres[t], color=TEXTO_2, fontsize=8, va="center")
ax.set_xticks(xs, etq_x)
ax.set_xlim(2008, 2026.5)
ax.set_ylabel("Participación (%)")
ax.set_title("Participación por tipo de sección")
guardar(fig, FIG / "f07_tipo_seccion.png")
anotar("rural_menos_urbana_pp", {int(a): round(float(tip.loc[a, "R"] - tip.loc[a, "U"]), 1) for a in xs})

# ---------------------------------------------------------------- f08 Estructura de las trayectorias
print("f08 estructura")
from sklearn.decomposition import PCA  # noqa: E402

C = T.corr()
C.round(3).to_csv(TAB / "eda_correlacion_trayectorias.csv")
pca = PCA().fit(T.values)
var = pca.explained_variance_ratio_
cargas = pd.DataFrame(pca.components_[:3].T, index=xs, columns=["CP1", "CP2", "CP3"])
signo = np.sign(cargas.sum())  # orientación: CP1 positiva = más participación
cargas = cargas * signo
cargas.round(3).to_csv(TAB / "eda_pca_cargas.csv")
anotar("pca_varianza_explicada", [round(float(v), 3) for v in var])
nivel = T.mean(axis=1)
forma = T.sub(nivel, axis=0)
anotar("varianza_total_nivel_vs_forma", {"nivel": round(float(6 * nivel.var() / T.var().sum()), 3),
                                          "forma": round(float(forma.var().sum() / T.var().sum()), 3)})
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw={"width_ratios": [1, 1.25]})
im = axs[0].imshow(C.values, cmap=CMAP_SEQ, vmin=0, vmax=1)
axs[0].set_xticks(range(6), etq_x, fontsize=8)
axs[0].set_yticks(range(6), [f"{a} {tipo_txt[a]}" for a in xs], fontsize=8)
axs[0].grid(False)
for i in range(6):
    for j in range(6):
        axs[0].text(j, i, f"{C.values[i, j]:.2f}", ha="center", va="center", fontsize=7.5, color="white" if C.values[i, j] > 0.6 else TEXTO_2)
axs[0].set_title("Correlación de la participación relativa")
for k, (c, nom) in enumerate(zip(CAT, ["CP1", "CP2", "CP3"])):
    axs[1].plot(xs, cargas[nom], color=c, marker="o")
    axs[1].text(2024.4, cargas.loc[2024, nom], f"{nom} ({100 * var[k]:.0f}%)", color=TEXTO_2, fontsize=8, va="center")
axs[1].axhline(0, color=GRIS, linewidth=1)
axs[1].set_xticks(xs, etq_x, fontsize=8)
axs[1].set_xlim(2008, 2027.5)
axs[1].set_title("Componentes principales de la trayectoria (cargas)")
fig.tight_layout()
guardar(fig, FIG / "f08_estructura_trayectorias.png")

# ---------------------------------------------------------------- f09 Trayectorias de ejemplo con el mismo nivel
print("f09 ejemplos")
scores = pd.DataFrame(pca.transform(T.values)[:, :3] * signo.values, index=T.index, columns=["CP1", "CP2", "CP3"])
grandes = meta.LN.reindex(T.index) >= 800              # ejemplos legibles: secciones con al menos 800 electores
cerca0 = T.index[(nivel.abs() < 1) & grandes]
vaiven = T[[2012, 2018, 2024]].mean(axis=1) - T[[2009, 2015, 2021]].mean(axis=1)
tendencia = pd.Series(np.polyfit(np.arange(6), T.T.values, 1)[0], index=T.index)  # pp por elección


def en_percentil(serie, q):
    """Sección cuyo valor está más cerca del percentil q (evita mostrar casos extremos o anómalos)."""
    obj = serie.quantile(q)
    return (serie - obj).abs().idxmin()


ejemplos = {"estable": forma.loc[cerca0].abs().max(axis=1).idxmin(),
            "vaivén alto": en_percentil(vaiven.loc[cerca0], 0.97),
            "mejora": en_percentil(tendencia.loc[cerca0], 0.97),
            "deterioro": en_percentil(tendencia.loc[cerca0], 0.03)}
anotar("pct_seccion_eleccion_abs_r_mayor_30pp", round(float(100 * (T.abs() > 30).mean().mean()), 3))
fig, axs = plt.subplots(1, 4, figsize=(11, 2.9), sharey=True)
for ax, (nom, s) in zip(axs, ejemplos.items()):
    ax.axhline(0, color=GRIS, linewidth=1)
    ax.plot(xs, T.loc[s], color=CAT[0], marker="o")
    m = meta.loc[s]
    ax.set_title(f"{nom}: sección {s % 10000}, {ENTIDADES[int(m.EDOCVE)]}", fontsize=8.5)
    ax.set_xticks(xs, [str(a)[2:] + tipo_txt[a] for a in xs], fontsize=7.5)
    ax.text(2009, ax.get_ylim()[0] if False else -1, "", fontsize=1)
axs[0].set_ylabel("pp respecto al nacional")
fig.suptitle("Cuatro secciones con nivel medio ≈ nacional (|nivel| < 1 pp) y trayectorias distintas", x=0.01, ha="left",
             fontsize=10.5, fontweight="bold")
fig.tight_layout()
guardar(fig, FIG / "f09_trayectorias_ejemplo.png")
pd.DataFrame({k: T.loc[v] for k, v in ejemplos.items()}).T.assign(sid=list(ejemplos.values())).round(2).to_csv(TAB / "eda_trayectorias_ejemplo.csv")

# ---------------------------------------------------------------- f10 Geografía: mapa municipal y descomposición
print("f10 geografía")
import geopandas as gpd  # noqa: E402

ln_w = sec[sec.sid.isin(T.index)].groupby(["mun", "AELEC"])[["SV", "NV"]].sum()
ln_w["r"] = 100 * (participacion(ln_w) - ln_w.index.get_level_values("AELEC").map(nac.p).values)
mun_r = ln_w.r.unstack().mean(axis=1).rename("r_media")
muni = gpd.read_parquet(PROC / "municipios_2021.parquet")
muni["mun"] = muni.ENTIDAD.astype("int64") * 1000 + muni.MUNICIPIO.astype("int64")
muni = muni.merge(mun_r, left_on="mun", right_index=True, how="left")
anotar("municipios_mapa_con_dato", f"{int(muni.r_media.notna().sum())} de {len(muni)}")
fig, ax = plt.subplots(figsize=(9, 6))
lim = 15
muni.plot(column="r_media", cmap=CMAP_DIV, vmin=-lim, vmax=lim, ax=ax, linewidth=0.05, edgecolor="#fcfcfb",
          missing_kwds={"color": "#fcfcfb", "edgecolor": "#8a8984", "hatch": "////", "linewidth": 0.1})
ax.set_axis_off()
sm = plt.cm.ScalarMappable(cmap=CMAP_DIV, norm=plt.Normalize(-lim, lim))
cb = fig.colorbar(sm, ax=ax, shrink=0.55, orientation="horizontal", pad=0.02)
cb.set_label("Participación relativa media 2009–2024 (pp; azul = por encima del nacional)")
ax.set_title("Participación relativa media 2009–2024 por municipio (rayado = sin dato)")
guardar(fig, FIG / "f10_mapa_municipal.png")

# Qué parte de la varianza entre secciones se explica por la entidad y por el municipio
def r2_grupo(y, g):
    return float(1 - ((y - y.groupby(g).transform("mean")) ** 2).sum() / ((y - y.mean()) ** 2).sum())


desc = []
m = meta.reindex(T.index)
for nombre, y in [("nivel (media 6 elecciones)", nivel), ("vaivén P−I medio", T[[2012, 2018, 2024]].mean(axis=1) - T[[2009, 2015, 2021]].mean(axis=1))] + \
        [(f"r {a}", T[a]) for a in xs]:
    desc.append({"variable": nombre, "R2_entidad": round(r2_grupo(y, m.EDOCVE), 3), "R2_municipio": round(r2_grupo(y, m.mun), 3)})
desc = pd.DataFrame(desc)
desc.to_csv(TAB / "eda_varianza_geografica.csv", index=False)
print(desc.to_string(index=False))

# ---------------------------------------------------------------- f11 Persistencia preliminar (H2, H3 y referencias)
print("f11 persistencia")
se = pd.read_parquet(PROC / "ccpc_seccion_sexo_edad.parquet")
se = se[se.sid.isin(T.index) & se.SEXO.isin([0, 1])]
se["grupo"] = se.BANDA.astype(str).map({"18-24": "joven", "25-34": "joven", "55-64": "mayor", "65-74": "mayor"})
g = se.dropna(subset=["grupo"]).groupby(["sid", "AELEC", "grupo"])[["SV", "NV"]].sum()
g["p"] = participacion(g)
gp = g.p.unstack("grupo")
gn = g.groupby(["AELEC", "grupo"])[["SV", "NV"]].sum().pipe(participacion).unstack()
brecha_j = ((gp.joven - gp.mayor) - (gp.index.get_level_values("AELEC").map(gn.joven - gn.mayor).values)).unstack() * 100
gs = se[se.BANDA.astype(str).isin(["18-24", "25-34", "35-44", "45-54"])].groupby(["sid", "AELEC", "SEXO"])[["SV", "NV"]].sum()
gs["p"] = participacion(gs)
gsp = gs.p.unstack("SEXO")
gsn = gs.groupby(["AELEC", "SEXO"])[["SV", "NV"]].sum().pipe(participacion).unstack()
brecha_g = ((gsp[1] - gsp[0]) - gsp.index.get_level_values("AELEC").map(gsn[1] - gsn[0]).values).unstack() * 100

A, B = [2009, 2012, 2015], [2018, 2021, 2024]
pruebas = {
    "nivel (media 2009–15 vs 2018–24)": (T[A].mean(axis=1), T[B].mean(axis=1)),
    "H2 vaivén 2009→2012 vs 2021→2024": (T[2012] - T[2009], T[2024] - T[2021]),
    "H2 vaivén 2009→2012 vs 2015→2018": (T[2012] - T[2009], T[2018] - T[2015]),
    "H2 vaivén 2015→2018 vs 2021→2024": (T[2018] - T[2015], T[2024] - T[2021]),
    "H3 brecha joven (18–34 − 55–74)": (brecha_j[A].mean(axis=1), brecha_j[B].mean(axis=1)),
    "brecha de género 18–54 (M − H)": (brecha_g[A].mean(axis=1), brecha_g[B].mean(axis=1)),
}
filas = []
for nom, (a, b) in pruebas.items():
    d = pd.concat([a, b], axis=1).dropna()
    grandes = meta.LN.reindex(d.index) >= 1000
    filas.append({"rasgo": nom, "r_todas": round(float(d.corr().iloc[0, 1]), 3), "n": len(d),
                  "r_LN_1000_o_mas": round(float(d[grandes].corr().iloc[0, 1]), 3), "n_LN_1000": int(grandes.sum())})
pers = pd.DataFrame(filas)
pers.to_csv(TAB / "eda_persistencia_preliminar.csv", index=False)
print(pers.to_string(index=False))
fig, ax = plt.subplots(figsize=(7.4, 3.3))
y = np.arange(len(pers))[::-1]
b1 = ax.barh(y + 0.18, pers.r_todas, height=0.34, color=CAT[0], label="todas las secciones")
b2 = ax.barh(y - 0.18, pers.r_LN_1000_o_mas, height=0.34, color=CAT[1], label="secciones con LN ≥ 1,000")
for yy, v1, v2 in zip(y, pers.r_todas, pers.r_LN_1000_o_mas):
    ax.text(v1 + 0.01, yy + 0.18, f"{v1:.2f}", va="center", fontsize=7.5, color=TEXTO_2)
    ax.text(v2 + 0.01, yy - 0.18, f"{v2:.2f}", va="center", fontsize=7.5, color=TEXTO_2)
ax.axvline(0.5, color=GRIS, linestyle="--", linewidth=1)
ax.text(0.505, y.max() + 0.55, "umbral H2/H3 (0.5)", fontsize=7.5, color=TEXTO_2)
ax.set_yticks(y, pers.rasgo, fontsize=8)
ax.set_xlim(min(0, pers[["r_todas", "r_LN_1000_o_mas"]].min().min() - 0.05), 1)
ax.set_xlabel("Correlación entre ventanas sin elecciones en común")
ax.legend(handles=[b1, b2], loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=8)
ax.set_title("¿Qué rasgos de la sección persisten entre periodos?")
guardar(fig, FIG / "f11_persistencia.png")

# ---------------------------------------------------------------- f12 H5 preliminar: deterioro frente a regresión a la media
print("f12 regresión a la media")
a_, b_ = T[A].mean(axis=1), T[B].mean(axis=1)
pend, inter = np.polyfit(a_, b_, 1)
resid = b_ - (inter + pend * a_)
anotar("H5_pendiente_B_sobre_A", round(float(pend), 3))
anotar("H5_resid_DE_pp", round(float(resid.std()), 2))
anotar("H5_pct_secciones_resid_menor_menos5pp", round(float(100 * (resid < -5).mean()), 2))
anotar("H5_R2_municipio_del_residuo", round(r2_grupo(resid, m.mun), 3))
anotar("H5_R2_entidad_del_residuo", round(r2_grupo(resid, m.EDOCVE), 3))
fig, ax = plt.subplots(figsize=(5.2, 4.4))
hb = ax.hexbin(a_, b_, gridsize=70, cmap=CMAP_SEQ, mincnt=1, bins="log", extent=(-30, 30, -30, 30))
lim = np.array([-30, 30])
ax.plot(lim, lim, color=GRIS, linestyle="--", linewidth=1, label="sin cambio (y = x)")
ax.plot(lim, inter + pend * lim, color=CAT[1], linewidth=1.8, label=f"ajuste lineal (pendiente {pend:.2f})")
ax.legend(loc="upper left", fontsize=8)
ax.set_xlim(lim)
ax.set_ylim(lim)
ax.set_xlabel("Nivel relativo 2009–2015 (pp)")
ax.set_ylabel("Nivel relativo 2018–2024 (pp)")
ax.set_title("Regresión a la media del nivel")
fig.colorbar(hb, ax=ax, shrink=0.7, label="secciones (log)")
guardar(fig, FIG / "f12_regresion_media.png")

(carpeta("fase2") / "eda_resumen.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str))
print("listo")
