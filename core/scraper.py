"""
core/scraper.py
---------------
Clase NovelScraper: navega sitios de novelas con Patchright (Playwright
reforzado contra detección de bots), usa perfiles de core/perfiles.py
para adaptar los selectores.
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
    from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: Patchright no instalado. Ejecuta: pip install patchright && patchright install chromium")
    raise

from core.perfiles import buscar_por_url, guardar_perfil, perfil_generico

# ── Constantes ────────────────────────────────────────────────────────────────

TIMEOUT_MS     = 30_000
MAX_REINTENTOS = 3

PERFIL_NAVEGADOR = Path(__file__).parent.parent / ".browser_profile"

# Marcadores de retos anti-bot conocidos (Cloudflare, DataDome, etc.)
MARCADORES_DESAFIO = [
    "just a moment",
    "attention required",
    "checking your browser",
    "verifying you are human",
    "un momento",
]
SELECTORES_DESAFIO = [
    "iframe[src*='challenges.cloudflare.com']",
    "#challenge-form",
    "#challenge-running",
]

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
        self._ctx       = None
        self._page      = None
        self._perfil    = None   # se asigna en scrapear()

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self._pw = sync_playwright().start()
        # Perfil persistente + sin personalizar user-agent/viewport: patchright
        # queda mejor "camuflado" dejando que Chromium use su huella por defecto.
        PERFIL_NAVEGADOR.mkdir(parents=True, exist_ok=True)
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(PERFIL_NAVEGADOR),
            headless=self.headless,
            no_viewport=True,
            args=["--no-sandbox"],
        )
        self._page = self._ctx.new_page()
        return self

    def __exit__(self, *_):
        if self._ctx: self._ctx.close()
        if self._pw:  self._pw.stop()

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

    # ── Detección y espera de retos anti-bot ──────────────────────────────────

    def _hay_desafio_activo(self) -> bool:
        try:
            titulo = (self._page.title() or "").lower()
        except Exception:
            return False
        if any(m in titulo for m in MARCADORES_DESAFIO):
            return True
        try:
            return self._page.query_selector(", ".join(SELECTORES_DESAFIO)) is not None
        except Exception:
            return False

    def _esperar_desafio(self, espera_max: float = 12.0) -> bool:
        """
        Si la página muestra un reto anti-bot (Cloudflare, etc.), espera a que
        se resuelva solo. Con un navegador no detectado, la mayoría de los
        retos "managed" se resuelven en pocos segundos sin intervención.
        Devuelve True si no había reto o si se resolvió a tiempo.
        """
        if not self._hay_desafio_activo():
            return True

        log("Reto anti-bot detectado, esperando resolución automática...", "WARN")
        transcurrido = 0.0
        paso = 1.0
        while transcurrido < espera_max:
            time.sleep(paso)
            transcurrido += paso
            if not self._hay_desafio_activo():
                log("Reto anti-bot resuelto.", "OK")
                return True

        log("El reto anti-bot no se resolvió a tiempo.", "ERROR")
        return False

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
        if not self._esperar_desafio():
            return None

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
                if not self._esperar_desafio():
                    raise RuntimeError("Reto anti-bot sin resolver")

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
            self._esperar_desafio()  # best-effort: seguimos aunque no se resuelva
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

            # Salvaguarda: contenido idéntico al capítulo anterior.
            # Pasa cuando el sitio bloquea/atasca la página (ej. un reto anti-bot
            # que no se resuelve) pero la URL "siguiente" sigue avanzando por el
            # fallback de incremento — sin esto se guardarían N copias del mismo
            # capítulo en vez de detenerse.
            if capitulos and (cap["titulo"], cap["texto"]) == (capitulos[-1]["titulo"], capitulos[-1]["texto"]):
                log("Contenido idéntico al capítulo anterior (posible bloqueo o "
                    "selector roto). Deteniendo.", "ERROR")
                log_progreso(i, num_capitulos, estado="error")
                break

            capitulos.append(cap)
            log(f'  -> "{cap["titulo"][:65]}"', "OK")
            log_progreso(i, num_capitulos, titulo=cap["titulo"], estado="ok")

            if i < num_capitulos:
                if not cap["siguiente"]:
                    log("No hay capítulo siguiente. Fin de la novela.", "SKIP")
                    log_progreso(i, num_capitulos, estado="fin")
                    break
                # Salvaguarda: el enlace "siguiente" apunta al capítulo actual
                # (selector roto que engancha un link fijo de la página, ej. un
                # widget de navegación que siempre apunta al mismo capítulo).
                if cap["siguiente"] == url_actual:
                    log("El enlace 'siguiente' apunta al mismo capítulo "
                        "(selector roto). Deteniendo.", "ERROR")
                    log_progreso(i, num_capitulos, estado="error")
                    break
                url_actual = cap["siguiente"]
                time.sleep(delay)

        return capitulos