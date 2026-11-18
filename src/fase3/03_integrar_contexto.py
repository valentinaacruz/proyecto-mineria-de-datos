# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow"]
# ///
"""Fase 3.4 · Integración de las variables de contexto por sección (para el árbol de la fase 4 y la descripción de grupos).

Fuentes y decisiones (docs/fase3_preparacion_datos.md §4):
  - ECEG 2020 por sección: los 29 indicadores preseleccionados en la fase 2 (§2.2), con las mismas fórmulas de
    05_comparar_coneval.py pero sin agregar al municipio. Donde el indicador no existe (secciones con < 50 habitantes,
    datos protegidos, o denominador cero) se usa el valor del municipio y se marca `contexto_imputado`.
  - Medición de pobreza municipal 2020 (decisión de la fase 2, §5): solo dos indicadores, % con ingreso inferior a la
    línea de pobreza y % en pobreza extrema, unidos con cruce_municipios_ine_inegi.csv (municipio INE de 2024).
  - De los conteos: tipo de sección 2024, log de la lista nominal 2024 y crecimiento anual de la lista nominal.
  - Identificadores: entidad, municipio INE 2024, municipio INEGI y distrito federal 2024 (solo para ubicar; la fase 2
    §2.1 advierte que los distritos no son comparables entre 2024 y años anteriores).
  - Concurrencia con elecciones locales: candidata de la fase 2 (§3.6), pendiente de fuente; no se incluye.

Uso:  uv run src/fase3/03_integrar_contexto.py      (requiere 01_seleccionar_limpiar.py y src/fase2/05_comparar_coneval.py)
Salidas: data/processed/fase3/contexto.parquet; resultados/fase3/tablas/contexto_descripcion.csv
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import ELECCIONES, PROC, carpeta  # noqa: E402

OUT = PROC / "fase3"
TAB = carpeta("fase3", "tablas")
R = {}


def anotar(clave, valor):
    R[clave] = valor
    print(f"  {clave}: {valor}")


U = pd.read_parquet(OUT / "trayectorias.parquet", columns=["sid"]).sid

# ---------------------------------------------------------------- ECEG 2020 por sección
# Comparación con el denominador que usó la fase 2 (VIVPAR_HAB), para documentar la corrección
def _proporciones_mayores_que_1_con_vivpar_hab(e: pd.DataFrame, ids) -> int:
    d = e.reindex(ids)
    vph = ["VPH_PISOTI", "VPH_NODREN", "VPH_AGUAFV", "VPH_S_ELEC", "VPH_REFRI", "VPH_LAVAD", "VPH_INTER", "VPH_PC", "VPH_CEL", "VPH_AUTOM", "VPH_1DOR"]
    return int((d[vph].div(d.VIVPAR_HAB, axis=0) > 1 + 1e-9).any(axis=1).sum())


CONTEOS = ["POBTOT", "P_3YMAS", "P_5YMAS", "P_12YMAS", "P_15YMAS", "P15YM_AN", "P15YM_SE", "P3YM_HLI", "PNACOE", "PRESOE15",
           "PSINDER", "PDER_IMSS", "PDER_SEGP", "VIVPARH_CV", "TVIVPARHAB", "VPH_PISOTI", "VPH_NODREN", "VPH_AGUAFV", "VPH_S_ELEC", "VPH_REFRI",
           "VPH_LAVAD", "VPH_INTER", "VPH_PC", "VPH_CEL", "VPH_AUTOM", "VPH_1DOR", "OCUPVIVPAR", "PEA", "PDESOCUP", "P_60YMAS",
           "POB0_14", "TOTHOG", "HOGJEF_F", "POB_AFRO", "PCON_DISC", "GRAPROES_x_P15"]


def indicadores(m: pd.DataFrame) -> pd.DataFrame:
    """Los 29 indicadores de la fase 2 a partir de conteos (por sección o sumados por municipio).

    Denominadores de vivienda según el diccionario oficial del ECEG: los VPH_* se captan sobre las viviendas particulares
    habitadas con características e incluyen a las que no tienen información de ocupantes (VIVPARH_CV); OCUPVIVPAR
    incluye la estimación de ocupantes de esas viviendas (TVIVPARHAB). Con VIVPAR_HAB, que las excluye, 15,646
    secciones del universo daban proporciones mayores que 1 (fase 3, §4.1)."""
    return pd.DataFrame({
        "escolaridad_promedio": m.GRAPROES_x_P15 / m.P_15YMAS, "pct_analfabeta": m.P15YM_AN / m.P_15YMAS,
        "pct_sin_escolaridad": m.P15YM_SE / m.P_15YMAS, "pct_lengua_indigena": m.P3YM_HLI / m.P_3YMAS,
        "pct_nacio_otra_entidad": m.PNACOE / m.POBTOT, "pct_otra_entidad_2015": m.PRESOE15 / m.P_5YMAS,
        "pct_sin_derechohabiencia": m.PSINDER / m.POBTOT, "pct_imss": m.PDER_IMSS / m.POBTOT, "pct_seguro_popular": m.PDER_SEGP / m.POBTOT,
        "pct_piso_tierra": m.VPH_PISOTI / m.VIVPARH_CV, "pct_sin_drenaje": m.VPH_NODREN / m.VIVPARH_CV,
        "pct_agua_fuera": m.VPH_AGUAFV / m.VIVPARH_CV, "pct_sin_electricidad": m.VPH_S_ELEC / m.VIVPARH_CV,
        "pct_refrigerador": m.VPH_REFRI / m.VIVPARH_CV, "pct_lavadora": m.VPH_LAVAD / m.VIVPARH_CV,
        "pct_internet": m.VPH_INTER / m.VIVPARH_CV, "pct_computadora": m.VPH_PC / m.VIVPARH_CV, "pct_celular": m.VPH_CEL / m.VIVPARH_CV,
        "pct_automovil": m.VPH_AUTOM / m.VIVPARH_CV, "pct_un_dormitorio": m.VPH_1DOR / m.VIVPARH_CV,
        "ocupantes_por_vivienda": m.OCUPVIVPAR / m.TVIVPARHAB, "tasa_pea": m.PEA / m.P_12YMAS, "pct_desocupada": m.PDESOCUP / m.PEA,
        "pct_60_mas": m.P_60YMAS / m.POBTOT, "pct_0_14": m.POB0_14 / m.POBTOT, "pct_jefatura_femenina": m.HOGJEF_F / m.TOTHOG,
        "pct_afro": m.POB_AFRO / m.POBTOT, "pct_discapacidad": m.PCON_DISC / m.POBTOT, "log_poblacion": np.log1p(m.POBTOT),
    }).replace([np.inf, -np.inf], np.nan)


e = pd.read_parquet(PROC / "eceg2020.parquet")
geo = pd.read_parquet(PROC / "secciones_2021.parquet", columns=["sid", "ENTIDAD", "MUNICIPIO"])
e = e.drop(columns=["ENTIDAD"], errors="ignore").merge(geo, on="sid", how="left")
e["mun21"] = e.ENTIDAD.astype("int64") * 1000 + e.MUNICIPIO.astype("int64")
e["GRAPROES_x_P15"] = e.GRAPROES * e.P_15YMAS
e = e.set_index("sid")
anotar("eceg_secciones_con_proporcion_mayor_que_1_usando_VIVPAR_HAB", _proporciones_mayores_que_1_con_vivpar_hab(e, U))
ind_sec = indicadores(e[CONTEOS])
ind_mun = indicadores(e.groupby("mun21")[CONTEOS].sum(min_count=1))
ECEG_VARS = list(ind_sec.columns)
PROPORCIONES = [c for c in ECEG_VARS if c.startswith("pct_") or c == "tasa_pea"]
ind_sec = ind_sec.reindex(U)
fuera = ind_sec[PROPORCIONES] > 1 + 1e-9                       # proporción imposible: se trata como faltante
anotar("eceg_proporciones_mayores_que_1_tras_corregir", {k: int(v) for k, v in fuera.sum().items() if v})
ind_sec[PROPORCIONES] = ind_sec[PROPORCIONES].mask(fuera)
faltan = ind_sec.isna()
relleno = pd.DataFrame(ind_mun.reindex(e.mun21.reindex(U).values).values, index=U, columns=ECEG_VARS)
ctx = ind_sec.where(~faltan, relleno)
ctx["contexto_imputado"] = faltan.any(axis=1)
anotar("eceg_poblacion_menor_50_en_universo", int((e.POBTOT.reindex(U) < 50).sum()))
anotar("eceg_secciones_con_algun_indicador_imputado", int(faltan.any(axis=1).sum()))
anotar("eceg_celdas_imputadas", int(faltan.to_numpy().sum()))
anotar("eceg_celdas_sin_dato_tras_imputar", int(ctx[ECEG_VARS].isna().to_numpy().sum()))

# ---------------------------------------------------------------- Variables de los conteos e identificadores
sec = pd.read_parquet(PROC / "ccpc_seccion.parquet", columns=["sid", "AELEC", "EDOCVE", "MPIOCVE", "TIPOSEC", "DEF", "LN"])
sec = sec[sec.sid.isin(U)]
s24 = sec[sec.AELEC == 2024].set_index("sid").reindex(U)
ctx["entidad"] = s24.EDOCVE.astype("int64")
ctx["mun_ine"] = (s24.EDOCVE.astype("int64") * 1000 + s24.MPIOCVE.astype("int64"))
ctx["distrito_federal_2024"] = s24.DEF.astype("Int64")
ctx["tipo_seccion"] = s24.TIPOSEC.astype(str).map({"U": "urbana", "M": "mixta", "R": "rural"})
ctx["LN_2024"] = s24.LN.astype("int64")
ctx["log_LN_2024"] = np.log(s24.LN.astype(float))
primera = sec.sort_values("AELEC").groupby("sid").first().reindex(U)
anios = 2024 - primera.AELEC.astype(int)
ctx["crecimiento_LN_anual_pct"] = 100 * ((s24.LN.astype(float) / primera.LN.astype(float)) ** (1 / anios) - 1)
anotar("tipo_seccion_2024", ctx.tipo_seccion.value_counts().to_dict())
anotar("secciones_sin_distrito_2024", int(ctx.distrito_federal_2024.isna().sum()))

# ---------------------------------------------------------------- Pobreza municipal 2020 (CONEVAL)
cruce = pd.read_csv(PROC / "cruce_municipios_ine_inegi.csv")
pob = pd.read_parquet(PROC / "coneval_pobreza.parquet")
pob = pob[pob.anio == 2020].set_index("mun_inegi")
ctx["mun_inegi"] = ctx.mun_ine.map(cruce.set_index("mun_ine").mun_inegi).astype("Int64")
ctx["pct_pobreza_extrema"] = ctx.mun_inegi.map(pob.pobreza_extrema)
ctx["pct_ingreso_inferior_lp"] = ctx.mun_inegi.map(pob.poblacion_con_ingreso_inferior_a_la_linea_de_pobreza_por_ingresos)
anotar("pobreza_secciones_sin_dato", int(ctx.pct_pobreza_extrema.isna().sum()))
anotar("pobreza_LN_2024_sin_dato_pct", round(float(100 * ctx.LN_2024[ctx.pct_pobreza_extrema.isna()].sum() / ctx.LN_2024.sum()), 3))
sin_pob = ctx.pct_pobreza_extrema.isna()
if sin_pob.any():   # se rellena con la mediana de la entidad y se marca
    for c in ["pct_pobreza_extrema", "pct_ingreso_inferior_lp"]:
        ctx[c] = ctx[c].fillna(ctx.groupby("entidad")[c].transform("median"))
    ctx.loc[sin_pob, "contexto_imputado"] = True

ctx.index.name = "sid"
ctx.reset_index().to_parquet(OUT / "contexto.parquet", index=False)
print("contexto", ctx.shape)

num = ECEG_VARS + ["pct_pobreza_extrema", "pct_ingreso_inferior_lp", "log_LN_2024", "crecimiento_LN_anual_pct"]
desc = ctx[num].describe(percentiles=[0.05, 0.5, 0.95]).T
desc["sin_dato_original"] = [int(faltan[c].sum()) if c in faltan else int(sin_pob.sum()) if c.startswith("pct_pob") or c.startswith("pct_ing") else 0 for c in num]
desc.round(4).to_csv(TAB / "contexto_descripcion.csv")
print(desc.round(3).to_string())
(carpeta("fase3") / "contexto_resumen.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str))
print("listo")
