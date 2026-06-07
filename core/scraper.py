"""
core/scraper.py
---------------
Clase NovelScraper: navega sitios de novelas con Playwright.
Usa core.anti_bot.AntiBotManager para evasión progresiva de bots.
"""

import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: Playwright no instalado. Ejecuta: pip install playwright && playwright install chromium")
    raise

try:
    from playwright_stealth import stealth_sync
    _STEALTH_DISPONIBLE = True
except ImportError:
    _STEALTH_DISPONIBLE = False

from core.anti_bot import AntiBotManager, NivelAntiBot, CLOUDFLARE_MARKERS
from core.perfiles import buscar_por_url, guardar_perfil, perfil_generico


# ── Constantes ────────────────────────────────────────────────────────────────

TIMEOUT_MS     = 35_000
MAX_REINTENTOS = 3

# User-agents rotativos (Chrome en Windows, Mac y Linux)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Resoluciones de pantalla comunes
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
]


# ── Logger ────────────────────────────────────────────────────────────────────

_modo_progreso = False

def set_modo_progreso(activo: bool):
    global _modo_progreso
    _modo_progreso = activo

def log(msg: str, nivel: str = "INFO"):
    iconos = {
        "INFO":  "[i]",
        "OK":    "[OK]",
        "WARN":  "[!]",
        "ERROR": "[X]",
        "SKIP":  "[>>]",
        "BOT":   "[~]",
    }
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
        with NovelScraper(anti_bot=AntiBotManager(...)) as s:
            caps = s.scrapear(url, num_caps, perfiles)
    """

    def __init__(self, anti_bot: AntiBotManager = None):
        """
        anti_bot : instancia de AntiBotManager que controla la estrategia
                   de evasión. Si no se pasa, se usa una por defecto (nivel 0).
        """
        self.anti_bot = anti_bot or AntiBotManager(modo=0)
        self._pw      = None
        self._browser = None
        self._ctx     = None
        self._page    = None
        self._perfil  = None
        self._modo_cdp = self.anti_bot.requiere_cdp

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self._pw = sync_playwright().start()

        if self._modo_cdp:
            self._conectar_chrome_real()
        else:
            self._lanzar_chromium()

        return self

    def _conectar_chrome_real(self):
        """Conecta a un Chrome real vía CDP (nivel 5)."""
        url_cdp = f"http://localhost:{self.anti_bot.chrome_port}"
        log(f"Conectando a Chrome real en {url_cdp} ...", "BOT")
        try:
            self._browser = self._pw.chromium.connect_over_cdp(url_cdp)
            contextos = self._browser.contexts
            if contextos:
                self._ctx  = contextos[0]
                paginas    = self._ctx.pages
                self._page = paginas[0] if paginas else self._ctx.new_page()
            else:
                self._ctx  = self._browser.new_context()
                self._page = self._ctx.new_page()

            log("Conectado a Chrome real. TLS fingerprint nativo activo.", "OK")
            log("Las cookies y sesion de tu Chrome se usaran automaticamente.", "BOT")

            if self.anti_bot.cookies:
                self._inyectar_cookies()

        except Exception as e:
            log(f"No se pudo conectar a Chrome en puerto {self.anti_bot.chrome_port}: {e}", "ERROR")
            log(f"Asegurate de que Chrome este abierto con --remote-debugging-port={self.anti_bot.chrome_port}", "ERROR")
            raise

    def _lanzar_chromium(self):
        """Lanza Chromium aplicando medidas según el nivel anti-bot configurado."""
        headless = not self.anti_bot.requiere_visible

        # Nivel 0 (Básico): argumentos anti-automatización
        args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
        ]

        self._browser = self._pw.chromium.launch(headless=headless, args=args)

        # Nivel 0: user-agent rotativo, viewport aleatorio, headers realistas
        self._ctx = self._browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=random.choice(VIEWPORTS),
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language":           "en-US,en;q=0.9",
                "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Encoding":           "gzip, deflate, br",
                "Connection":                "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest":            "document",
                "Sec-Fetch-Mode":            "navigate",
                "Sec-Fetch-Site":            "none",
                "Sec-Fetch-User":            "?1",
            },
        )
        self._page = self._ctx.new_page()

        # Nivel 1 (Stealth JS)
        if self.anti_bot.nivel_actual >= NivelAntiBot.STEALTH_JS:
            if _STEALTH_DISPONIBLE:
                stealth_sync(self._page)
                log("playwright-stealth activo (nivel 1)", "BOT")
            else:
                self._aplicar_stealth_manual()
                log("Stealth manual activo (nivel 1) — playwright-stealth no instalado", "WARN")

        # Nivel 3+ (Cookies)
        if self.anti_bot.cookies:
            self._inyectar_cookies()

        # Nivel 4 (Interactivo)
        if self.anti_bot.requiere_visible:
            log("Navegador visible activo para resolucion interactiva (nivel 4+)", "BOT")

    def __exit__(self, *_):
        if self._browser: self._browser.close()
        if self._pw:      self._pw.stop()

    # ── Stealth manual (fallback del nivel 1) ─────────────────────────────────

    def _aplicar_stealth_manual(self):
        """Parches JS básicos de evasión cuando playwright-stealth no está disponible."""
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.call(this, parameter);
            };
        """)

    # ── Comportamiento humano (nivel 2) ───────────────────────────────────────

    def _delay_humano(self, base: float = None, variacion: float = 1.5):
        """Espera aleatoria. Si nivel >= 2, añade más variación."""
        if base is None:
            base = self._perfil["opciones"].get("espera_carga", 2.0) if self._perfil else 2.0

        # Nivel 2+: comportamiento humano con delays variables
        if self.anti_bot.nivel_actual >= NivelAntiBot.COMPORTAMIENTO:
            tiempo = max(0.8, base + random.uniform(-variacion * 0.3, variacion))
        else:
            tiempo = max(0.5, base)
        time.sleep(tiempo)

    def _scroll_humano(self):
        """Scroll gradual como lector real. Solo se ejecuta en nivel >= 2."""
        if self.anti_bot.nivel_actual < NivelAntiBot.COMPORTAMIENTO:
            return
        try:
            altura = self._page.evaluate("document.body.scrollHeight")
            if not altura or altura < 500:
                return

            pos = 0
            while pos < altura:
                paso = random.randint(200, 600)
                pos = min(pos + paso, altura)
                self._page.evaluate(f"window.scrollTo({{top: {pos}, behavior: 'smooth'}})")
                time.sleep(random.uniform(0.08, 0.25))

                if random.random() < 0.15:
                    time.sleep(random.uniform(0.5, 1.5))

                if random.random() < 0.08:
                    pos = max(0, pos - random.randint(50, 150))
                    self._page.evaluate(f"window.scrollTo({{top: {pos}, behavior: 'smooth'}})")
                    time.sleep(random.uniform(0.1, 0.3))

            self._page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            time.sleep(random.uniform(0.3, 0.7))
        except Exception:
            pass

    def _mover_mouse(self):
        """Mueve el mouse aleatoriamente (nivel 2+)."""
        if self.anti_bot.nivel_actual < NivelAntiBot.COMPORTAMIENTO:
            return
        try:
            vp = self._ctx.pages[0].viewport_size or {"width": 1280, "height": 800}
            x = random.randint(100, vp["width"] - 100)
            y = random.randint(100, vp["height"] - 100)
            self._page.mouse.move(x, y)
        except Exception:
            pass

    def _aceptar_cookies(self):
        """Cierra banners de cookies comunes."""
        botones = [
            "button:has-text('Accept')",
            "button:has-text('Accept All')",
            "button:has-text('I Accept')",
            "button:has-text('Agree')",
            "button:has-text('OK')",
            "button:has-text('Got it')",
            "#accept-cookies",
            ".accept-cookies",
            "[aria-label='Accept cookies']",
            "#onetrust-accept-btn-handler",
        ]
        for sel in botones:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    log("Cookie banner aceptado", "BOT")
                    time.sleep(random.uniform(0.5, 1.0))
                    return
            except Exception:
                continue

    # ── Inyección de cookies ──────────────────────────────────────────────────

    def _inyectar_cookies(self):
        """Inyecta cookies normalizadas en el contexto. Soporta Cookie-Editor y Playwright nativo."""
        normalizadas = []
        for c in self.anti_bot.cookies:
            try:
                cookie = {
                    "name":   c.get("name", ""),
                    "value":  c.get("value", ""),
                    "domain": c.get("domain", ""),
                    "path":   c.get("path", "/"),
                }
                ss = c.get("sameSite", c.get("same_site", "Lax"))
                if isinstance(ss, str):
                    ss = ss.capitalize()
                    if ss not in ("Strict", "Lax", "None"):
                        ss = "Lax"
                cookie["sameSite"] = ss

                if "expirationDate" in c:
                    cookie["expires"] = int(c["expirationDate"])
                elif "expires" in c and isinstance(c["expires"], (int, float)):
                    cookie["expires"] = int(c["expires"])

                if "httpOnly" in c: cookie["httpOnly"] = bool(c["httpOnly"])
                if "secure"   in c: cookie["secure"]   = bool(c["secure"])

                if cookie["name"] and cookie["domain"]:
                    normalizadas.append(cookie)
            except Exception as e:
                log(f"Cookie ignorada (formato invalido): {e}", "WARN")

        if normalizadas:
            self._ctx.add_cookies(normalizadas)
            nombres = [c["name"] for c in normalizadas]
            log(f"Cookies inyectadas ({len(normalizadas)}): {', '.join(nombres)}", "OK")
            if "cf_clearance" in nombres:
                log("cf_clearance presente — Cloudflare deberia aceptar la sesion", "BOT")
        else:
            log("No se pudo normalizar ninguna cookie", "WARN")

    # ── Detección de Cloudflare ───────────────────────────────────────────────

    def _es_cloudflare(self) -> bool:
        """Detecta si la página actual es un challenge de Cloudflare."""
        try:
            contenido = self._page.content()
            return any(m.lower() in contenido.lower() for m in CLOUDFLARE_MARKERS)
        except Exception:
            return False

    def _manejar_cloudflare(self) -> bool:
        """
        Maneja Cloudflare según el nivel actual.
        Niveles 0-2: espera automática
        Nivel 4:     resolución manual interactiva
        Nivel 5:     CDP — no debería aparecer
        """
        nivel = self.anti_bot.nivel_actual

        if nivel >= NivelAntiBot.INTERACTIVO:
            return self._resolver_cloudflare_manual()

        # Niveles 0-2: esperar resolución automática con movimientos
        return self._esperar_cloudflare_auto()

    def _esperar_cloudflare_auto(self) -> bool:
        """Espera que el JS challenge se resuelva automáticamente."""
        log("Cloudflare detectado. Esperando resolucion automatica...", "BOT")
        inicio = time.time()
        max_wait = 15  # segundos
        while time.time() - inicio < max_wait:
            time.sleep(2)
            if not self._es_cloudflare():
                log("Cloudflare resuelto automaticamente", "OK")
                time.sleep(1.5)
                return True
            self._mover_mouse()
        log(f"Cloudflare no se resolvio en {max_wait}s.", "WARN")
        return False

    def _resolver_cloudflare_manual(self) -> bool:
        """Pausa y espera que el usuario resuelva el challenge manualmente (nivel 4)."""
        log("=" * 58, "BOT")
        log("CLOUDFLARE DETECTADO — RESOLUCION MANUAL ACTIVA (nivel 4)", "BOT")
        log("=" * 58, "BOT")
        log("1. Mira el navegador visible.", "BOT")
        log("2. Completa la verificacion (checkbox, puzzle, Turnstile).", "BOT")
        log("3. Regresa a esta terminal y presiona ENTER.", "BOT")
        log("=" * 58, "BOT")

        try:
            input("   >>> ENTER cuando hayas resuelto el challenge: ")
        except EOFError:
            log("Sin terminal interactiva. Esperando hasta 90s...", "WARN")
            for _ in range(18):
                if not self._es_cloudflare():
                    break
                time.sleep(5)

        if not self._es_cloudflare():
            log("Challenge resuelto. Continuando scraping...", "OK")
            self._guardar_cf_clearance()
            return True

        log("La pagina aun muestra Cloudflare.", "ERROR")
        return False

    def _guardar_cf_clearance(self):
        """Guarda cf_clearance en cf_clearance.json para reutilizar."""
        try:
            cf_cookies = [c for c in self._ctx.cookies()
                          if c["name"] == "cf_clearance"]
            if cf_cookies:
                ruta = Path(__file__).parent.parent / "cf_clearance.json"
                ruta.write_text(
                    json.dumps(cf_cookies, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                log(f"cf_clearance guardada en: {ruta}", "OK")
        except Exception as e:
            log(f"No se pudo guardar cf_clearance: {e}", "WARN")

    # ── Navegación robusta con escalación ─────────────────────────────────────

    def _navegar(self, url: str) -> bool:
        """
        Navega a una URL. Si detecta bloqueo y el modo es auto,
        escala al siguiente nivel y reintenta.
        """
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                resp = self._page.goto(url, timeout=TIMEOUT_MS,
                                       wait_until="domcontentloaded")

                # Obtener contenido y status
                http_status = resp.status if resp else 200
                contenido   = self._page.content() if resp else ""

                # Evaluar respuesta con el AntiBotManager
                resultado = self.anti_bot.evaluar_respuesta(
                    contenido_html=contenido,
                    http_status=http_status,
                    url_actual=url,
                )

                # URL sospechosa: avisar
                if resultado.url_sospechosa:
                    log(f"[!] URL sospechosa detectada: {url}. "
                        f"Posible redireccion a login/captcha/bloqueo.", "WARN")

                # Bloqueo detectado: escalar si es automático
                if resultado.bloqueado:
                    log(f"Bloqueo detectado: {resultado.motivo}", "WARN")
                    if resultado.escalar and self.anti_bot.subir_nivel():
                        log("Reintentando con mayor nivel anti-bot...", "BOT")
                        # Reconstruir el contexto con el nuevo nivel
                        self._reconstruir_contexto()
                        continue  # reintentar con nuevo nivel
                    return False

                # Cloudflare específico (manejo con espera)
                if self._es_cloudflare():
                    if not self._manejar_cloudflare():
                        # Escalar si falló y es posible
                        if self.anti_bot.es_automatico and self.anti_bot.subir_nivel():
                            self._reconstruir_contexto()
                            continue
                        return False

                self._aceptar_cookies()
                return True

            except PlaywrightTimeout:
                log(f"Timeout cargando {url} (intento {intento}/{MAX_REINTENTOS})", "WARN")
                resultado = self.anti_bot.evaluar_respuesta(
                    contenido_html="", timeout_ocurrido=True, url_actual=url
                )
                if resultado.escalar and self.anti_bot.subir_nivel():
                    self._reconstruir_contexto()
                    continue
                if intento < MAX_REINTENTOS:
                    time.sleep(3 * intento)

            except Exception as e:
                log(f"Error cargando {url}: {e} (intento {intento}/{MAX_REINTENTOS})", "WARN")
                if intento < MAX_REINTENTOS:
                    time.sleep(3 * intento)

        return False

    def _reconstruir_contexto(self):
        """
        Reconstruye el contexto del navegador con el nuevo nivel anti-bot.
        Se llama después de escalar a un nivel superior.
        """
        log("Reconstruyendo contexto del navegador con nuevo nivel...", "BOT")
        try:
            # Cerrar página y contexto actuales
            if self._page:
                self._page.close()
            if self._ctx:
                self._ctx.close()
        except Exception:
            pass

        if self._modo_cdp:
            # CDP: reutilizar el mismo browser (no podemos lanzar uno nuevo)
            contextos = self._browser.contexts
            if contextos:
                self._ctx = contextos[0]
            else:
                self._ctx = self._browser.new_context()
            self._page = self._ctx.new_page()
        else:
            # Lanzar nuevo contexto con nivel actualizado (sin relanzar el browser completo)
            self._ctx = self._browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport=random.choice(VIEWPORTS),
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language":           "en-US,en;q=0.9",
                    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Encoding":           "gzip, deflate, br",
                    "Connection":                "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest":            "document",
                    "Sec-Fetch-Mode":            "navigate",
                    "Sec-Fetch-Site":            "none",
                    "Sec-Fetch-User":            "?1",
                },
            )
            self._page = self._ctx.new_page()

            # Reaplicar stealth si el nivel lo requiere
            if self.anti_bot.nivel_actual >= NivelAntiBot.STEALTH_JS:
                if _STEALTH_DISPONIBLE:
                    stealth_sync(self._page)
                else:
                    self._aplicar_stealth_manual()

            # Reinyectar cookies
            if self.anti_bot.cookies:
                self._inyectar_cookies()

        log(f"Contexto reconstruido en nivel {self.anti_bot.nivel_num} "
            f"({self.anti_bot.nivel_actual.nombre_corto()})", "OK")

    # ── Utilidades de selección ───────────────────────────────────────────────

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

    # ── Tipo de URL ───────────────────────────────────────────────────────────

    def _es_indice(self, url: str) -> bool:
        patron = self._perfil.get("patron_indice", "")
        if patron:
            return bool(re.search(patron, url))
        return "chapter" not in url.lower()

    # ── Primer capítulo desde índice ──────────────────────────────────────────

    def _primer_capitulo_desde_indice(self, url: str) -> str | None:
        log(f"Cargando indice: {url}")
        if not self._navegar(url):
            log("No se pudo cargar la pagina de indice.", "ERROR")
            return None

        self._delay_humano()
        self._scroll_humano()

        elem = self._primer_elem(self._sels("indice_primer_cap"))
        if elem:
            href = self._resolver_url(elem.get_attribute("href") or "")
            if href:
                log(f"Primer capitulo: {href}", "OK")
                return href

        log("No se encontro el primer capitulo en el indice.", "ERROR")
        return None

    # ── Extracción de capítulo ────────────────────────────────────────────────

    def _extraer_capitulo(self, url: str) -> dict | None:
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                if not self._navegar(url):
                    raise Exception("Fallo al navegar a la URL")

                self._delay_humano()
                self._mover_mouse()
                self._scroll_humano()
                self._delay_humano(base=0.5, variacion=0.5)

                # Título
                titulo = ""
                elem = self._primer_elem(self._sels("titulo"))
                if elem:
                    titulo = elem.inner_text().strip()

                # Contenido
                texto = ""
                for sel in self._sels("contenido"):
                    try:
                        elem = self._page.query_selector(sel)
                        if not elem:
                            continue
                        for ad_sel in self._sels("eliminar_anuncios"):
                            for node in elem.query_selector_all(ad_sel):
                                node.evaluate("el => el.remove()")
                        texto = elem.inner_text().strip()
                        if len(texto) > 100:
                            break
                    except Exception:
                        continue

                # Fallback: body limpio
                if len(texto) < 100:
                    for sel in ["nav", "header", "footer", ".navbar", ".sidebar", ".ads"]:
                        for el in self._page.query_selector_all(sel):
                            try: el.evaluate("el => el.remove()")
                            except: pass
                    texto = self._page.inner_text("body").strip()

                # Siguiente capítulo
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

                # Fallback: incremento de URL
                if not siguiente:
                    siguiente = self._siguiente_por_incremento(url)
                    if siguiente:
                        log(f"  Siguiente inferido por URL: {siguiente}", "WARN")

                return {"titulo": titulo, "url": url, "texto": texto, "siguiente": siguiente}

            except Exception as e:
                log(f"Error intento {intento}/{MAX_REINTENTOS}: {e}", "WARN")
                if intento < MAX_REINTENTOS:
                    time.sleep(random.uniform(3, 6) * intento)

        log(f"No se pudo extraer: {url}", "ERROR")
        return None

    # ── Siguiente por incremento de URL ──────────────────────────────────────

    def _siguiente_por_incremento(self, url: str) -> str | None:
        patrones = [
            r'(/chapter/)(\d+)(/?$)',
            r'(/chapter-)(\d+)(/?(?:\?.*)?$)',
            r'(/chapter_)(\d+)(/?(?:\?.*)?$)',
            r'(-chapter-)(\d+)(/?(?:\?.*)?$)',
        ]
        for patron in patrones:
            m = re.search(patron, url)
            if m:
                return (
                    url[: m.start()]
                    + m.group(1)
                    + str(int(m.group(2)) + 1)
                    + m.group(3)
                )
        return None

    # ── Detección automática de selectores ────────────────────────────────────

    def detectar_y_guardar(self, url: str) -> dict | None:
        """Visita una URL, detecta selectores y guarda el perfil."""
        log(f"Detectando selectores en: {url}")
        dominio = urlparse(url).netloc.lower()
        self._perfil = perfil_generico()

        if not self._navegar(url):
            log("No se pudo cargar la pagina.", "ERROR")
            return None

        self._delay_humano()
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
                log(f"  {tipo}: no detectado, se usara generico", "WARN")

        nuevo = {
            "id":              dominio.lstrip("www.").replace(".", "_"),
            "nombre":          dominio.lstrip("www.").split(".")[0].capitalize(),
            "dominios":        [dominio, "www." + dominio],
            "activo":          True,
            "descripcion":     f"Perfil detectado automaticamente para {dominio}",
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
        self._perfil = buscar_por_url(url_inicio, perfiles, forzar_id=forzar_sitio)
        log(f"Perfil activo: {self._perfil['nombre']}")
        log(f"Anti-bot: nivel {self.anti_bot.nivel_num} "
            f"({self.anti_bot.nivel_actual.nombre_corto()}) "
            f"| modo: {self.anti_bot.modo_actual}", "BOT")
        delay_base = self._perfil["opciones"].get("delay_entre_paginas", 2.0)

        # Registrar URL inicial para aprendizaje de patrón
        self.anti_bot.aprender_url(url_inicio)

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
                log(f"Fallo en capitulo {i}. Deteniendo.", "ERROR")
                log_progreso(i, num_capitulos, estado="error")
                break

            capitulos.append(cap)
            log(f'  -> "{cap["titulo"][:65]}"', "OK")
            log_progreso(i, num_capitulos, titulo=cap["titulo"], estado="ok")

            if i < num_capitulos:
                if cap["siguiente"]:
                    url_actual = cap["siguiente"]

                    # Verificar consistencia de URL con el AntiBotManager
                    resultado = self.anti_bot.evaluar_respuesta(
                        contenido_html="", url_actual=url_actual
                    )
                    if resultado.url_sospechosa:
                        log(f"[!] ALERTA: La URL del siguiente capitulo parece sospechosa: "
                            f"{url_actual}", "WARN")
                        log("Posible redireccion a login/captcha/bloqueo. Verifica manualmente.", "WARN")

                    # Delay entre capítulos
                    delay = delay_base + random.uniform(-0.5, 1.5)
                    time.sleep(max(1.0, delay))
                else:
                    log("No hay capitulo siguiente. Fin de la novela.", "SKIP")
                    log_progreso(i, num_capitulos, estado="fin")
                    break

        return capitulos
