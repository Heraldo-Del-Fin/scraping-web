"""
traductor_cli.py
----------------
Punto de entrada CLI para el traductor + exportador.
La GUI lo llama como subproceso; también funciona desde la terminal.

Uso:
    python traductor_cli.py <archivo.txt> [opciones]
    python traductor_cli.py novelas/mi-novela.txt --idioma es --formato-salida pdf
    python traductor_cli.py novelas/mi-novela.txt --idioma pt --formato-salida txt
"""

import argparse
import re
import sys
from pathlib import Path

# Forzar UTF-8 en Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from traductor.exportar_pdf import guardar as exportar_traducido
from traductor.traducir import IDIOMAS, set_modo_progreso, traducir_capitulos


# ── Parser del TXT scrapeado ──────────────────────────────────────────────────

def parsear_txt(ruta: Path) -> list[dict]:
    """Lee el TXT generado por scraper_cli.py y lo separa en capítulos."""
    contenido = ruta.read_text(encoding="utf-8")
    bloques   = re.split(r'\n={50,}\n', contenido)
    caps      = []
    i         = 0

    while i < len(bloques):
        bloque = bloques[i].strip()
        if not bloque:
            i += 1
            continue
        lineas = bloque.split("\n")
        titulo = lineas[0].strip()
        texto  = "\n".join(lineas[1:]).strip() if len(lineas) > 1 else ""
        if not texto and i + 1 < len(bloques):
            texto = bloques[i + 1].strip()
            i += 1
        if titulo and texto:
            caps.append({"titulo": titulo, "texto": texto})
        i += 1

    # Fallback: tratar todo como un único capítulo
    if not caps and contenido.strip():
        caps = [{"titulo": ruta.stem, "texto": contenido.strip()}]
    return caps


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Traductor + exportador para novelas scrapeadas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("archivo", nargs="?", help="Ruta al TXT a traducir")
    parser.add_argument("--idioma",          "-i", default="es")
    parser.add_argument("--formato-salida",  choices=["pdf", "txt"], default="pdf")
    parser.add_argument("--salida",          "-o", default="./pdfs")
    parser.add_argument("--nombre",          "-n", default="")
    parser.add_argument("--listar-idiomas",  action="store_true")
    parser.add_argument("--progreso",        action="store_true")
    args = parser.parse_args()

    set_modo_progreso(args.progreso)

    if args.listar_idiomas:
        print("\nIdiomas disponibles:")
        for cod, nombre in IDIOMAS.items():
            print(f"  {cod:<12} {nombre}")
        return

    if not args.archivo:
        parser.print_help()
        return

    ruta_txt = Path(args.archivo)
    if not ruta_txt.exists():
        print(f"[X] Archivo no encontrado: {ruta_txt}", flush=True)
        sys.exit(1)

    carpeta = Path(args.salida)
    carpeta.mkdir(parents=True, exist_ok=True)

    nombre_base   = args.nombre or ruta_txt.stem
    titulo_novela = nombre_base.replace("-", " ").replace("_", " ").title()
    extension     = ".pdf" if args.formato_salida == "pdf" else f"_{args.idioma}.txt"
    ruta_salida   = carpeta / f"{nombre_base}{extension}"

    print(f"[i] Leyendo: {ruta_txt}", flush=True)
    caps = parsear_txt(ruta_txt)
    print(f"[OK] {len(caps)} capitulos encontrados.", flush=True)

    if not caps:
        print("[X] No se encontraron capitulos.", flush=True)
        sys.exit(1)

    idioma_nombre = IDIOMAS.get(args.idioma, args.idioma)
    print(f"[i] Traduciendo al {idioma_nombre}...\n", flush=True)
    caps = traducir_capitulos(caps, args.idioma)

    print(f"\n[i] Exportando como {args.formato_salida.upper()}...", flush=True)
    exportar_traducido(caps, args.formato_salida, ruta_salida, titulo_novela, args.idioma)
    print(f"\n[OK] Listo: {ruta_salida}", flush=True)


if __name__ == "__main__":
    main()