# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow", "openpyxl", "scikit-learn", "matplotlib"]
# ///
"""Fase 2.5 · Comparación del Índice de Rezago Social (IRS) y la Medición de la pobreza municipal del CONEVAL,
con los criterios C1-C5 fijados en la fase 1 (docs/fase1_comprension_negocio.md §4.4).

  C1 Cobertura: % de municipios y de lista nominal 2024 (secciones con las seis elecciones) con dato.
  C2 Comparabilidad temporal: notas metodológicas (documentado en el reporte) y estabilidad 2010→2020.
  C3 Valor añadido sobre el ECEG: R² con validación cruzada agrupada por entidad al explicar cada indicador del
     CONEVAL 2020 con indicadores del ECEG 2020 agregados al municipio. R² alto = redundante con el ECEG.
  C4/C5 Granularidad e interpretabilidad: cualitativos (documentados en el reporte).
Para no adelantar el modelado, aquí NO se usa la relación de ninguna fuente con la participación.

Uso:  uv run src/fase2/05_comparar_coneval.py      (requiere 02_construir_bases.py)
Salidas: data/processed/coneval_irs.parquet, coneval_pobreza.parquet, cruce_municipios_ine_inegi.csv;
         resultados/fase2/tablas/coneval_*.csv, resultados/fase2/fig/f13_coneval_valor_anadido.png
"""
import difflib
import io
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import PROC, RAW, carpeta  # noqa: E402
from graficas import CAT, TEXTO_2, guardar, plt  # noqa: E402

TAB, FIG = carpeta("fase2", "tablas"), carpeta("fase2", "fig")
R = {}


def anotar(clave, valor):
    R[clave] = valor
    print(f"  {clave}: {valor}")


# ---------------------------------------------------------------- Lectura del IRS (2010, 2015, 2020)
IRS_IND = ["analfabeta_15", "no_asiste_6_14", "basica_incompleta_15", "sin_derechohabiencia", "piso_tierra",
           "sin_excusado", "sin_agua_entubada", "sin_drenaje", "sin_electricidad", "sin_lavadora", "sin_refrigerador"]


