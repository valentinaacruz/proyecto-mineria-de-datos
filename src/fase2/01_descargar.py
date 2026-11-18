# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Fase 2.1 · Recolección inicial de datos. Descarga las fuentes públicas a data/raw/ (idempotente: no repite lo ya descargado).

Uso (desde la raíz del repositorio):  uv run src/fase2/01_descargar.py

Fuentes (URLs verificadas el 17-nov-2026):
  1. INE-DECEyEC, Conteos Censales de Participación Ciudadana 2009-2024 (sección × sexo × edad simple) y su manual.
  2. INE-INEGI, Estadísticas Censales a Escalas Geoelectorales (ECEG) 2020, por sección (API de cartografia.ine.mx).
  3. INE, marco seccional 2021 (shapefiles de secciones por entidad).
  4. CONEVAL, Índice de Rezago Social 2000-2020 por entidad y municipio, y nota técnica del IRS longitudinal.
  5. CONEVAL, Medición de la pobreza municipal 2010-2020 (concentrado de indicadores) y su metodología.
Si una ruta cambia, el script se detiene con el nombre del archivo esperado para descargarlo a mano.
"""
import json
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"
INE = "https://www.ine.mx/wp-content/uploads"
CARTO = "https://cartografia.ine.mx"
CONEVAL = "https://www.coneval.org.mx/Medicion/Documents"
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"
REGISTRO = []  # (archivo, url, bytes) para el reporte de recolección


def bajar(url: str, destino: Path, min_bytes: int = 10_000) -> None:
    if not (destino.exists() and destino.stat().st_size >= min_bytes):
        destino.parent.mkdir(parents=True, exist_ok=True)
        r = S.get(url, timeout=600, stream=True)
        if r.status_code != 200 or "text/html" in r.headers.get("content-type", ""):
            sys.exit(f"[ERROR] {r.status_code} {url}\n  La ruta cambió: descarga el archivo a mano a {destino}")
        tmp = destino.with_suffix(destino.suffix + ".part")
        with open(tmp, "wb") as f:
            for bloque in r.iter_content(1 << 20):
                f.write(bloque)
        if tmp.stat().st_size < min_bytes:
            tmp.unlink()
            sys.exit(f"[ERROR] archivo demasiado pequeño: {url}")
        tmp.rename(destino)
        print(f"ok  {destino.relative_to(RAIZ)}  {destino.stat().st_size / 1e6:.1f} MB", flush=True)
    REGISTRO.append({"archivo": str(destino.relative_to(RAIZ)), "url": url, "bytes": destino.stat().st_size})


def main() -> None:
    # 1. Conteos censales (un zip por elección con 32 CSV, uno por entidad) y manual
    for anio in (2009, 2012, 2015, 2018, 2021):
        bajar(f"{INE}/2022/04/DatosAbiertos_DECEyEC_ConteosCensales{anio}.zip", RAW / "ccpc" / f"ccpc_{anio}.zip", 1_000_000)
    bajar(f"{INE}/2025/08/DatosAbiertos_DECEyEC_ConteosCensales2024.zip", RAW / "ccpc" / "ccpc_2024.zip", 1_000_000)
    bajar(f"{INE}/2025/06/Manual-Conteos-Censales-2009-2024.pdf", RAW / "ccpc" / "manual_ccpc_2009_2024.pdf")

    # 2. ECEG 2020 (lista de archivos servida por la API de cartografía)
    for f in S.get(f"{CARTO}/sige8/api/estadisticos?producto=ECEG&corte=2020", timeout=60).json():
        bajar(f"{CARTO}/mapoteca/{f['path']}{f['archivo']}", RAW / "eceg2020" / f["archivo"])

    # 3. Marco seccional 2021 (un zip por entidad)
    for ent in range(1, 33):
        for f in S.get(f"{CARTO}/sige8/api/estadisticos/marcoseccional?producto=ECEG&corte=2021&entidad={ent}", timeout=60).json():
            bajar(f"{CARTO}/mapoteca/{f['path']}{f['archivo']}", RAW / "cartografia" / f["archivo"])

    # 4. CONEVAL: Índice de Rezago Social
    bajar(f"{CONEVAL}/IRS_2020/IRS_ent_mun_2000_2020.zip", RAW / "coneval" / "IRS_ent_mun_2000_2020.zip")
    bajar(f"{CONEVAL}/IRS_2020/Nota_principales_resultados_IRS_2020.pdf", RAW / "coneval" / "IRS_2020_nota_resultados.pdf")
    bajar(f"{CONEVAL}/Rezago_Social_Longitudinal/2020/Nota_tecnica.pdf", RAW / "coneval" / "IRS_longitudinal_nota_tecnica.pdf")

    # 5. CONEVAL: Medición de la pobreza municipal 2010-2020
    bajar(f"{CONEVAL}/Pobreza_municipal/2020/Concentrado_indicadores_de_pobreza_2020.zip", RAW / "coneval" / "pobreza_municipal_2010_2020.zip")
    bajar(f"{CONEVAL}/Pobreza_municipal/2020/Metodologia_pobreza_municipal_2020.pdf", RAW / "coneval" / "pobreza_municipal_metodologia_2020.pdf")

    (RAW / "registro_descargas.json").write_text(json.dumps(REGISTRO, indent=1, ensure_ascii=False))
    total = sum(r["bytes"] for r in REGISTRO)
    print(f"\n{len(REGISTRO)} archivos, {total / 1e9:.2f} GB en data/raw/ (registro en data/raw/registro_descargas.json)")


if __name__ == "__main__":
    main()
