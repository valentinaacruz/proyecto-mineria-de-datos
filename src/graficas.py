"""Estilo común de las figuras (matplotlib, PNG estáticos para los reportes).

Paleta: instancia de referencia validada de la guía de visualización (azul, naranja, aqua como primeros tres
colores categóricos; con más de tres series se usan paneles). Divergente: azul (por encima del nacional) ↔ rojo
(por debajo) con gris neutro en el centro. Secuencial: un solo tono azul, de claro a oscuro.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
REJILLA = "#e4e3df"
CAT = ["#2a78d6", "#eb6834", "#1baf7a"]          # categóricos 1-3 (validados para todos los pares)
GRIS = "#8a8984"                                   # referencia / contexto
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIV = ["#990618", "#db534f", "#fba9a1", "#f0efec", "#9ec5f4", "#3987e5", "#184f95"]  # brazos con luminosidad OKLab igualada

CMAP_SEQ = LinearSegmentedColormap.from_list("seq_azul", SEQ)
CMAP_DIV = LinearSegmentedColormap.from_list("div_rojo_azul", DIV)

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
    "figure.dpi": 110, "savefig.dpi": 160, "savefig.bbox": "tight",
    "font.family": "sans-serif", "font.size": 9.5,
    "text.color": TEXTO, "axes.labelcolor": TEXTO_2, "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
    "axes.edgecolor": REJILLA, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "lines.linewidth": 2, "lines.markersize": 5, "legend.frameon": False,
    "axes.prop_cycle": matplotlib.cycler(color=CAT),
})


def guardar(fig, ruta):
    fig.savefig(ruta)
    plt.close(fig)
    print("fig", ruta.name)