def leer_irs():
    z = zipfile.ZipFile(RAW / "coneval" / "IRS_ent_mun_2000_2020.zip")
    partes = []
    for anio in (2010, 2015, 2020):
        d = pd.read_excel(io.BytesIO(z.read(f"IRS_entidades_mpios_{anio}.xlsx")), sheet_name="Municipios", header=None, dtype=str)
        d = d[d[2].fillna("").str.strip().str.fullmatch(r"\d{4,5}")]          # renglones de municipio (clave de 5 dígitos)
        d = d.iloc[:, :19]
        d.columns = ["ent", "nom_ent", "mun_inegi", "nom_mun", "poblacion"] + IRS_IND + ["irs", "grado", "lugar"]
        d["mun_inegi"] = d.mun_inegi.astype(int)
        for c in ["poblacion"] + IRS_IND + ["irs"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d["anio"] = anio
        partes.append(d.drop(columns=["lugar"]))
    return pd.concat(partes, ignore_index=True)


# ---------------------------------------------------------------- Lectura de la medición de pobreza (2010, 2015, 2020)
def norm_txt(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def leer_pobreza():
    z = zipfile.ZipFile(RAW / "coneval" / "pobreza_municipal_2010_2020.zip")
    d = pd.read_excel(io.BytesIO(z.read(z.namelist()[0])), sheet_name="Concentrado municipal", header=None, dtype=str)
    grupo = d.iloc[4].ffill()
    sub = d.iloc[5]
    cols = []
    for j in range(d.shape[1]):
        g, s = grupo[j], sub[j]
        if j <= 4 or pd.isna(s):
            cols.append(norm_txt(g) if pd.notna(g) else f"c{j}")
        else:
            cols.append(f"{norm_txt(g)}|{norm_txt(s)}")
    d.columns = cols
    d = d[d.clave_de_municipio.fillna("").str.strip().str.fullmatch(r"\d{4,5}")].copy()
    d["mun_inegi"] = d.clave_de_municipio.astype(int)
    largo = []
    for anio in (2010, 2015, 2020):
        sel = {c: c.split("|")[0] for c in d.columns if c.endswith(f"|porcentaje_{anio}")}
        x = d[["mun_inegi", "entidad_federativa", "municipio"] + list(sel)].rename(columns=sel)
        for c in sel.values():
            x[c] = pd.to_numeric(x[c], errors="coerce")     # 'n.a.' → NaN (municipio inexistente ese año)
        x["anio"] = anio
        largo.append(x)
    return pd.concat(largo, ignore_index=True)


irs = leer_irs()
pob = leer_pobreza()
irs.to_parquet(PROC / "coneval_irs.parquet", index=False)
pob.to_parquet(PROC / "coneval_pobreza.parquet", index=False)
IND_POB = [c for c in pob.columns if c not in ("mun_inegi", "entidad_federativa", "municipio", "anio")]
anotar("irs_municipios_por_anio", irs.groupby("anio").irs.count().to_dict())
anotar("pobreza_municipios_por_anio", pob.groupby("anio").pobreza.count().to_dict())
anotar("pobreza_indicadores", IND_POB)

# ---------------------------------------------------------------- Cruce de municipios INE → INEGI (por nombre dentro de la entidad)
def norm_mun(s):
    s = unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode()
    s = re.sub(r"\b(de|del|la|las|los|el|y|heroica|villa|ciudad|h)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


sec = pd.read_parquet(PROC / "ccpc_seccion.parquet", columns=["sid", "AELEC", "EDOCVE", "MPIOCVE", "MPIONOM", "LN"])
sec["mun"] = sec.EDOCVE.astype("int64") * 1000 + sec.MPIOCVE.astype("int64")
nombres_ine = sec.sort_values("AELEC").groupby("mun").agg(ent=("EDOCVE", "last"), nom_ine=("MPIONOM", "last")).reset_index()
# Alias INEGI: todas las variantes de nombre de cada clave (ambas fuentes, todos los años; hay municipios renombrados)
alias = pd.concat([irs[["mun_inegi", "nom_mun"]].rename(columns={"nom_mun": "nom"}),
                   pob[["mun_inegi", "municipio"]].rename(columns={"municipio": "nom"})]).dropna()
alias["nom"] = alias.nom.str.replace(r"\s*-\s*Dto\.?\s*\d+\s*-?", "", regex=True)   # 'San Juan Mixtepec -Dto. 26 -' → nombre base
alias["n"] = alias.nom.map(norm_mun)
alias["ent"] = alias.mun_inegi // 1000
alias = alias.drop_duplicates(["mun_inegi", "n"])
nombre_inegi = pd.concat([irs[irs.anio == 2020][["mun_inegi", "nom_mun"]].rename(columns={"nom_mun": "nom"}),
                          irs[["mun_inegi", "nom_mun"]].rename(columns={"nom_mun": "nom"})]).drop_duplicates("mun_inegi")
nombres_ine["n"] = nombres_ine.nom_ine.map(norm_mun)
asign = {}
for ent, g in nombres_ine.groupby("ent"):
    pool = alias[alias.ent == ent]
    por_nombre = pool.groupby("n").mun_inegi.apply(lambda s: sorted(set(s))).to_dict()
    # 1) nombre exacto; si el nombre se repite en la entidad (p. ej. dos 'San Juan Mixtepec' en Oaxaca) se emparejan
    #    las claves INE e INEGI en orden, uno a uno
    for n, gg in g.groupby("n"):
        if n in por_nombre:
            ine_ord, inegi_ord = sorted(gg.mun), por_nombre[n]
            if len(ine_ord) == len(inegi_ord):
                asign.update({a: (b, "exacto") for a, b in zip(ine_ord, inegi_ord)})
            else:
                for a in ine_ord:
                    asign[a] = (min(inegi_ord, key=lambda b: abs(b % 1000 - a % 1000)), "exacto_ambiguo")
    # 2) aproximado (errores de captura) y 3) un nombre contenido en el otro (nombres largos/cortos)
    for _, r in g[~g.mun.isin(asign)].iterrows():
        cerca = difflib.get_close_matches(r.n, list(por_nombre), 1, 0.85)
        if cerca:
            asign[r.mun] = (min(por_nombre[cerca[0]], key=lambda b: abs(b % 1000 - r.mun % 1000)), "aproximado")
            continue
        cont = sorted((k for k in por_nombre if len(k) >= 5 and (k in r.n or r.n in k)), key=len, reverse=True)
        if cont and (len(cont) == 1 or len(cont[0]) > len(cont[1])):   # el alias contenido más largo, si no hay empate
            asign[r.mun] = (por_nombre[cont[0]][0], "contenido")
# 4) Municipios creados después de 2020 (sin dato del CONEVAL): municipio de origen = el que tenían sus secciones antes
sin = [m for m in nombres_ine.mun if m not in asign]
for m in sin:
    ids = sec[(sec.mun == m)].sid.unique()
    antes = sec[sec.sid.isin(ids) & (sec.mun != m)].sort_values("AELEC")
    if len(antes):
        origen = antes[antes.AELEC == antes.AELEC.max()].mun.mode().iloc[0]
        if origen in asign:
            asign[m] = (asign[origen][0], "municipio_origen")
cruce = nombres_ine[["mun", "nom_ine"]].rename(columns={"mun": "mun_ine"})
cruce["mun_inegi"] = cruce.mun_ine.map(lambda m: asign.get(m, (np.nan, ""))[0])
cruce["metodo"] = cruce.mun_ine.map(lambda m: asign.get(m, (np.nan, "sin_cruce"))[1])
cruce = cruce.merge(nombre_inegi.rename(columns={"nom": "nom_inegi"}), on="mun_inegi", how="left")
dup = cruce[cruce.metodo != "municipio_origen"].mun_inegi.dropna().duplicated(keep=False)
anotar("claves_inegi_asignadas_a_mas_de_un_municipio_ine", int(dup.sum()))
cruce.to_csv(PROC / "cruce_municipios_ine_inegi.csv", index=False)
cruce[cruce.metodo != "exacto"].to_csv(TAB / "coneval_cruce_no_exactos.csv", index=False)
anotar("cruce_metodo", cruce.metodo.value_counts().to_dict())
anotar("claves_ine_igual_inegi_pct", round(float(100 * (cruce.mun_ine == cruce.mun_inegi).mean()), 1))

# ---------------------------------------------------------------- C1 Cobertura
n6 = sec.groupby("sid").AELEC.nunique()
s24 = sec[(sec.AELEC == 2024) & sec.sid.isin(n6[n6 == 6].index)][["sid", "mun", "LN"]]
s24 = s24.merge(cruce[["mun_ine", "mun_inegi"]], left_on="mun", right_on="mun_ine", how="left")
c1 = []
for fuente, df, var in [("IRS", irs, "irs"), ("Pobreza", pob, "pobreza")]:
    for anio in (2010, 2015, 2020):
        con = set(df[(df.anio == anio) & df[var].notna()].mun_inegi)
        m = s24.mun_inegi.isin(con)
        muns = s24.drop_duplicates("mun")
        c1.append({"fuente": fuente, "anio": anio, "municipios_ine": len(muns), "municipios_con_dato": int(muns.mun_inegi.isin(con).sum()),
                   "pct_municipios": round(100 * muns.mun_inegi.isin(con).mean(), 2), "pct_LN_2024": round(100 * s24.LN[m].sum() / s24.LN.sum(), 2)})
c1 = pd.DataFrame(c1)
c1.to_csv(TAB / "coneval_c1_cobertura.csv", index=False)
print(c1.to_string(index=False))

# ---------------------------------------------------------------- C2 Estabilidad 2010 → 2020 (complementa las notas metodológicas)
c2 = []
for fuente, df, var in [("IRS (índice)", irs, "irs"), ("Pobreza (%)", pob, "pobreza"), ("Pobreza extrema (%)", pob, "pobreza_extrema")]:
    w = df.pivot_table(index="mun_inegi", columns="anio", values=var)
    c2.append({"indicador": fuente, "r_2010_2015": round(w[[2010, 2015]].corr().iloc[0, 1], 3),
               "r_2015_2020": round(w[[2015, 2020]].corr().iloc[0, 1], 3), "r_2010_2020": round(w[[2010, 2020]].corr().iloc[0, 1], 3),
               "media_2010": round(w[2010].mean(), 2), "media_2020": round(w[2020].mean(), 2)})
c2 = pd.DataFrame(c2)
c2.to_csv(TAB / "coneval_c2_estabilidad.csv", index=False)
print(c2.to_string(index=False))

# ---------------------------------------------------------------- C3 Valor añadido sobre el ECEG
e = pd.read_parquet(PROC / "eceg2020.parquet")
geo = pd.read_parquet(PROC / "secciones_2021.parquet", columns=["sid", "ENTIDAD", "MUNICIPIO"])
e = e.merge(geo, on="sid", how="left")
e["mun"] = e.ENTIDAD_y.astype("int64") * 1000 + e.MUNICIPIO.astype("int64") if "ENTIDAD_y" in e else e.ENTIDAD.astype("int64") * 1000 + e.MUNICIPIO.astype("int64")
e["GRAPROES_x_P15"] = e.GRAPROES * e.P_15YMAS
cols_suma = ["POBTOT", "P_3YMAS", "P_5YMAS", "P_12YMAS", "P_15YMAS", "P15YM_AN", "P15YM_SE", "P3YM_HLI", "PNACOE", "PRESOE15",
             "PSINDER", "PDER_IMSS", "PDER_SEGP", "VIVPAR_HAB", "VPH_PISOTI", "VPH_NODREN", "VPH_AGUAFV", "VPH_S_ELEC", "VPH_REFRI",
             "VPH_LAVAD", "VPH_INTER", "VPH_PC", "VPH_CEL", "VPH_AUTOM", "VPH_1DOR", "OCUPVIVPAR", "PEA", "PDESOCUP", "P_60YMAS",
             "POB0_14", "TOTHOG", "HOGJEF_F", "POB_AFRO", "PCON_DISC", "GRAPROES_x_P15"]
m = e.groupby("mun")[cols_suma].sum(min_count=1)
X = pd.DataFrame({
    "escolaridad_promedio": m.GRAPROES_x_P15 / m.P_15YMAS, "pct_analfabeta": m.P15YM_AN / m.P_15YMAS, "pct_sin_escolaridad": m.P15YM_SE / m.P_15YMAS,
    "pct_lengua_indigena": m.P3YM_HLI / m.P_3YMAS, "pct_nacio_otra_entidad": m.PNACOE / m.POBTOT, "pct_otra_entidad_2015": m.PRESOE15 / m.P_5YMAS,
    "pct_sin_derechohabiencia": m.PSINDER / m.POBTOT, "pct_imss": m.PDER_IMSS / m.POBTOT, "pct_seguro_popular": m.PDER_SEGP / m.POBTOT,
    "pct_piso_tierra": m.VPH_PISOTI / m.VIVPAR_HAB, "pct_sin_drenaje": m.VPH_NODREN / m.VIVPAR_HAB, "pct_agua_fuera": m.VPH_AGUAFV / m.VIVPAR_HAB,
    "pct_sin_electricidad": m.VPH_S_ELEC / m.VIVPAR_HAB, "pct_refrigerador": m.VPH_REFRI / m.VIVPAR_HAB, "pct_lavadora": m.VPH_LAVAD / m.VIVPAR_HAB,
    "pct_internet": m.VPH_INTER / m.VIVPAR_HAB, "pct_computadora": m.VPH_PC / m.VIVPAR_HAB, "pct_celular": m.VPH_CEL / m.VIVPAR_HAB,
    "pct_automovil": m.VPH_AUTOM / m.VIVPAR_HAB, "pct_un_dormitorio": m.VPH_1DOR / m.VIVPAR_HAB, "ocupantes_por_vivienda": m.OCUPVIVPAR / m.VIVPAR_HAB,
    "tasa_pea": m.PEA / m.P_12YMAS, "pct_desocupada": m.PDESOCUP / m.PEA, "pct_60_mas": m.P_60YMAS / m.POBTOT, "pct_0_14": m.POB0_14 / m.POBTOT,
    "pct_jefatura_femenina": m.HOGJEF_F / m.TOTHOG, "pct_afro": m.POB_AFRO / m.POBTOT, "pct_discapacidad": m.PCON_DISC / m.POBTOT,
    "log_poblacion": np.log1p(m.POBTOT),
}).replace([np.inf, -np.inf], np.nan)
X.to_csv(TAB / "coneval_eceg_municipal_features.csv")
X = X.join(cruce.set_index("mun_ine").mun_inegi)

from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import RidgeCV  # noqa: E402
from sklearn.model_selection import GroupKFold, cross_val_predict  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

objetivos = {"IRS · índice": ("irs", irs)}
objetivos.update({f"IRS · {c}": (c, irs) for c in ["analfabeta_15", "sin_derechohabiencia", "piso_tierra", "sin_refrigerador"]})
etiqueta_pob = {"pobreza": "pobreza", "pobreza_extrema": "pobreza extrema", "vulnerables_por_ingreso": "vulnerables por ingreso",
                "poblacion_con_ingreso_inferior_a_la_linea_de_pobreza_por_ingresos": "ingreso < línea de pobreza",
                "poblacion_con_ingreso_inferior_a_la_linea_de_pobreza_extrema_por_ingresos": "ingreso < línea de pobreza extrema",
                "carencia_por_acceso_a_la_seguridad_social": "carencia seguridad social",
                "carencia_por_acceso_a_la_alimentacion": "carencia alimentación",
                "carencia_por_acceso_a_los_servicios_basicos_en_la_vivienda": "carencia servicios básicos",
                "rezago_educativo": "rezago educativo", "carencia_por_calidad_y_espacios_de_la_vivienda": "carencia vivienda"}
for c, et in etiqueta_pob.items():
    if c in IND_POB:
        objetivos[f"Pobreza · {et}"] = (c, pob)
faltan = [c for c in etiqueta_pob if c not in IND_POB]
anotar("indicadores_pobreza_no_encontrados", faltan)

cv = GroupKFold(n_splits=8)
filas = []
for nombre, (var, df) in objetivos.items():
    y = df[df.anio == 2020].drop_duplicates("mun_inegi").set_index("mun_inegi")[var]
    d = X.dropna(subset=["mun_inegi"]).drop_duplicates("mun_inegi").set_index("mun_inegi").join(y.rename("y"), how="inner").dropna(subset=["y"])
    Xm, ym, grupos = d.drop(columns="y"), d.y.values, (d.index // 1000).values
    res = {"objetivo": nombre, "fuente": nombre.split(" · ")[0], "municipios": len(d)}
    for etiqueta, modelo in [("ridge", make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 13)))),
                             ("boosting", HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0))]:
        pred = cross_val_predict(modelo, Xm, ym, groups=grupos, cv=cv)
        res[f"R2_cv_{etiqueta}"] = round(1 - ((ym - pred) ** 2).sum() / ((ym - ym.mean()) ** 2).sum(), 3)
    res["R2_cv_max"] = max(res["R2_cv_ridge"], res["R2_cv_boosting"])
    filas.append(res)
