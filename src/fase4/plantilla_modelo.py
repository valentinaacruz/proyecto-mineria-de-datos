# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow", "scikit-learn"]
# ///
"""Plantilla para el modelo de cada integrante en la fase 4 (docs/fase3_preparacion_datos.md §6).

Cómo usarla:
  1. Copia este archivo como src/fase4/<tu_modelo>.py (p. ej. ward_forma.py) y agrega a `dependencies` lo que uses
     (p. ej. "tslearn" para DTW).
  2. Llena NOMBRE, AUTOR, ALGORITMO, ENTRADA y PARAMETROS, y reescribe ajustar().
  3. Corre:  uv run src/fase4/<tu_modelo>.py
     Escribe resultados/fase4/modelos/<NOMBRE>/ (particiones.csv.gz, metricas.csv, ficha.json). Esa carpeta se sube
     al repositorio: es lo que usa el ensamble.

Reglas del contrato (las verifica modelado.py):
  - ajustar(X, k, semilla) recibe un arreglo de n renglones y devuelve n etiquetas enteras 0..k-1, en el mismo orden.
  - Debe asignar grupo a TODOS los renglones. Si tu algoritmo no escala a 60,934 secciones (p. ej. Ward), ajústalo con
    una submuestra y asigna el resto (p. ej. al centroide más cercano), dentro de ajustar().
  - Usa la semilla que recibe; no fijes otra. Así las réplicas son reproducibles.
  - Entradas: "forma" (6 variables z), "forma_sin_nivel" (5) o "trayectoria_centrada" (6 elecciones, pp).
  - La búsqueda de hiperparámetros (grid search) es libre, pero los valores finales van en PARAMETROS.
  - Si tu modelo usa otra distancia (p. ej. DTW), pásala en DISTANCIA para que la silueta (T1) se calcule con ella.

Costo: por cada k de 4 a 7 se ajusta 42 veces (1 completa + 20 nulos + 20 bootstrap + 1 ventana). Para probar rápido,
usa evaluar_modelo(..., n_replicas=2, n_nulos=2) y no guardes el resultado.

El ejemplo de abajo (K-means) solo sirve para probar que el flujo funciona; reemplázalo por tu modelo.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modelado import evaluar_modelo, guardar_modelo  # noqa: E402

NOMBRE = "ejemplo_kmeans"            # carpeta de salida: minúsculas y guiones bajos
AUTOR = "Nombre Apellido"
ALGORITMO = "K-means (ejemplo de la plantilla)"
ENTRADA = "forma"                    # "forma" | "forma_sin_nivel" | "trayectoria_centrada"
PARAMETROS = {"n_init": 10}
DISTANCIA = None                     # None = euclidiana; o una función A -> matriz de distancias n×n
NOTAS = ""


def ajustar(X: np.ndarray, k: int, semilla: int) -> np.ndarray:
    from sklearn.cluster import KMeans
    return KMeans(n_clusters=k, n_init=PARAMETROS["n_init"], random_state=semilla).fit_predict(X)


if __name__ == "__main__":
    prueba = "--prueba" in sys.argv          # corrida rápida para revisar que todo funcione; no guarda nada
    res = evaluar_modelo(ajustar, ENTRADA, distancia=DISTANCIA, **({"n_replicas": 2, "n_nulos": 2} if prueba else {}))
    print(res.metricas.to_string(index=False))
    print("k elegido:", res.k_elegido, "·", res.nota_k)
    if not prueba:
        guardar_modelo(NOMBRE, res, autor=AUTOR, algoritmo=ALGORITMO, parametros=PARAMETROS, notas=NOTAS)
