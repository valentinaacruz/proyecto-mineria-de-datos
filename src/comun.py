"""Rutas y definiciones compartidas por todos los scripts del proyecto.

Las definiciones de este módulo son las de la fase 1 (docs/fase1_comprension_negocio.md §2.4):
participación ajustada = SV / (SV + NV); los registros sin captura (NS) se excluyen.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
RES = RAIZ / "resultados"

ELECCIONES = (2009, 2012, 2015, 2018, 2021, 2024)
TIPO_ELECCION = {2009: "intermedia", 2012: "presidencial", 2015: "intermedia",
                 2018: "presidencial", 2021: "intermedia", 2024: "presidencial"}
INTERMEDIAS = tuple(a for a, t in TIPO_ELECCION.items() if t == "intermedia")
PRESIDENCIALES = tuple(a for a, t in TIPO_ELECCION.items() if t == "presidencial")

# Bandas de edad de 10 años (la primera, 18-24, es la de primer voto); límites inferiores
BANDAS = {"18-24": 18, "25-34": 25, "35-44": 35, "45-54": 45, "55-64": 55, "65-74": 65, "75+": 75}

ENTIDADES = {1: "Aguascalientes", 2: "Baja California", 3: "Baja California Sur", 4: "Campeche", 5: "Coahuila",
             6: "Colima", 7: "Chiapas", 8: "Chihuahua", 9: "Ciudad de México", 10: "Durango", 11: "Guanajuato",
             12: "Guerrero", 13: "Hidalgo", 14: "Jalisco", 15: "México", 16: "Michoacán", 17: "Morelos",
             18: "Nayarit", 19: "Nuevo León", 20: "Oaxaca", 21: "Puebla", 22: "Querétaro", 23: "Quintana Roo",
             24: "San Luis Potosí", 25: "Sinaloa", 26: "Sonora", 27: "Tabasco", 28: "Tamaulipas", 29: "Tlaxcala",
             30: "Veracruz", 31: "Yucatán", 32: "Zacatecas"}


def banda(edad):
    """Banda de edad (texto) para una serie de edades simples."""
    import pandas as pd
    cortes = list(BANDAS.values()) + [200]
    return pd.cut(edad, bins=cortes, right=False, labels=list(BANDAS))


def participacion(df, sv="SV", nv="NV"):
    """Participación ajustada SV / (SV + NV)."""
    return df[sv] / (df[sv] + df[nv])


def sid(edo, seccion):
    """Identificador único de sección: entidad * 10000 + sección (las secciones se numeran dentro de cada entidad)."""
    return edo.astype("int64") * 10000 + seccion.astype("int64")


def carpeta(*partes) -> Path:
    p = RES.joinpath(*partes)
    p.mkdir(parents=True, exist_ok=True)
    return p
