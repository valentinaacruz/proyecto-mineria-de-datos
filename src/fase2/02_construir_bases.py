# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow", "openpyxl", "geopandas"]
# ///
"""Fase 2.1-2.2 · Lee los 192 CSV crudos de los Conteos Censales (6 elecciones × 32 entidades), registra su calidad
fila por fila y construye las bases de trabajo de la fase 2. No filtra ni imputa nada: eso es de la fase 3.

Uso:  uv run src/fase2/02_construir_bases.py            (todo; o un paso: --ccpc, --eceg, --carto)

Salidas en data/processed/:
  ccpc_seccion.parquet          sección × elección: metadatos (municipio, tipo, distritos) y LN, SV, NV, NS
  ccpc_seccion_sexo_edad.parquet  sección × elección × sexo (0, 1, 2) × banda de edad (7 bandas): LN, SV, NV, NS
  ccpc_nacional_edad.parquet    elección × tipo de sección × sexo × edad simple: LN, SV, NV, NS
  eceg2020.parquet              ECEG 2020 por sección (227 indicadores)
  secciones_2021.parquet, municipios_2021.parquet   cartografía (marco seccional 2021, EPSG:6372)
Salidas en resultados/fase2/:
  lectura_archivos.csv          un renglón por CSV crudo con las verificaciones de lectura
"""
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comun import BANDAS, ELECCIONES, PROC, RAW, banda, carpeta, sid  # noqa: E402

COLUMNAS = ["AELEC", "FELECCION", "EDOCVE", "EDONOM", "MPIOCVE", "MPIONOM", "SECCION", "TIPOSEC",
            "DEF", "DEL", "SEXO", "EDAD", "LN", "SV", "NV", "NS"]
NUMERICAS = ["AELEC", "EDOCVE", "MPIOCVE", "SECCION", "DEF", "DEL", "SEXO", "EDAD", "LN", "SV", "NV", "NS"]
CONTEOS = ["LN", "SV", "NV", "NS"]
CLAVE = ["AELEC", "EDOCVE", "SECCION"]
SEXOS = [0, 1, 2]  # 0 hombres, 1 mujeres, 2 no binario (categoría agregada en 2024)


def leer_csv(zf: zipfile.ZipFile, nombre: str) -> tuple[pd.DataFrame, str]:
    crudo = zf.read(nombre)
    for codif in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(crudo), encoding=codif, dtype=str, keep_default_na=False), codif
        except UnicodeDecodeError:
            continue
    raise RuntimeError(nombre)


def verificar_y_limpiar(df: pd.DataFrame, archivo: str, codif: str) -> tuple[pd.DataFrame, dict]:
    """Convierte a número y documenta cada anomalía. Devuelve el DataFrame con NaN donde no había número."""
    info = {"archivo": archivo, "codificacion": codif, "filas": len(df),
            "columnas_ok": list(df.columns) == COLUMNAS}
    for c in NUMERICAS:
        txt = df[c].str.strip()
        num = pd.to_numeric(txt, errors="coerce")
        info[f"no_numerico_{c}"] = int((num.isna() & txt.ne("")).sum())   # texto que no es número
        info[f"vacio_{c}"] = int(txt.eq("").sum())                           # celda vacía o solo espacios
        df[c] = num
    for c in ["TIPOSEC", "MPIONOM", "EDONOM", "FELECCION"]:
        df[c] = df[c].str.strip()
    info["anio"] = int(df.AELEC.mode().iloc[0])
    info["entidad"] = int(df.EDOCVE.mode().iloc[0])
    info["fecha_eleccion"] = df.FELECCION.mode().iloc[0]  # formato distinto en 2024 (MM/DD/AAAA)
    info["tiposec_valores"] = "|".join(sorted(df.TIPOSEC.unique()))
    info["filas_sexo_no_binario"] = int((df.SEXO == 2).sum())         # categoría 2 = no binario (solo 2024)
    info["sexo_invalido"] = int((~df.SEXO.isin(SEXOS)).sum())
    info["edad_min"], info["edad_max"] = df.EDAD.min(), df.EDAD.max()
    info["edad_menor_18"] = int((df.EDAD < 18).sum())
    info["edad_mayor_100"] = int((df.EDAD > 100).sum())
    info["negativos"] = int((df[CONTEOS] < 0).any(axis=1).sum())
    dif = df.LN - (df.SV + df.NV + df.NS)
    info["filas_LN_distinto_suma"] = int((dif.fillna(0) != 0).sum())
    info["LN_menos_suma_total"] = float(dif.sum())
    info["LN_total"] = float(df.LN.sum())
    info["LN_en_filas_sin_edad"] = float(df.loc[df.EDAD.isna(), "LN"].sum())
    info["LN_no_binario"] = float(df.loc[df.SEXO == 2, "LN"].sum())
    info["LN_en_filas_sexo_invalido"] = float(df.loc[~df.SEXO.isin(SEXOS), "LN"].sum())
    info["filas_LN_cero"] = int((df.LN == 0).sum())
    info["duplicados_seccion_sexo_edad"] = int(df.duplicated(["SECCION", "SEXO", "EDAD"]).sum())
    info["secciones"] = int(df.SECCION.nunique())
    # metadatos que deberían ser constantes dentro de cada sección
    g = df.groupby("SECCION")
    for c in ["MPIOCVE", "TIPOSEC", "DEF", "DEL"]:
        info[f"secciones_con_{c}_variable"] = int((g[c].nunique(dropna=False) > 1).sum())
    return df, info


