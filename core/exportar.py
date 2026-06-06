"""
core/exportar.py
----------------
Guarda capítulos scrapeados en TXT (único), JSON, o TXT por capítulo.
No depende de tkinter ni de Playwright.
"""

import json
import re
from pathlib import Path


def limpiar_nombre(nombre: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nombre).strip()


def como_txt(capitulos: list[dict], ruta: Path):
    """Un único archivo TXT con todos los capítulos separados."""
    with open(ruta, "w", encoding="utf-8") as f:
        for cap in capitulos:
            f.write(f"\n{'=' * 70}\n")
            f.write(f"{cap['titulo']}\n")
            f.write(f"{'=' * 70}\n\n")
            f.write(cap["texto"])
            f.write("\n\n")
    print(f"[OK] TXT guardado: {ruta}", flush=True)


def como_json(capitulos: list[dict], ruta: Path):
    """Capítulos como JSON estructurado."""
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(capitulos, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON guardado: {ruta}", flush=True)


def como_separados(capitulos: list[dict], carpeta: Path):
    """Un archivo TXT por capítulo dentro de una subcarpeta."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for i, cap in enumerate(capitulos, 1):
        nombre = limpiar_nombre(f"{i:04d}_{cap['titulo'][:60]}.txt")
        (carpeta / nombre).write_text(
            f"{cap['titulo']}\n{'=' * 60}\n\n{cap['texto']}\n",
            encoding="utf-8",
        )
    print(f"[OK] {len(capitulos)} capítulos en: {carpeta}", flush=True)


def guardar(capitulos: list[dict], formato: str, carpeta: Path, nombre_base: str):
    """
    Punto de entrada unificado.
    formato: 'txt' | 'json' | 'separados'
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    if formato == "txt":
        como_txt(capitulos, carpeta / f"{nombre_base}.txt")
    elif formato == "json":
        como_json(capitulos, carpeta / f"{nombre_base}.json")
    elif formato == "separados":
        como_separados(capitulos, carpeta / nombre_base)
    else:
        raise ValueError(f"Formato desconocido: {formato!r}")