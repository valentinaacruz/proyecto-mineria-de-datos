# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow", "matplotlib"]
# ///
"""Fase 3.3 · Construcción de las variables de forma de la trayectoria y de las brechas por edad y sexo.

Variables de forma (docs/fase3_preparacion_datos.md §3). Para cada sección se ajusta, sobre sus seis valores de
participación relativa r[e] (pp), la regresión
        r[e] = nivel + tendencia · (t[e] − 2.5) + vaivén · (P[e] − 0.5) + residuo,    t = 0..5,  P = 1 si presidencial
  - nivel:       promedio de las seis elecciones (pp sobre el nacional).
  - tendencia:   cambio por elección (cada 3 años), descontado el vaivén. Se estima junto con el vaivén porque, con la
                 secuencia I-P-I-P-I-P, una diferencia simple de medias mezclaría los dos efectos (r(t, P) = 0.29).
  - vaivén:      presidenciales − intermedias, descontada la tendencia, relativo al vaivén nacional (0 = igual que el país).
  - volatilidad: desviación estándar del residuo (3 grados de libertad): lo que la trayectoria no explica con las tres
                 anteriores.
  - cambio_ajustado (H5): residuo del nivel 2018-2024 sobre el nivel 2009-2015 (descuenta la regresión a la media).
Brechas, relativas a la brecha nacional de cada elección y promediadas en las elecciones con dato observado:
  - brecha_joven:  participación 18-34 − participación 55-74 (H3). El salto de los 30-33 años (fase 2 §3.3) queda dentro
                   de la banda 25-34, salvo en 2009, cuando el de los hombres está justo en el corte 34|35 (1.3 pp). Se
                   excluye a los mayores de 74, incluidos los registros de más de 100 años (fase 2 §4.4).
  - brecha_genero: participación de mujeres − hombres, 18-54 años.
Las mismas variables se calculan con la ventana 2009-2018 (sufijo _v) para la validez temporal (T3).

Uso:  uv run src/fase3/02_construir_variables.py      (requiere 01_seleccionar_limpiar.py)
Salidas: data/processed/fase3/variables.parquet; resultados/fase3/tablas/{variables_descripcion,
         variables_correlacion, variables_tamano}.csv; resultados/fase3/fig/g03_variables_forma.png
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import ELECCIONES, PRESIDENCIALES, PROC, carpeta, participacion  # noqa: E402
from graficas import CAT, GRIS, TEXTO_2, guardar, plt  # noqa: E402

OUT = PROC / "fase3"
TAB, FIG = carpeta("fase3", "tablas"), carpeta("fase3", "fig")
VENTANA = [2009, 2012, 2015, 2018]
A, B = [2009, 2012, 2015], [2018, 2021, 2024]
R = {}


def anotar(clave, valor):
    R[clave] = valor
    print(f"  {clave}: {valor}")


tray = pd.read_parquet(OUT / "trayectorias.parquet").set_index("sid")
T = tray[[f"r_{a}" for a in ELECCIONES]].set_axis(list(ELECCIONES), axis=1)
TV = tray[[f"rv_{a}" for a in VENTANA]].set_axis(VENTANA, axis=1)
imp = tray[[f"imputado_{a}" for a in ELECCIONES]].set_axis(list(ELECCIONES), axis=1)


def forma(m: pd.DataFrame, sufijo: str = "") -> pd.DataFrame:
    """Nivel, tendencia, vaivén y volatilidad por mínimos cuadrados con el mismo diseño para todas las secciones."""
    anios = list(m.columns)
    t = np.array([ELECCIONES.index(a) for a in anios], dtype=float)
    p = np.array([a in PRESIDENCIALES for a in anios], dtype=float)
    X = np.column_stack([np.ones(len(anios)), t - t.mean(), p - p.mean()])
    coef = m.to_numpy() @ np.linalg.pinv(X).T
    resid = m.to_numpy() - coef @ X.T
    gl = len(anios) - X.shape[1]
    return pd.DataFrame({f"nivel{sufijo}": coef[:, 0], f"tendencia{sufijo}": coef[:, 1], f"vaiven{sufijo}": coef[:, 2],
                         f"volatilidad{sufijo}": np.sqrt((resid ** 2).sum(axis=1) / gl)}, index=m.index)


V = forma(T).join(forma(TV, "_v"))
anotar("correlacion_diseno_t_P", round(float(np.corrcoef(np.arange(6), [a in PRESIDENCIALES for a in ELECCIONES])[0, 1]), 3))

# H5: cambio de nivel descontando la regresión a la media
na, nb = T[A].mean(axis=1), T[B].mean(axis=1)
pend, inter = np.polyfit(na, nb, 1)
V["cambio_ajustado"] = nb - (inter + pend * na)
anotar("H5_pendiente_regresion_media", round(float(pend), 3))

# ---------------------------------------------------------------- Brechas por edad y sexo
se = pd.read_parquet(PROC / "ccpc_seccion_sexo_edad.parquet", columns=["sid", "AELEC", "SEXO", "BANDA", "SV", "NV"])
se = se[se.sid.isin(T.index) & se.SEXO.isin([0, 1])]
se["BANDA"] = se.BANDA.astype(str)
observada = (~imp).stack().rename("obs")
observada.index.names = ["sid", "AELEC"]


def brecha(sel_a, sel_b, clave):
    """(participación del grupo a − la del grupo b) en la sección, menos la misma diferencia nacional, por elección."""
    g = pd.concat([sel_a.assign(g="a"), sel_b.assign(g="b")]).groupby(["sid", "AELEC", "g"])[["SV", "NV"]].sum()
    pnac = g.groupby(["AELEC", "g"]).sum().pipe(participacion).unstack()
    ps = participacion(g).unstack()
    ps = ps[(g.SV + g.NV).unstack().gt(0).all(axis=1)]                            # ambos grupos con registros
    d = 100 * ((ps.a - ps.b) - ps.index.get_level_values("AELEC").map(pnac.a - pnac.b).values)
    d = d[observada.reindex(d.index).fillna(False).to_numpy()]                    # solo elecciones observadas
    anotar(f"{clave}_nacional_pp", {int(k): round(100 * float(v), 2) for k, v in (pnac.a - pnac.b).items()})
    return d.unstack()


joven = brecha(se[se.BANDA.isin(["18-24", "25-34"])], se[se.BANDA.isin(["55-64", "65-74"])], "brecha_joven")
m18_54 = se.BANDA.isin(["18-24", "25-34", "35-44", "45-54"])
genero = brecha(se[m18_54 & (se.SEXO == 1)], se[m18_54 & (se.SEXO == 0)], "brecha_genero")
for nombre, d in [("brecha_joven", joven), ("brecha_genero", genero)]:
    V[nombre] = d.mean(axis=1).reindex(V.index)
    V[f"{nombre}_v"] = d[[a for a in VENTANA if a in d.columns]].mean(axis=1).reindex(V.index)
    anotar(f"{nombre}_persistencia_r", round(float(d[A].mean(axis=1).corr(d[B].mean(axis=1))), 3))
    anotar(f"{nombre}_sin_dato", int(V[nombre].isna().sum()))

V.index.name = "sid"
V.reset_index().to_parquet(OUT / "variables.parquet", index=False)
print("variables", V.shape)

# ---------------------------------------------------------------- Descripción
PRINC = ["nivel", "tendencia", "vaiven", "volatilidad", "brecha_joven", "brecha_genero", "cambio_ajustado"]
desc = V[PRINC].describe(percentiles=[0.005, 0.05, 0.25, 0.5, 0.75, 0.95, 0.995]).T
desc["asimetria"] = V[PRINC].skew()
desc.round(3).to_csv(TAB / "variables_descripcion.csv")
print(desc.round(2).to_string())
corr = V[PRINC].corr()
corr.round(3).to_csv(TAB / "variables_correlacion.csv")
print(corr.round(2).to_string())

# Relación con el tamaño de la sección (anticipa el criterio T5: los grupos no deben ser un artefacto del tamaño)
s24 = pd.read_parquet(PROC / "ccpc_seccion.parquet", columns=["sid", "AELEC", "LN"])
log_ln = np.log(s24[s24.AELEC == 2024].set_index("sid").LN.astype(float).reindex(V.index))
tam = pd.DataFrame({"variable": PRINC, "r_con_log_LN_2024": [round(float(V[c].corr(log_ln)), 3) for c in PRINC],
                    "R2_deciles_LN": [round(float(V[c].groupby(pd.qcut(log_ln, 10, labels=False)).transform("mean").var() / V[c].var()), 3)
                                      for c in PRINC]})
tam.to_csv(TAB / "variables_tamano.csv", index=False)
print(tam.to_string(index=False))
anotar("max_R2_deciles_LN", float(tam.R2_deciles_LN.max()))

# Persistencia de cada variable entre la ventana 2009-2018 y la serie completa (orientativo para T3)
anotar("r_ventana_vs_completa", {c: round(float(V[c].corr(V[f"{c}_v"])), 3) for c in ["nivel", "tendencia", "vaiven", "volatilidad"]})

# ---------------------------------------------------------------- Figura: distribución de las variables de forma
etq = {"nivel": "Nivel (pp)", "tendencia": "Tendencia (pp por elección)", "vaiven": "Vaivén P − I (pp)",
       "volatilidad": "Volatilidad (pp)", "brecha_joven": "Brecha joven 18–34 − 55–74 (pp)", "brecha_genero": "Brecha de género M − H (pp)"}
fig, axs = plt.subplots(2, 3, figsize=(10.5, 5.2))
for ax, c in zip(axs.flat, etq):
    lo, hi = V[c].quantile([0.005, 0.995])
    ax.hist(V[c][V[c].between(lo, hi)], bins=70, color=CAT[0], alpha=0.9)
    ax.axvline(V[c].median(), color=CAT[1], linewidth=1.4)
    if c != "volatilidad":
        ax.axvline(0, color=GRIS, linewidth=1, linestyle="--")
    ax.set_title(etq[c], fontsize=9.5)
    ax.set_yticks([])
    ax.text(0.98, 0.95, f"mediana {V[c].median():.1f}\nDE {V[c].std():.1f}", transform=ax.transAxes, ha="right",
            va="top", fontsize=7.5, color=TEXTO_2)
fig.suptitle("Variables de forma por sección (relativas al nacional; se muestra el 99% central)",
             x=0.01, ha="left", fontsize=10.5, fontweight="bold")
fig.tight_layout()
guardar(fig, FIG / "g03_variables_forma.png")

(carpeta("fase3") / "variables_resumen.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str))
print("listo")