def construir_ccpc():
    seccion, sexo_edad, nacional, lectura = [], [], [], []
    for anio in ELECCIONES:
        ruta = RAW / "ccpc" / f"ccpc_{anio}.zip"
        with zipfile.ZipFile(ruta) as zf:
            for nombre in sorted(n for n in zf.namelist() if n.lower().endswith(".csv")):
                df, codif = leer_csv(zf, nombre)
                df, info = verificar_y_limpiar(df, Path(nombre).name, codif)
                lectura.append(info)
                df = df[df.SECCION.notna()]
                # 1) sección × elección: todos los registros (con o sin edad). Los metadatos se toman del primer
                #    registro; lectura_archivos.csv cuenta las secciones donde no son constantes.
                meta = df.groupby(CLAVE)[["MPIOCVE", "MPIONOM", "TIPOSEC", "DEF", "DEL"]].first()
                seccion.append(meta.join(df.groupby(CLAVE)[CONTEOS].sum()))
                # 2) sección × sexo × banda de edad (solo registros con edad y sexo válidos)
                v = df[df.EDAD.notna() & df.SEXO.isin(SEXOS)].copy()
                v["BANDA"] = banda(v.EDAD)
                v = v[v.BANDA.notna()]
                sexo_edad.append(v.groupby(CLAVE + ["SEXO", "BANDA"], observed=True)[CONTEOS].sum())
                # 3) nacional por edad simple
                nacional.append(v.groupby(["AELEC", "TIPOSEC", "SEXO", "EDAD"])[CONTEOS].sum())
        print(f"ok {anio}", flush=True)

    sec = pd.concat(seccion).reset_index()
    sec.insert(0, "sid", sid(sec.EDOCVE, sec.SECCION))
    for c in ["AELEC", "EDOCVE", "SECCION", "MPIOCVE", "DEF", "DEL"] + CONTEOS:
        sec[c] = sec[c].astype("Int64")
    sec["TIPOSEC"] = sec.TIPOSEC.astype("category")
    sec.to_parquet(PROC / "ccpc_seccion.parquet", index=False)

    se = pd.concat(sexo_edad).reset_index()
    se.insert(0, "sid", sid(se.EDOCVE, se.SECCION))
    se["BANDA"] = pd.Categorical(se.BANDA.astype(str), categories=list(BANDAS), ordered=True)
    se = se.astype({c: "int64" for c in ["AELEC", "EDOCVE", "SECCION", "SEXO"] + CONTEOS})
    se.to_parquet(PROC / "ccpc_seccion_sexo_edad.parquet", index=False)

    nac = pd.concat(nacional).groupby(level=[0, 1, 2, 3]).sum().reset_index()
    nac.to_parquet(PROC / "ccpc_nacional_edad.parquet", index=False)

    lec = pd.DataFrame(lectura)
    lec.to_csv(carpeta("fase2", "tablas") / "lectura_archivos.csv", index=False)
    print(sec.shape, se.shape, nac.shape, lec.shape)


def construir_eceg():
    datos = sorted((RAW / "eceg2020").glob("ECEG [0-9][0-9] *.xlsx"))
    assert len(datos) == 32, len(datos)
    e = pd.concat([pd.read_excel(f, sheet_name=0) for f in datos], ignore_index=True)
    e.columns = [str(c).strip() for c in e.columns]
    e = e.copy()  # desfragmenta el DataFrame que arma read_excel
    e.insert(0, "sid", sid(e.ENTIDAD, e.SECCION))
    e.to_parquet(PROC / "eceg2020.parquet", index=False)
    # Diccionario oficial de variables (se conserva tal cual para el diccionario de datos de la fase 2)
    dic = pd.read_excel(RAW / "eceg2020" / "Diccionario de Datos .xlsx", sheet_name=None, header=None)
    for hoja, d in dic.items():
        d.to_csv(carpeta("fase2", "tablas") / f"eceg2020_diccionario_{hoja.strip().replace(' ', '_')}.csv", index=False, header=False)
    print("ECEG", e.shape, "| hojas del diccionario:", list(dic))


def construir_cartografia():
    """Polígonos de sección (marco 2021) en EPSG:6372, y polígonos municipales obtenidos al disolver secciones."""
    import geopandas as gpd
    partes = []
    for z in sorted((RAW / "cartografia").glob("*.zip")):
        shp = next(n for n in zipfile.ZipFile(z).namelist() if n.upper().endswith("SECCION.SHP"))
        partes.append(gpd.read_file(f"zip://{z}!{shp}").to_crs(6372))
    g = pd.concat(partes, ignore_index=True)
    g["sid"] = sid(g.ENTIDAD, g.SECCION)
    g.to_parquet(PROC / "secciones_2021.parquet")
    mun = g.dissolve(by=["ENTIDAD", "MUNICIPIO"], as_index=False)[["ENTIDAD", "MUNICIPIO", "geometry"]]
    mun["geometry"] = mun.geometry.simplify(200)  # 200 m: suficiente para mapas nacionales y estatales
    mun.to_parquet(PROC / "municipios_2021.parquet")
    print("cartografía", g.shape, "municipios", mun.shape, "| columnas:", list(g.columns))


if __name__ == "__main__":
    PROC.mkdir(parents=True, exist_ok=True)
    pasos = {"ccpc": construir_ccpc, "eceg": construir_eceg, "carto": construir_cartografia}
    elegidos = [a.removeprefix("--") for a in sys.argv[1:]] or list(pasos)  # p. ej. --carto para un solo paso
    for nombre in elegidos:
        pasos[nombre]()
