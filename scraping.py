"""
NovelBin Scraper
================
Extrae capítulos de novelas desde novelbin.me

Uso:
    python novelbin_scraper.py <url> [opciones]

Ejemplos:
    # Desde el índice de la novela (saca los primeros 10 capítulos)
    python novelbin_scraper.py https://novelbin.me/novel-book/supreme-magus

    # Desde un capítulo específico
    python novelbin_scraper.py https://novelbin.me/novel-book/supreme-magus/chapter-5

    # Cambiar cantidad de capítulos a descargar
    python novelbin_scraper.py https://novelbin.me/novel-book/supreme-magus --capitulos 25

    # Guardar como TXT (por defecto) o JSON
    python novelbin_scraper.py https://novelbin.me/novel-book/supreme-magus --formato json

    # Guardar en carpeta específica
    python novelbin_scraper.py https://novelbin.me/novel-book/supreme-magus --salida ./mis_novelas

Instalación de dependencias:
    pip install playwright
    playwright install chromium
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Forzar UTF-8 en la salida estándar (necesario en Windows con cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: Playwright no está instalado.")
    print("Ejecuta: pip install playwright && playwright install chromium")
    exit(1)


# ─── Configuración ────────────────────────────────────────────────────────────

DELAY_ENTRE_PAGINAS = 2.0   # segundos entre requests (sé amable con el servidor)
TIMEOUT_PAGINA      = 30000  # ms para cargar cada página
MAX_REINTENTOS      = 3      # reintentos si falla una página


# ─── Helpers ──────────────────────────────────────────────────────────────────

def limpiar_nombre_archivo(nombre: str) -> str:
    """Elimina caracteres inválidos para nombres de archivo."""
    return re.sub(r'[\\/*?:"<>|]', "", nombre).strip()


_MODO_PROGRESO = False  # activado por --progreso (GUI)

def log(msg: str, nivel: str = "INFO"):
    iconos = {"INFO": "📖", "OK": "✅", "WARN": "⚠️", "ERROR": "❌", "SKIP": "⏭️"}
    print(f"{iconos.get(nivel, '·')} {msg}", flush=True)

def log_progreso(actual: int, total: int, titulo: str = "", estado: str = "descargando"):
    """Emite una línea JSON de progreso para que la GUI la lea."""
    if _MODO_PROGRESO:
        import json as _json
        data = {"tipo": "progreso", "actual": actual, "total": total,
                "titulo": titulo, "estado": estado}
        print(f"PROGRESO:{_json.dumps(data, ensure_ascii=False)}", flush=True)


# ─── Scraper principal ────────────────────────────────────────────────────────

class NovelBinScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        self._page = context.new_page()
        # Ocultar webdriver flag
        self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return self

    def __exit__(self, *_):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    # ── Detectar tipo de URL ──────────────────────────────────────────────────

    def es_indice(self, url: str) -> bool:
        """Devuelve True si la URL es la página índice de la novela."""
        # Índice: /novel-book/nombre  (sin /chapter-N al final)
        return bool(re.search(r"/novel-book/[^/]+/?$", url))

    # ── Obtener primer capítulo desde el índice ───────────────────────────────

    def obtener_primer_capitulo_desde_indice(self, url_indice: str) -> str | None:
        """Navega al índice y devuelve la URL del primer capítulo."""
        log(f"Cargando índice: {url_indice}")
        self._page.goto(url_indice, timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
        time.sleep(2)

        # Buscar el botón "Read Now" o el primer enlace de capítulo
        selectores = [
            "a.btn-read-now",
            "a[href*='/chapter-']",
            ".chapter-list a",
            "ul.list-chapter a",
        ]
        for sel in selectores:
            try:
                elem = self._page.query_selector(sel)
                if elem:
                    href = elem.get_attribute("href")
                    if href:
                        if href.startswith("/"):
                            href = "https://novelbin.me" + href
                        log(f"Primer capítulo encontrado: {href}", "OK")
                        return href
            except Exception:
                continue

        log("No se encontró el primer capítulo en el índice.", "ERROR")
        return None

    # ── Extraer contenido de un capítulo ─────────────────────────────────────

    def extraer_capitulo(self, url: str) -> dict | None:
        """Extrae título y texto de un capítulo. Retorna dict o None si falla."""
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                self._page.goto(url, timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
                time.sleep(1.5)

                # Título del capítulo
                titulo = ""
                for sel in ["h2", ".chr-title", ".chapter-title", "title"]:
                    elem = self._page.query_selector(sel)
                    if elem:
                        titulo = elem.inner_text().strip()
                        break

                # Contenido del capítulo
                texto = ""
                for sel in ["#chr-content", ".chr-c", "#chapter-content", ".chapter-content"]:
                    elem = self._page.query_selector(sel)
                    if elem:
                        # Eliminar anuncios internos si los hay
                        for ad in elem.query_selector_all(".ads, .ad, script, .adsbox"):
                            ad.evaluate("el => el.remove()")
                        texto = elem.inner_text().strip()
                        break

                if not texto:
                    # Último recurso: body completo sin nav/header/footer
                    for sel in ["nav", "header", "footer", ".navbar", ".sidebar"]:
                        for el in self._page.query_selector_all(sel):
                            el.evaluate("el => el.remove()")
                    texto = self._page.inner_text("body").strip()

                # URL del siguiente capítulo
                siguiente = None
                for sel in ["a.next_page", "a[rel='next']", ".next-chap", "a:has-text('Next')", "a:has-text('next chapter')"]:
                    try:
                        elem = self._page.query_selector(sel)
                        if elem:
                            href = elem.get_attribute("href")
                            if href and "chapter" in href:
                                siguiente = href if href.startswith("http") else "https://novelbin.me" + href
                                break
                    except Exception:
                        continue

                return {"titulo": titulo, "url": url, "texto": texto, "siguiente": siguiente}

            except PlaywrightTimeout:
                log(f"Timeout en intento {intento}/{MAX_REINTENTOS}: {url}", "WARN")
                if intento < MAX_REINTENTOS:
                    time.sleep(3 * intento)
            except Exception as e:
                log(f"Error en intento {intento}/{MAX_REINTENTOS}: {e}", "WARN")
                if intento < MAX_REINTENTOS:
                    time.sleep(3 * intento)

        log(f"No se pudo extraer: {url}", "ERROR")
        return None

    # ── Método principal ──────────────────────────────────────────────────────

    def scrapear(self, url_inicio: str, num_capitulos: int) -> list[dict]:
        """Descarga `num_capitulos` capítulos a partir de `url_inicio`."""
        url_actual = url_inicio

        # Si nos pasan el índice, buscar el primer capítulo
        if self.es_indice(url_actual):
            url_actual = self.obtener_primer_capitulo_desde_indice(url_actual)
            if not url_actual:
                return []

        capitulos = []
        for i in range(1, num_capitulos + 1):
            log(f"[{i}/{num_capitulos}] {url_actual}")
            log_progreso(i, num_capitulos, estado="descargando")
            cap = self.extraer_capitulo(url_actual)

            if not cap:
                log(f"Deteniendo scraping (fallo en capítulo {i}).", "ERROR")
                log_progreso(i, num_capitulos, estado="error")
                break

            capitulos.append(cap)
            log(f'  → "{cap["titulo"][:60]}"', "OK")
            log_progreso(i, num_capitulos, titulo=cap["titulo"], estado="ok")

            if i < num_capitulos:
                if cap["siguiente"]:
                    url_actual = cap["siguiente"]
                    time.sleep(DELAY_ENTRE_PAGINAS)
                else:
                    log("No hay capítulo siguiente. Fin de la novela.", "SKIP")
                    log_progreso(i, num_capitulos, estado="fin")
                    break

        return capitulos


# ─── Guardar resultados ───────────────────────────────────────────────────────

def guardar_txt(capitulos: list[dict], ruta: Path):
    """Guarda todos los capítulos en un único archivo TXT."""
    with open(ruta, "w", encoding="utf-8") as f:
        for cap in capitulos:
            f.write(f"\n{'='*70}\n")
            f.write(f"{cap['titulo']}\n")
            f.write(f"{'='*70}\n\n")
            f.write(cap["texto"])
            f.write("\n\n")
    log(f"Guardado TXT: {ruta}", "OK")


def guardar_json(capitulos: list[dict], ruta: Path):
    """Guarda los capítulos como JSON estructurado."""
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(capitulos, f, ensure_ascii=False, indent=2)
    log(f"Guardado JSON: {ruta}", "OK")


def guardar_capitulos_separados(capitulos: list[dict], carpeta: Path):
    """Guarda cada capítulo en su propio archivo TXT."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for i, cap in enumerate(capitulos, 1):
        nombre = limpiar_nombre_archivo(f"{i:04d}_{cap['titulo'][:60]}.txt")
        ruta = carpeta / nombre
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(f"{cap['titulo']}\n{'='*60}\n\n{cap['texto']}\n")
    log(f"Guardados {len(capitulos)} capítulos en: {carpeta}", "OK")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scraper de novelas para novelbin.me",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("url", help="URL del índice o del primer capítulo")
    parser.add_argument(
        "--capitulos", "-c", type=int, default=10,
        help="Cantidad de capítulos a descargar (default: 10)"
    )
    parser.add_argument(
        "--formato", "-f", choices=["txt", "json", "separados"], default="txt",
        help="Formato de salida: txt (un archivo), json, separados (un TXT por capítulo)"
    )
    parser.add_argument(
        "--salida", "-o", default="./novelas",
        help="Carpeta de salida (default: ./novelas)"
    )
    parser.add_argument(
        "--nombre", "-n", default="",
        help="Nombre personalizado para el archivo de salida (sin extensión)"
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Mostrar el navegador (útil para depurar)"
    )
    parser.add_argument(
        "--progreso", action="store_true",
        help="Emitir líneas JSON de progreso (usado por la GUI)"
    )

    args = parser.parse_args()

    global _MODO_PROGRESO
    _MODO_PROGRESO = args.progreso

    # Crear carpeta de salida
    carpeta_salida = Path(args.salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    # Nombre base: usa --nombre si se pasó, si no deriva de la URL
    if args.nombre:
        nombre_base = limpiar_nombre_archivo(args.nombre)
    else:
        slug = re.search(r"/novel-book/([^/]+)", args.url)
        nombre_base = limpiar_nombre_archivo(slug.group(1) if slug else "novela")

    log(f"Iniciando scraper → {args.url}")
    log(f"Capítulos a descargar: {args.capitulos}")
    log(f"Formato: {args.formato} | Salida: {carpeta_salida}")
    print()

    with NovelBinScraper(headless=not args.visible) as scraper:
        capitulos = scraper.scrapear(args.url, args.capitulos)

    if not capitulos:
        log("No se descargó ningún capítulo.", "ERROR")
        return

    log(f"\nDescargados {len(capitulos)} capítulos.", "OK")

    # Guardar según formato elegido
    if args.formato == "txt":
        guardar_txt(capitulos, carpeta_salida / f"{nombre_base}.txt")
    elif args.formato == "json":
        guardar_json(capitulos, carpeta_salida / f"{nombre_base}.json")
    elif args.formato == "separados":
        guardar_capitulos_separados(capitulos, carpeta_salida / nombre_base)


if __name__ == "__main__":
    main()