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

Estrategia anti-bot:
    --anti-bot auto          → escalación automática (0→1→2, luego pide manual)
    --anti-bot 3             → nivel fijo 3 (Cookies), requiere --cookies
    --anti-bot 5             → nivel fijo 5 (Chrome real), requiere --chrome-port
    --nivel-max 4            → límite máximo para modo auto
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Forzar UTF-8 en Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from core import exportar, perfiles as pm
from core.anti_bot import AntiBotManager
from core.scraper import NovelScraper, set_modo_progreso


def _cargar_cookies(ruta_str: str) -> list[dict]:
    """Lee un archivo JSON de cookies y lo devuelve como lista."""
    ruta = Path(ruta_str)
    if not ruta.exists():
        print(f"[X] Archivo de cookies no encontrado: {ruta}", flush=True)
        sys.exit(1)
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if isinstance(datos, list):
            return datos
        if isinstance(datos, dict) and "cookies" in datos:
            return datos["cookies"]
        print("[X] Formato de cookies no reconocido. Debe ser una lista JSON.", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"[X] Error leyendo cookies: {e}", flush=True)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Scraper multi-sitio de novelas web con evasión anti-bot progresiva.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", nargs="?", default="",
                        help="URL del indice o primer capitulo")
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

    # ── Anti-bot ─────────────────────────────────────────────────────────────
    parser.add_argument("--anti-bot",        "-a", default="auto",
                        metavar="MODO",
                        help="Estrategia anti-bot: 'auto' | 0-5 (nivel fijo)")
    parser.add_argument("--nivel-max",       "-m", type=int, default=5,
                        metavar="N",
                        help="Nivel máximo permitido en modo auto (default: 5)")
    parser.add_argument("--chrome-port",     type=int, default=0,
                        metavar="PUERTO",
                        help="Puerto CDP para Chrome real (nivel 5). "
                             "Ej: chrome.exe --remote-debugging-port=9222")
    parser.add_argument("--cookies",         default="",
                        metavar="archivo.json",
                        help="Archivo JSON con cookies a inyectar (niveles 3+)")
    parser.add_argument("--visible",         action="store_true",
                        help="Forzar navegador visible (requerido para nivel 4)")
    parser.add_argument("--progreso",        action="store_true",
                        help="Emitir lineas PROGRESO: para la GUI")

    # ── Compatibilidad (deprecados) ─────────────────────────────────────────
    parser.add_argument("--resolver-cf",     action="store_true",
                        help=argparse.SUPPRESS)  # oculto, redirigido a --anti-bot 4

    args = parser.parse_args()

    set_modo_progreso(args.progreso)
    todos = pm.cargar_todos()

    # ── Migrar flags deprecados ──────────────────────────────────────────────
    if args.resolver_cf:
        print("[!] --resolver-cf esta deprecado. Usa --anti-bot 4 --visible",
              flush=True)
        if args.anti_bot == "auto":
            args.anti_bot = "4"
        args.visible = True

    # ── Configurar AntiBotManager ────────────────────────────────────────────
    cookies = _cargar_cookies(args.cookies) if args.cookies else []
    if cookies:
        print(f"[i] Cookies cargadas: {len(cookies)} cookies", flush=True)

    anti_bot = AntiBotManager(
        modo=args.anti_bot,
        nivel_max=args.nivel_max,
        cookies=cookies,
        chrome_port=args.chrome_port,
    )

    # Validar configuración
    if anti_bot.requiere_visible and not args.visible:
        print("[!] El nivel actual requiere navegador visible. Activando --visible.",
              flush=True)
        args.visible = True

    if anti_bot.requiere_cdp and not anti_bot.chrome_port:
        print("[X] Nivel 5 (Chrome real) requiere --chrome-port.", flush=True)
        print("    Ej: --chrome-port 9222", flush=True)
        sys.exit(1)

    # ── Listar perfiles ───────────────────────────────────────────────────────
    if args.listar_perfiles:
        print("\nPerfiles disponibles:")
        for p in todos:
            doms = ", ".join(p.get("dominios", [])) or "(fallback)"
            print(f"  {p['id']:<22} {p['nombre']:<25} {doms}")
        print(f"\nSistema anti-bot:")
        print(AntiBotManager.resumen_niveles())
        return

    if not args.url:
        parser.print_help()
        return

    # ── Modo detección ────────────────────────────────────────────────────────
    if args.detectar:
        with NovelScraper(anti_bot=anti_bot) as s:
            nuevo = s.detectar_y_guardar(args.url)
        if nuevo:
            print(f"[OK] Perfil '{nuevo['id']}' guardado.", flush=True)
        return

    # ── Scraping normal ───────────────────────────────────────────────────────
    carpeta = Path(args.salida)
    if args.nombre:
        nombre_base = exportar.limpiar_nombre(args.nombre)
    else:
        slug = re.search(r"/([^/]+?)(?:/chapter|/?$)", args.url)
        nombre_base = exportar.limpiar_nombre(slug.group(1) if slug else "novela")

    nivel = anti_bot.nivel_actual
    print(f"[i] URL: {args.url}", flush=True)
    print(f"[i] Capitulos: {args.capitulos} | Formato: {args.formato}", flush=True)
    print(f"[~] Anti-bot: nivel {nivel.value} ({nivel.nombre_corto()}) | "
          f"modo: {anti_bot.modo_actual}", flush=True)
    if cookies:
        print(f"[i] Cookies inyectadas: {len(cookies)}", flush=True)
    if anti_bot.requiere_cdp:
        print(f"[i] Chrome CDP: puerto {anti_bot.chrome_port}", flush=True)

    with NovelScraper(anti_bot=anti_bot) as s:
        caps = s.scrapear(args.url, args.capitulos, todos, forzar_sitio=args.sitio)

        # Mostrar resumen de escalación
        if len(anti_bot.historial) > 1:
            hist = " → ".join(
                f"{NivelAntiBot(n).nombre_corto()}" for n in anti_bot.historial
            )
            print(f"[~] Historial anti-bot: {hist}", flush=True)

    if not caps:
        print("[X] No se descargo ningun capitulo.", flush=True)
        sys.exit(1)

    print(f"\n[OK] {len(caps)} capitulos descargados.", flush=True)
    exportar.guardar(caps, args.formato, carpeta, nombre_base)


if __name__ == "__main__":
    main()