c3 = pd.DataFrame(filas)
c3.to_csv(TAB / "coneval_c3_valor_anadido.csv", index=False)
print(c3.to_string(index=False))

# Redundancia entre las dos fuentes (2020)
both = irs[irs.anio == 2020].set_index("mun_inegi")[["irs"]].join(pob[pob.anio == 2020].set_index("mun_inegi")[["pobreza", "pobreza_extrema"]], how="inner")
anotar("r_irs_vs_pobreza_2020", round(float(both.corr().loc["irs", "pobreza"]), 3))
anotar("r_irs_vs_pobreza_extrema_2020", round(float(both.corr().loc["irs", "pobreza_extrema"]), 3))

fig, ax = plt.subplots(figsize=(7.4, 4.6))
d = c3.sort_values("R2_cv_max")
colores = [CAT[0] if f == "IRS" else CAT[1] for f in d.fuente]
ax.barh(d.objetivo, d.R2_cv_max, color=colores, height=0.6)
for i, v in enumerate(d.R2_cv_max):
    ax.text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=8, color=TEXTO_2)
ax.set_xlim(0, 1.08)
ax.set_xlabel("R² con validación cruzada por entidad (mejor de ridge y boosting)")
ax.set_title("¿Cuánto de cada indicador del CONEVAL 2020 ya está en el ECEG?")
from matplotlib.patches import Patch  # noqa: E402
ax.legend(handles=[Patch(color=CAT[0], label="Índice de Rezago Social"), Patch(color=CAT[1], label="Medición de pobreza")],
          loc="lower right", fontsize=8)
ax.tick_params(axis="y", labelsize=8)
guardar(fig, FIG / "f13_coneval_valor_anadido.png")

(carpeta("fase2") / "coneval_resumen.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str))
print("listo")
