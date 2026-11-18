# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow", "matplotlib", "scikit-learn"]
# ///
"""Fase 3.5 · Formato final: tabla analítica por sección, matrices listas para el modelado, PCA y diccionario.

Decisiones (docs/fase3_preparacion_datos.md §5):
  - Variables de agrupamiento: nivel, vaivén, tendencia, log(volatilidad), brecha_joven y brecha_genero.
    La volatilidad se pasa a logaritmo por su asimetría (1.8). Cada variable se recorta (winsoriza) al percentil
    0.5-99.5 y se estandariza (media 0, DE 1). Recortar evita que unas pocas secciones extremas muevan los centroides.
  - Nivel y forma por separado (riesgo R2): la matriz trae z_nivel como columna aparte, para que la fase 4 agrupe con
    o sin ella. La trayectoria centrada (r − nivel) es la entrada de K-means con DTW.
  - PCA sobre las seis variables estandarizadas, solo para visualizar.
  - Las mismas matrices para la ventana 2009-2018 (validez temporal, T3), estandarizadas con sus propias medias y DE.

Uso:  uv run src/fase3/04_formatear.py      (requiere 01, 02 y 03)
Salidas en data/processed/fase3/: tabla_analitica.parquet, matriz_forma.parquet, matriz_forma_2009_2018.parquet,
        trayectoria_centrada.parquet
Salidas en resultados/fase3/: tablas/{diccionario_tabla_analitica, estandarizacion, pca_cargas}.csv,
        fig/g04_pca.png, g05_trayectorias_centradas.png, preparacion_resumen.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import ELECCIONES, PRESIDENCIALES, PROC, carpeta  # noqa: E402
from graficas import CAT, CMAP_SEQ, GRIS, TEXTO_2, guardar, plt  # noqa: E402

OUT = PROC / "fase3"
TAB, FIG = carpeta("fase3", "tablas"), carpeta("fase3", "fig")
CORTE = (0.005, 0.995)
VARS = ["nivel", "vaiven", "tendencia", "log_volatilidad", "brecha_joven", "brecha_genero"]
R = {}


def anotar(clave, valor):
    R[clave] = valor
    print(f"  {clave}: {valor}")


tray = pd.read_parquet(OUT / "trayectorias.parquet").set_index("sid")
var = pd.read_parquet(OUT / "variables.parquet").set_index("sid")
ctx = pd.read_parquet(OUT / "contexto.parquet").set_index("sid")
var["log_volatilidad"] = np.log(var.volatilidad)
var["log_volatilidad_v"] = np.log(var.volatilidad_v)

# Brechas sin dato (secciones sin registros de algún grupo): mediana del municipio, marcada
sin_brecha = var[["brecha_joven", "brecha_genero"]].isna().any(axis=1)
for c in ["brecha_joven", "brecha_genero", "brecha_joven_v", "brecha_genero_v"]:
    var[c] = var[c].fillna(var[c].groupby(ctx.mun_ine).transform("median")).fillna(var[c].median())
var["brecha_imputada"] = sin_brecha
anotar("brechas_imputadas", int(sin_brecha.sum()))

tabla = ctx[["entidad", "mun_ine", "mun_inegi", "distrito_federal_2024", "tipo_seccion", "LN_2024"]].join(tray).join(var)
tabla = tabla.join(ctx.drop(columns=["entidad", "mun_ine", "mun_inegi", "distrito_federal_2024", "tipo_seccion", "LN_2024"]))
for a in ELECCIONES:
    tabla[f"rc_{a}"] = tabla[f"r_{a}"] - tabla.nivel             # trayectoria centrada (forma sin nivel)
VENTANA = (2009, 2012, 2015, 2018)
for a in VENTANA:
    tabla[f"rvc_{a}"] = tabla[f"rv_{a}"] - tabla.nivel_v         # ídem para la ventana 2009-2018 (T3 con DTW)
tabla.reset_index().to_parquet(OUT / "tabla_analitica.parquet", index=False)
anotar("tabla_analitica", list(tabla.shape))


def estandarizar(df: pd.DataFrame, cols: list[str], sufijo: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
    z, info = pd.DataFrame(index=df.index), []
    for c in cols:
        x = df[c + sufijo]
        lo, hi = x.quantile(CORTE)
        xw = x.clip(lo, hi)
        z[f"z_{c}"] = (xw - xw.mean()) / xw.std()
        info.append({"variable": c + sufijo, "p0.5": lo, "p99.5": hi, "recortadas": int(((x < lo) | (x > hi)).sum()),
                     "media_tras_recorte": xw.mean(), "de_tras_recorte": xw.std(), "asimetria_original": x.skew(),
                     "asimetria_final": z[f"z_{c}"].skew()})
    return z, pd.DataFrame(info)


Z, info = estandarizar(tabla, VARS)
Zv, info_v = estandarizar(tabla, VARS, "_v")
pd.concat([info.assign(ventana="2009–2024"), info_v.assign(ventana="2009–2018")]).round(4).to_csv(TAB / "estandarizacion.csv", index=False)
print(info.round(3).to_string(index=False))
peso = tabla.LN_2024.rename("peso_LN_2024")
Z.join(peso).reset_index().to_parquet(OUT / "matriz_forma.parquet", index=False)
Zv.join(peso).reset_index().to_parquet(OUT / "matriz_forma_2009_2018.parquet", index=False)
tabla[[f"rc_{a}" for a in ELECCIONES]].join(peso).reset_index().to_parquet(OUT / "trayectoria_centrada.parquet", index=False)
tabla[[f"rvc_{a}" for a in VENTANA]].join(peso).reset_index().to_parquet(OUT / "trayectoria_centrada_2009_2018.parquet", index=False)
anotar("matriz_forma", list(Z.shape))
anotar("correlacion_max_abs_entre_variables_z", round(float((Z.corr().abs() - np.eye(len(VARS))).max().max()), 3))

# ---------------------------------------------------------------- PCA (solo para visualizar)
from sklearn.decomposition import PCA  # noqa: E402

pca = PCA().fit(Z.values)
cargas = pd.DataFrame(pca.components_.T, index=VARS, columns=[f"CP{i + 1}" for i in range(len(VARS))])
cargas.loc["varianza_explicada"] = pca.explained_variance_ratio_
cargas.round(3).to_csv(TAB / "pca_cargas.csv")
print(cargas.round(2).to_string())
anotar("pca_varianza_explicada", [round(float(v), 3) for v in pca.explained_variance_ratio_])
S = pca.transform(Z.values)

etq = {"nivel": "nivel", "vaiven": "vaivén", "tendencia": "tendencia", "log_volatilidad": "volatilidad",
       "brecha_joven": "brecha joven", "brecha_genero": "brecha género"}
fig, axs = plt.subplots(1, 2, figsize=(10.5, 4.3), gridspec_kw={"width_ratios": [1.15, 1]})
hb = axs[0].hexbin(S[:, 0], S[:, 1], gridsize=80, cmap=CMAP_SEQ, mincnt=1, bins="log", extent=(-5, 5, -5, 5))
esc = 3.6
for v in VARS:
    x, y = cargas.loc[v, "CP1"] * esc, cargas.loc[v, "CP2"] * esc
    axs[0].annotate("", xy=(x, y), xytext=(0, 0), arrowprops=dict(arrowstyle="->", color=CAT[1], lw=1.4))
    ang = np.arctan2(y, x)
    axs[0].annotate(etq[v], xy=(x, y), xytext=(14 * np.cos(ang), 14 * np.sin(ang)), textcoords="offset points",
                    fontsize=8, color=TEXTO_2, ha="left" if x >= 0 else "right", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
axs[0].set_xlim(-5, 5)
axs[0].set_ylim(-5, 5)
axs[0].set_xlabel(f"CP1 ({100 * pca.explained_variance_ratio_[0]:.0f}%)")
axs[0].set_ylabel(f"CP2 ({100 * pca.explained_variance_ratio_[1]:.0f}%)")
axs[0].set_title("Secciones en el plano de los dos primeros componentes")
fig.colorbar(hb, ax=axs[0], shrink=0.75, label="secciones (log)")
axs[1].bar(range(1, len(VARS) + 1), 100 * pca.explained_variance_ratio_, color=CAT[0], width=0.6)
axs[1].axhline(100 / len(VARS), color=GRIS, linestyle="--", linewidth=1)
axs[1].text(len(VARS) + 0.4, 100 / len(VARS) + 0.8, "variables\nindependientes", fontsize=7.5, color=TEXTO_2, ha="right")
for i, v in enumerate(pca.explained_variance_ratio_):
    axs[1].text(i + 1, 100 * v + 0.6, f"{100 * v:.0f}%", ha="center", fontsize=8, color=TEXTO_2)
axs[1].set_xticks(range(1, len(VARS) + 1), [f"CP{i}" for i in range(1, len(VARS) + 1)])
axs[1].set_ylabel("Varianza explicada (%)")
axs[1].grid(axis="x", visible=False)
axs[1].set_title("Varianza por componente")
fig.tight_layout()
guardar(fig, FIG / "g04_pca.png")

# ---------------------------------------------------------------- Trayectorias centradas: percentiles por elección
fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.4), sharey=True)
xs = list(ELECCIONES)
etq_x = [f"{a}\n{'P' if a in PRESIDENCIALES else 'I'}" for a in xs]
for ax, (pref, titulo) in zip(axs, [("r", "Trayectoria relativa al nacional (con nivel)"), ("rc", "Trayectoria centrada (sin nivel)")]):
    m = tabla[[f"{pref}_{a}" for a in xs]]
    for (q1, q2), alfa in [((0.05, 0.95), 0.18), ((0.25, 0.75), 0.35)]:
        ax.fill_between(xs, m.quantile(q1), m.quantile(q2), color=CAT[0], alpha=alfa, linewidth=0)
    ax.plot(xs, m.median(), color=CAT[0], marker="o")
    ax.axhline(0, color=GRIS, linewidth=1)
    ax.set_xticks(xs, etq_x, fontsize=8)
    ax.set_title(titulo)
axs[0].set_ylabel("pp (mediana, 25–75% y 5–95%)")
fig.tight_layout()
guardar(fig, FIG / "g05_trayectorias_centradas.png")
anotar("DE_r_por_eleccion_promedio", round(float(tabla[[f"r_{a}" for a in xs]].std().mean()), 2))
anotar("DE_rc_por_eleccion_promedio", round(float(tabla[[f"rc_{a}" for a in xs]].std().mean()), 2))

# ---------------------------------------------------------------- Diccionario de la tabla analítica
D = {
    "sid": ("Identificador de sección: entidad × 10,000 + sección", "—", "CCPC"),
    "entidad": ("Clave de entidad (1–32)", "—", "CCPC 2024"),
    "mun_ine": ("Municipio, clave INE de 2024 (entidad × 1,000 + municipio)", "—", "CCPC 2024"),
    "mun_inegi": ("Municipio, clave INEGI (vía cruce_municipios_ine_inegi.csv)", "—", "Fase 2 §5"),
    "distrito_federal_2024": ("Distrito federal, marco 2023; solo para ubicar, no comparable con años previos", "—", "CCPC 2024"),
    "tipo_seccion": ("Urbana, mixta o rural en 2024", "—", "CCPC 2024"),
    "LN_2024": ("Lista nominal 2024; peso de la sección en la lista nominal (criterio T4)", "personas", "CCPC 2024"),
    "n_imputadas": ("Número de elecciones imputadas (0 o 1)", "—", "01_seleccionar_limpiar.py"),
    "brecha_imputada": ("La sección no tenía registros de algún grupo de edad o sexo", "—", "04_formatear.py"),
    "contexto_imputado": ("Algún indicador del ECEG tomado del municipio (28 secciones) o la pobreza tomada de la mediana de la entidad (17)", "—", "03_integrar_contexto.py"),
    "nivel": ("Promedio de la participación relativa en las seis elecciones", "pp", "02_construir_variables.py"),
    "tendencia": ("Cambio por elección (3 años), descontado el vaivén", "pp/elección", "02_construir_variables.py"),
    "vaiven": ("Presidenciales − intermedias, descontada la tendencia, relativo al vaivén nacional", "pp", "02_construir_variables.py"),
    "volatilidad": ("DE del residuo de la regresión nivel + tendencia + vaivén (3 gl)", "pp", "02_construir_variables.py"),
    "log_volatilidad": ("Logaritmo natural de la volatilidad", "log pp", "04_formatear.py"),
    "cambio_ajustado": ("H5: nivel 2018–2024 menos el esperado por regresión a la media desde 2009–2015", "pp", "02_construir_variables.py"),
    "brecha_joven": ("(Participación 18–34 − 55–74) menos la nacional, promedio de elecciones observadas", "pp", "02_construir_variables.py"),
    "brecha_genero": ("(Mujeres − hombres, 18–54) menos la nacional, promedio de elecciones observadas", "pp", "02_construir_variables.py"),
    "pct_pobreza_extrema": ("Población en pobreza extrema del municipio, 2020", "%", "CONEVAL"),
    "pct_ingreso_inferior_lp": ("Población con ingreso inferior a la línea de pobreza, municipio, 2020", "%", "CONEVAL"),
    "log_LN_2024": ("Logaritmo de la lista nominal 2024", "log personas", "CCPC 2024"),
    "crecimiento_LN_anual_pct": ("Crecimiento anual de la lista nominal desde la primera elección en que aparece", "%/año", "CCPC"),
}
for a in ELECCIONES:
    D[f"r_{a}"] = (f"Participación {a} relativa a la nacional (imputada si imputado_{a})", "pp", "01_seleccionar_limpiar.py")
    D[f"imputado_{a}"] = (f"La participación de {a} fue imputada", "—", "01_seleccionar_limpiar.py")
    D[f"rc_{a}"] = (f"Trayectoria centrada: r_{a} − nivel", "pp", "04_formatear.py")
for a in VENTANA:
    D[f"rv_{a}"] = (f"Participación {a} relativa, imputada solo con la ventana 2009–2018 (T3)", "pp", "01_seleccionar_limpiar.py")
    D[f"rvc_{a}"] = (f"Trayectoria centrada de la ventana: rv_{a} − nivel_v", "pp", "04_formatear.py")
for c in ["nivel", "tendencia", "vaiven", "volatilidad", "log_volatilidad", "brecha_joven", "brecha_genero"]:
    D[f"{c}_v"] = (f"{c} calculada solo con 2009–2018 (T3)", D[c][1], D[c][2])
for c in ctx.columns:
    if c not in D and c != "sid":
        unidad = {"escolaridad_promedio": "años", "ocupantes_por_vivienda": "personas por vivienda",
                  "log_poblacion": "log(1 + personas)"}.get(c, "proporción" if c.startswith("pct_") or c == "tasa_pea" else "—")
        D[c] = (f"Indicador del ECEG 2020 por sección ({c}); valor del municipio si la sección no tiene dato", unidad, "ECEG 2020")
dic = pd.DataFrame([{"columna": c, "descripcion": D[c][0], "unidad": D[c][1], "origen": D[c][2],
                     "tipo": str(tabla.reset_index()[c].dtype), "sin_dato": int(tabla.reset_index()[c].isna().sum())}
                    for c in tabla.reset_index().columns])
dic.to_csv(TAB / "diccionario_tabla_analitica.csv", index=False)
anotar("columnas_sin_describir", [c for c in tabla.reset_index().columns if c not in D])
anotar("celdas_sin_dato_en_matriz_forma", int(Z.isna().to_numpy().sum()))

(carpeta("fase3") / "preparacion_resumen.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str))
print("listo")
