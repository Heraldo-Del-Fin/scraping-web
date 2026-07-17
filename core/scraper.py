"""
core/scraper.py
---------------
Clase NovelScraper: navega sitios de novelas con Playwright,
usa perfiles de core/perfiles.py para adaptar los selectores.
"""

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

# Forzar UTF-8 en Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: Playwright no instalado. Ejecuta: pip install playwright && playwright install chromium")
    raise

from core.perfiles import buscar_por_url, guardar_perfil, perfil_generico

# ── Constantes ────────────────────────────────────────────────────────────────

TIMEOUT_MS     = 30_000
MAX_REINTENTOS = 3

# ── Logger simple (compatible con el sistema PROGRESO: de la GUI) ─────────────

_modo_progreso = False   # se activa con set_modo_progreso(True)

def set_modo_progreso(activo: bool):
    global _modo_progreso
    _modo_progreso = activo

def log(msg: str, nivel: str = "INFO"):
    iconos = {"INFO": "[i]", "OK": "[OK]", "WARN": "[!]", "ERROR": "[X]", "SKIP": "[>>]"}
    print(f"{iconos.get(nivel, '·')} {msg}", flush=True)

def log_progreso(actual: int, total: int, titulo: str = "", estado: str = "ok"):
    if _modo_progreso:
        data = {"tipo": "progreso", "actual": actual, "total": total,
                "titulo": titulo, "estado": estado}
        print(f"PROGRESO:{json.dumps(data, ensure_ascii=False)}", flush=True)


# ── Clase principal ───────────────────────────────────────────────────────────

