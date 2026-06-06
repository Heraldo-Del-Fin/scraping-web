"""
scraper_cli.py
--------------
Punto de entrada CLI para el scraper.
La GUI lo llama como subproceso; también funciona desde la terminal.

Uso:
    python scraper_cli.py <url> [opciones]
    python scraper_cli.py https://novelbin.me/novel-book/supreme-magus --capitulos 20
    python scraper_cli.py <url> --detectar
    python scraper_cli.py --listar-perfiles
"""

import argparse
import re
import sys
from pathlib import Path

# Forzar UTF-8 en Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Asegurar que el directorio raíz del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).parent))

from core import exportar, perfiles as pm
from core.scraper import NovelScraper, set_modo_progreso


def main():
    parser = argparse.ArgumentParser(
        description="Scraper multi-sitio de novelas web",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", nargs="?", default="",
                        help="URL del índice o primer capítulo")
    parser.add_argument("--capitulos",       "-c", type=int, default=10)
    parser.add_argument("--formato",         "-f",
                        choices=["txt", "json", "separados"], default="txt")
    parser.add_argument("--salida",          "-o", default="./novelas")
    parser.add_argument("--nombre",          "-n", default="")
    parser.add_argument("--sitio",           "-s", default="",
                        help="Forzar perfil por ID (ej: royalroad)")
    parser.add_argument("--detectar",        action="store_true",
                        help="Detectar selectores y guardar perfil en perfiles.json")
    parser.add_argument("--listar-perfiles", action="store_true")
    parser.add_argument("--visible",         action="store_true")
    parser.add_argument("--progreso",        action="store_true",
                        help="Emitir líneas PROGRESO: para la GUI")
    args = parser.parse_args()

    set_modo_progreso(args.progreso)
    todos = pm.cargar_todos()

    # ── Listar perfiles ───────────────────────────────────────────────────────
    if args.listar_perfiles:
        print("\nPerfiles disponibles:")
        for p in todos:
            doms = ", ".join(p.get("dominios", [])) or "(fallback)"
            print(f"  {p['id']:<22} {p['nombre']:<25} {doms}")
        return

    if not args.url:
        parser.print_help()
        return

    # ── Modo detección ────────────────────────────────────────────────────────
    if args.detectar:
        with NovelScraper(headless=not args.visible) as s:
            nuevo = s.detectar_y_guardar(args.url)
        if nuevo:
            print(f"[OK] Perfil '{nuevo['id']}' guardado. Ya puedes scrapear.", flush=True)
        return

    # ── Scraping normal ───────────────────────────────────────────────────────
    carpeta = Path(args.salida)
    if args.nombre:
        nombre_base = exportar.limpiar_nombre(args.nombre)
    else:
        slug = re.search(r"/([^/]+?)(?:/chapter|/?$)", args.url)
        nombre_base = exportar.limpiar_nombre(slug.group(1) if slug else "novela")

    print(f"[i] URL: {args.url}", flush=True)
    print(f"[i] Capitulos: {args.capitulos} | Formato: {args.formato}", flush=True)

    with NovelScraper(headless=not args.visible) as s:
        caps = s.scrapear(args.url, args.capitulos, todos, forzar_sitio=args.sitio)

    if not caps:
        print("[X] No se descargo ningun capitulo.", flush=True)
        sys.exit(1)

    print(f"\n[OK] {len(caps)} capitulos descargados.", flush=True)
    exportar.guardar(caps, args.formato, carpeta, nombre_base)


if __name__ == "__main__":
    main()