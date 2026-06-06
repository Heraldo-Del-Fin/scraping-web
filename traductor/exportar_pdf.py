"""
traductor/exportar_pdf.py
-------------------------
Genera PDF y TXT a partir de capítulos traducidos.
No depende de tkinter.
"""

import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    )
except ImportError:
    print("ERROR: Falta reportlab. Ejecuta: pip install reportlab")
    raise


# ── Registro de fuentes ───────────────────────────────────────────────────────

_FUENTES_CANDIDATAS = [
    ("C:/Windows/Fonts/DejaVuSans.ttf",  "DejaVuSans"),
    ("C:/Windows/Fonts/Arial.ttf",        "ArialUnicode"),
    ("C:/Windows/Fonts/calibri.ttf",      "Calibri"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "LiberationSans"),
    ("/Library/Fonts/Arial.ttf",          "ArialUnicode"),
    ("/System/Library/Fonts/Helvetica.ttc","HelveticaMac"),
]

def _registrar_fuente() -> str:
    for ruta, nombre in _FUENTES_CANDIDATAS:
        if os.path.exists(ruta):
            try:
                pdfmetrics.registerFont(TTFont(nombre, ruta))
                return nombre
            except Exception:
                continue
    return "Helvetica"


# ── Estilos ───────────────────────────────────────────────────────────────────

def _estilos(fuente: str) -> dict:
    base = getSampleStyleSheet()
    return {
        "portada": ParagraphStyle(
            "Portada", parent=base["Title"],
            fontName=fuente, fontSize=22, leading=28,
            spaceAfter=20, textColor=colors.HexColor("#1a1a2e"), alignment=1,
        ),
        "capitulo": ParagraphStyle(
            "Capitulo", parent=base["Heading1"],
            fontName=fuente, fontSize=15, leading=20,
            spaceBefore=10, spaceAfter=14,
            textColor=colors.HexColor("#16213e"), alignment=1,
        ),
        "cuerpo": ParagraphStyle(
            "Cuerpo", parent=base["Normal"],
            fontName=fuente, fontSize=11, leading=17,
            spaceAfter=8, firstLineIndent=20,
            textColor=colors.HexColor("#2c2c2c"), alignment=4,
        ),
        "nota": ParagraphStyle(
            "Nota", parent=base["Italic"],
            fontName=fuente, fontSize=9,
            textColor=colors.gray, alignment=1,
        ),
    }


def _xml(texto: str) -> str:
    return (texto
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ── API pública ───────────────────────────────────────────────────────────────

IDIOMAS = {
    "es": "Español",    "pt": "Portugués",  "fr": "Francés",
    "de": "Alemán",     "it": "Italiano",   "ja": "Japonés",
    "ko": "Coreano",    "zh-CN": "Chino Simplificado",
    "ru": "Ruso",       "ar": "Árabe",
}

def como_pdf(
    capitulos: list[dict],
    ruta_salida: Path,
    titulo_novela: str,
    idioma: str = "es",
):
    """Genera un PDF bien formateado con portada y capítulos."""
    fuente  = _registrar_fuente()
    estilos = _estilos(fuente)

    doc = SimpleDocTemplate(
        str(ruta_salida), pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
        topMargin=2.5*cm, bottomMargin=2.5*cm,
        title=titulo_novela, author="Novel Scraper",
    )

    historia = []

    # Portada
    historia += [
        Spacer(1, 3*cm),
        Paragraph(_xml(titulo_novela), estilos["portada"]),
        Spacer(1, 0.5*cm),
        HRFlowable(width="60%", thickness=2,
                   color=colors.HexColor("#16213e"), hAlign="CENTER"),
        Spacer(1, 0.5*cm),
        Paragraph(
            f"Traducido al {IDIOMAS.get(idioma, idioma)} · {len(capitulos)} capítulos",
            estilos["nota"],
        ),
        PageBreak(),
    ]

    # Capítulos
    for i, cap in enumerate(capitulos, 1):
        historia += [
            Paragraph(_xml(cap["titulo"]), estilos["capitulo"]),
            HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey),
            Spacer(1, 0.3*cm),
        ]
        for parrafo in cap["texto"].split("\n"):
            if parrafo.strip():
                historia.append(Paragraph(_xml(parrafo.strip()), estilos["cuerpo"]))
        if i < len(capitulos):
            historia.append(PageBreak())

    doc.build(historia)
    print(f"[OK] PDF guardado: {ruta_salida}", flush=True)


def como_txt(capitulos: list[dict], ruta_salida: Path):
    """Guarda los capítulos traducidos como TXT manteniendo la estructura."""
    with open(ruta_salida, "w", encoding="utf-8") as f:
        for cap in capitulos:
            f.write(f"\n{'=' * 70}\n{cap['titulo']}\n{'=' * 70}\n\n{cap['texto']}\n\n")
    print(f"[OK] TXT traducido guardado: {ruta_salida}", flush=True)


def guardar(
    capitulos: list[dict],
    formato: str,
    ruta_salida: Path,
    titulo_novela: str,
    idioma: str = "es",
):
    """
    Punto de entrada unificado.
    formato: 'pdf' | 'txt'
    """
    if formato == "pdf":
        como_pdf(capitulos, ruta_salida, titulo_novela, idioma)
    elif formato == "txt":
        como_txt(capitulos, ruta_salida)
    else:
        raise ValueError(f"Formato desconocido: {formato!r}")