class NovelScraper:
    """
    Uso:
        with NovelScraper(headless=True) as s:
            caps = s.scrapear(url, num_caps, perfiles)
    """

    def __init__(self, headless: bool = True):
        self.headless   = headless
        self._pw        = None
        self._browser   = None
        self._page      = None
        self._perfil    = None   # se asigna en scrapear()

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        self._page = ctx.new_page()
        self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return self

    def __exit__(self, *_):
        if self._browser:  self._browser.close()
        if self._pw:       self._pw.stop()

    # ── Utilidades internas ───────────────────────────────────────────────────

    def _sels(self, tipo: str) -> list[str]:
        return self._perfil["selectores"].get(tipo, [])

    def _base_url(self) -> str:
        return self._perfil["opciones"].get("base_url", "")

    def _resolver_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith("http"):
            return href
        base = self._base_url()
        return (base.rstrip("/") + "/" + href.lstrip("/")) if base else href

    def _primer_elem(self, selectores: list[str]):
        for sel in selectores:
            try:
                elem = self._page.query_selector(sel)
                if elem:
                    return elem
            except Exception:
                continue
        return None

    def _esperar_carga(self):
        time.sleep(self._perfil["opciones"].get("espera_carga", 1.5))

    # ── Detección de tipo de URL ──────────────────────────────────────────────

    def _es_indice(self, url: str) -> bool:
        patron = self._perfil.get("patron_indice", "")
        if patron:
            return bool(re.search(patron, url))
        return "chapter" not in url.lower()

    # ── Obtener primer capítulo desde página índice ───────────────────────────

    def _primer_capitulo_desde_indice(self, url: str) -> str | None:
        log(f"Cargando índice: {url}")
        self._page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
        self._esperar_carga()

        elem = self._primer_elem(self._sels("indice_primer_cap"))
        if elem:
            href = self._resolver_url(elem.get_attribute("href") or "")
            if href:
                log(f"Primer capítulo: {href}", "OK")
                return href

        log("No se encontró el primer capítulo en el índice.", "ERROR")
        return None

    # ── Extraer un capítulo ───────────────────────────────────────────────────

    def _extraer_capitulo(self, url: str) -> dict | None:
        espera = self._perfil["opciones"].get("espera_carga", 1.5)

        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                self._page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
                time.sleep(espera)

                # Título
                titulo = ""
                elem = self._primer_elem(self._sels("titulo"))
                if elem:
                    titulo = elem.inner_text().strip()

                # Contenido (eliminar anuncios primero)
                texto = ""
                solo_parrafos = self._perfil.get("opciones", {}).get("solo_parrafos", False)
                for sel in self._sels("contenido"):
                    try:
                        elem = self._page.query_selector(sel)
                        if not elem:
                            continue
                        for ad in self._sels("eliminar_anuncios"):
                            for node in elem.query_selector_all(ad):
                                node.evaluate("el => el.remove()")
                        if solo_parrafos:
                            parrafos = elem.query_selector_all("p")
                            texto = "\n\n".join(
                                p.inner_text().strip()
                                for p in parrafos
                                if p.inner_text().strip()
                            )
                        else:
                            texto = elem.inner_text().strip()
                        if len(texto) > 100:
                            break
                    except Exception:
                        continue

                # Fallback: body sin chrome del sitio
                if len(texto) < 100:
                    for sel in ["nav", "header", "footer", ".navbar", ".sidebar", ".ads"]:
                        for el in self._page.query_selector_all(sel):
                            try: el.evaluate("el => el.remove()")
                            except: pass
                    texto = self._page.inner_text("body").strip()

                # Siguiente capítulo — selectores primero
                siguiente = None
                for sel in self._sels("siguiente"):
                    try:
                        elem = self._page.query_selector(sel)
                        if elem:
                            href = elem.get_attribute("href")
                            if href:
                                siguiente = self._resolver_url(href)
                                break
                    except Exception:
                        continue

                # Fallback: incrementar el número de capítulo en la URL
                # Funciona con patrones como /chapter/5/, /chapter-5, /chapter_5
                if not siguiente:
                    siguiente = self._siguiente_por_incremento(url)
                    if siguiente:
                        log(f"  Siguiente inferido por URL: {siguiente}", "WARN")

                return {"titulo": titulo, "url": url, "texto": texto, "siguiente": siguiente}

            except PlaywrightTimeout:
                log(f"Timeout intento {intento}/{MAX_REINTENTOS}: {url}", "WARN")
                if intento < MAX_REINTENTOS: time.sleep(3 * intento)
            except Exception as e:
                log(f"Error intento {intento}/{MAX_REINTENTOS}: {e}", "WARN")
                if intento < MAX_REINTENTOS: time.sleep(3 * intento)

        log(f"No se pudo extraer: {url}", "ERROR")
        return None

    # ── Fallback: siguiente capítulo por incremento de URL ───────────────────

    def _siguiente_por_incremento(self, url: str) -> str | None:
        """
        Intenta construir la URL del siguiente capítulo incrementando
        el número en la URL actual.
        Soporta patrones: /chapter/5/, /chapter-5, /chapter_5, /chapter/5
        """
        patrones = [
            r'(/chapter/)(\d+)(/?$)',        # /chapter/5/ o /chapter/5
            r'(/chapter-)(\d+)(/?(?:\?.*)?$)',  # /chapter-5
            r'(/chapter_)(\d+)(/?(?:\?.*)?$)',  # /chapter_5
            r'(-chapter-)(\d+)(/?(?:\?.*)?$)',  # -chapter-5
        ]
        for patron in patrones:
            m = re.search(patron, url)
            if m:
                num_actual = int(m.group(2))
                nueva_url = (
                    url[: m.start()]
                    + m.group(1)
                    + str(num_actual + 1)
                    + m.group(3)
                )
                return nueva_url
        return None

    # ── Detección automática de selectores ───────────────────────────────────

    def detectar_y_guardar(self, url: str) -> dict | None:
        """
        Visita una URL, prueba selectores genéricos y guarda el perfil
        detectado en perfiles.json. Devuelve el perfil creado o None.
        """
        log(f"Detectando selectores en: {url}")
        dominio = urlparse(url).netloc.lower()
        self._perfil = perfil_generico()

        try:
            self._page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
            self._esperar_carga()
        except Exception as e:
            log(f"No se pudo cargar la página: {e}", "ERROR")
            return None

        gen_sels = perfil_generico()["selectores"]
        detectados = {}

        for tipo in ["titulo", "contenido", "siguiente"]:
            for sel in gen_sels[tipo]:
                try:
                    elem = self._page.query_selector(sel)
                    if elem and len(elem.inner_text().strip()) > 10:
                        detectados[tipo] = sel
                        log(f"  {tipo}: '{sel}'", "OK")
                        break
                except Exception:
                    continue
            if tipo not in detectados:
                log(f"  {tipo}: no detectado, se usará genérico", "WARN")

        nuevo = {
            "id":              dominio.lstrip("www.").replace(".", "_"),
            "nombre":          dominio.lstrip("www.").split(".")[0].capitalize(),
            "dominios":        [dominio, "www." + dominio],
            "activo":          True,
            "descripcion":     f"Perfil detectado automáticamente para {dominio}",
            "patron_indice":   "",
            "patron_capitulo": "",
            "selectores": {
                "titulo":            [detectados.get("titulo", "h1")],
                "contenido":         [detectados.get("contenido", ".chapter-content")],
                "siguiente":         [detectados.get("siguiente", "a[rel='next']")],
                "indice_primer_cap": gen_sels["indice_primer_cap"],
                "eliminar_anuncios": gen_sels["eliminar_anuncios"],
            },
            "opciones": {
                "delay_entre_paginas": 2.5,
                "espera_carga":        2.0,
                "base_url":            f"https://{dominio}",
            },
        }
        guardar_perfil(nuevo)
        log(f"Perfil '{nuevo['id']}' guardado en perfiles.json", "OK")
        return nuevo

    # ── Método público principal ──────────────────────────────────────────────

    def scrapear(
        self,
        url_inicio: str,
        num_capitulos: int,
        perfiles: list[dict],
        forzar_sitio: str = "",
    ) -> list[dict]:
        """
        Descarga `num_capitulos` capítulos empezando en `url_inicio`.
        Devuelve lista de dicts {titulo, url, texto, siguiente}.
        """
        self._perfil = buscar_por_url(url_inicio, perfiles, forzar_id=forzar_sitio)
        log(f"Perfil activo: {self._perfil['nombre']}")
        delay = self._perfil["opciones"].get("delay_entre_paginas", 2.0)

        url_actual = url_inicio
        if self._es_indice(url_actual):
            url_actual = self._primer_capitulo_desde_indice(url_actual)
            if not url_actual:
                return []

        capitulos = []
        for i in range(1, num_capitulos + 1):
            log(f"[{i}/{num_capitulos}] {url_actual}")
            log_progreso(i, num_capitulos, estado="descargando")

            cap = self._extraer_capitulo(url_actual)
            if not cap:
                log(f"Fallo en capítulo {i}. Deteniendo.", "ERROR")
                log_progreso(i, num_capitulos, estado="error")
                break

            capitulos.append(cap)
            log(f'  -> "{cap["titulo"][:65]}"', "OK")
            log_progreso(i, num_capitulos, titulo=cap["titulo"], estado="ok")

            if i < num_capitulos:
                if cap["siguiente"]:
                    url_actual = cap["siguiente"]
                    time.sleep(delay)
                else:
                    log("No hay capítulo siguiente. Fin de la novela.", "SKIP")
                    log_progreso(i, num_capitulos, estado="fin")
                    break

        return capitulos