"""
core/anti_bot.py
----------------
Sistema de evasión de bots por capas progresivas.

Niveles:
  0 - Básico         : User-agent rotativo, viewport aleatorio, headers realistas
  1 - Stealth JS     : playwright_stealth (oculta navigator.webdriver, WebGL spoof...)
  2 - Comportamiento : Scroll humano, mouse aleatorio, delays variables
  3 - Cookies        : Inyección de cf_clearance + cookies de navegador real
  4 - Interactivo    : Navegador visible, pausa para resolver challenge manualmente
  5 - Chrome real    : Conexión CDP a Chrome del usuario (TLS fingerprint nativo)

Modos:
  "auto"  → escala automáticamente si detecta bloqueos (0→1→2, luego pide manual)
  0..5    → nivel fijo, no escala

Uso:
    from core.anti_bot import AntiBotManager, NivelAntiBot

    manager = AntiBotManager(modo="auto", nivel_max=5,
                             cookies=cookies, chrome_port=9222)
    # En el bucle de navegación:
    resultado = manager.evaluar_respuesta(page, url, http_status, contenido)
    if resultado.escalar:
        manager.subir_nivel()
        # reintentar navegación
"""

import json
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

# ── Niveles ───────────────────────────────────────────────────────────────────

class NivelAntiBot(IntEnum):
    BASICO        = 0
    STEALTH_JS    = 1
    COMPORTAMIENTO = 2
    COOKIES       = 3
    INTERACTIVO   = 4
    CHROME_REAL   = 5

    def descripcion(self) -> str:
        return DESCRIPCIONES[self.value]

    def es_automatico(self) -> bool:
        return self.value <= 2

    def requiere_config(self) -> bool:
        return self.value >= 3

    def nombre_corto(self) -> str:
        return NOMBRES_CORTOS[self.value]


DESCRIPCIONES = [
    "User-agent rotativo, viewport aleatorio, headers HTTP realistas, "
    "flags anti-automatización en Chromium.",
    "Inyección JS para ocultar navigator.webdriver, falsificar plugins, "
    "WebGL vendor/renderer y permisos. Usa playwright-stealth.",
    "Scroll gradual, movimiento de mouse aleatorio, delays variables "
    "entre páginas, pausas de lectura simuladas.",
    "Inyección de cookies de sesión reales (cf_clearance, session, etc.) "
    "exportadas desde un navegador con Cookie-Editor.",
    "Navegador visible + pausa interactiva para que el usuario resuelva "
    "manualmente challenges de Cloudflare/Turnstile.",
    "Conexión CDP a un Chrome real abierto por el usuario. TLS fingerprint "
    "nativo, cookies y sesión del perfil real. Máxima evasión.",
]

NOMBRES_CORTOS = [
    "Básico",
    "Stealth JS",
    "Comportamiento",
    "Cookies",
    "Interactivo",
    "Chrome real",
]

# Nivel máximo que se puede alcanzar automáticamente (sin intervención del usuario)
NIVEL_MAX_AUTO = 2


# ── Señales de bloqueo ───────────────────────────────────────────────────────

# Marcadores de Cloudflare en el contenido HTML
CLOUDFLARE_MARKERS = [
    "Just a moment",
    "Checking your browser",
    "DDoS protection by Cloudflare",
    "cf-browser-verification",
    "ray ID",
    "Please wait",
    "Enable JavaScript and cookies",
    "cf-challenge",
    "turnstile",
    "challenge-platform",
]

# Marcadores de CAPTCHA genérico
CAPTCHA_MARKERS = [
    "captcha",
    "verify you are human",
    "are you a robot",
    "recaptcha",
    "hcaptcha",
]

# Códigos HTTP que indican bloqueo
HTTP_BLOQUEO = {403, 429, 503}


# ── Resultado de evaluación ──────────────────────────────────────────────────

@dataclass
class ResultadoNavegacion:
    """Resultado de evaluar la respuesta de una navegación."""
    exito: bool = True
    bloqueado: bool = False
    motivo: str = ""
    escalar: bool = False
    nivel_sugerido: NivelAntiBot | None = None
    url_sospechosa: bool = False
    url_original: str = ""
    url_actual: str = ""


# ── Gestor de niveles ────────────────────────────────────────────────────────

class AntiBotManager:
    """
    Gestiona la estrategia anti-bot, el nivel actual, y decide cuándo escalar.

    Parámetros:
        modo       : "auto" para escalación automática, o un int 0-5 para nivel fijo
        nivel_max  : nivel máximo permitido (útil en modo "auto")
        cookies    : lista de cookies para nivel 3
        chrome_port: puerto CDP para nivel 5
        log_fn     : función de log (por defecto print)
    """

    def __init__(
        self,
        modo: str | int = "auto",
        nivel_max: int = 5,
        cookies: list[dict] | None = None,
        chrome_port: int = 0,
        log_fn: Callable[[str], None] = None,
    ):
        self._modo = modo
        self.nivel_max = min(nivel_max, 5)
        self.cookies = cookies or []
        self.chrome_port = chrome_port
        self.log = log_fn or (lambda msg: print(msg, flush=True))

        # Determinar nivel inicial
        if modo == "auto":
            self.nivel_actual = NivelAntiBot.BASICO
        elif isinstance(modo, int) or (isinstance(modo, str) and modo.isdigit()):
            self.nivel_actual = NivelAntiBot(min(int(modo), 5))
        else:
            self.nivel_actual = NivelAntiBot.BASICO

        # Historial de escalación
        self.historial: list[NivelAntiBot] = [self.nivel_actual]
        self._url_anterior: str = ""
        self._patron_url: re.Pattern | None = None  # patrón aprendido de URLs

    # ── Propiedades ───────────────────────────────────────────────────────────

    @property
    def modo_actual(self) -> str:
        if self._modo == "auto":
            return "auto"
        return str(self.nivel_actual.value)

    @property
    def es_automatico(self) -> bool:
        return self._modo == "auto"

    @property
    def nivel_num(self) -> int:
        return self.nivel_actual.value

    @property
    def requiere_cookies(self) -> bool:
        return self.nivel_actual >= NivelAntiBot.COOKIES

    @property
    def requiere_visible(self) -> bool:
        return self.nivel_actual >= NivelAntiBot.INTERACTIVO

    @property
    def requiere_cdp(self) -> bool:
        return self.nivel_actual == NivelAntiBot.CHROME_REAL

    @property
    def nivel_descripcion(self) -> str:
        return DESCRIPCIONES[self.nivel_num]

    # ── Control de nivel ─────────────────────────────────────────────────────

    def subir_nivel(self) -> NivelAntiBot | None:
        """
        Intenta subir al siguiente nivel. En modo auto, salta niveles manuales
        si no están configurados (sin cookies, sin chrome_port).
        Devuelve el nuevo nivel o None si ya está en el máximo.
        """
        if self._modo != "auto":
            self.log(f"[BOT] Modo fijo (nivel {self.nivel_num}). No se escala automáticamente.")
            return None

        siguiente = self.nivel_actual.value + 1
        if siguiente > self.nivel_max:
            self.log(f"[BOT] Ya en nivel máximo ({self.nivel_max}). No se puede escalar más.")
            return None

        # Saltar niveles manuales no configurados
        while siguiente <= self.nivel_max:
            candidato = NivelAntiBot(siguiente)
            if candidato == NivelAntiBot.COOKIES and not self.cookies:
                self.log(f"[BOT] Nivel {siguiente} (Cookies) omitido: no hay cookies configuradas.")
                siguiente += 1
                continue
            if candidato == NivelAntiBot.CHROME_REAL and not self.chrome_port:
                self.log(f"[BOT] Nivel {siguiente} (Chrome real) omitido: no hay puerto CDP configurado.")
                siguiente += 1
                continue
            break

        if siguiente > self.nivel_max:
            self.log(f"[BOT] No hay más niveles disponibles dentro del máximo ({self.nivel_max}).")
            return None

        anterior = self.nivel_actual
        self.nivel_actual = NivelAntiBot(siguiente)
        self.historial.append(self.nivel_actual)
        self.log(
            f"[BOT] ⬆ Escalando: {anterior.nombre_corto()} (nivel {anterior.value}) "
            f"→ {self.nivel_actual.nombre_corto()} (nivel {self.nivel_actual.value})"
        )
        return self.nivel_actual

    def set_nivel(self, nivel: int | NivelAntiBot):
        """Fija manualmente el nivel (incluso en modo auto)."""
        if isinstance(nivel, int):
            nivel = NivelAntiBot(min(nivel, 5))
        self.nivel_actual = nivel
        self.historial.append(nivel)
        self.log(f"[BOT] Nivel fijado manualmente: {nivel.nombre_corto()} ({nivel.value})")

    def reset(self):
        """Vuelve al nivel inicial."""
        inicial = NivelAntiBot.BASICO if self._modo == "auto" else self.nivel_actual
        self.nivel_actual = inicial
        self.historial = [inicial]
        self._url_anterior = ""
        self._patron_url = None

    # ── Evaluación de respuesta ──────────────────────────────────────────────

    def evaluar_respuesta(
        self,
        contenido_html: str,
        http_status: int = 200,
        url_actual: str = "",
        timeout_ocurrido: bool = False,
    ) -> ResultadoNavegacion:
        """
        Evalúa la respuesta de una navegación y decide si hubo bloqueo,
        si la URL es sospechosa, y si se debe escalar.

        Llamar después de cada page.goto() o equivalente.
        """
        r = ResultadoNavegacion(url_actual=url_actual, url_original=url_actual)

        # 1. Timeout
        if timeout_ocurrido:
            r.exito = False
            r.bloqueado = True
            r.motivo = "Timeout de navegación"
            if self._modo == "auto" and self.nivel_actual.es_automatico():
                r.escalar = True
                r.nivel_sugerido = NivelAntiBot(min(self.nivel_actual.value + 1, 5))
            return r

        # 2. HTTP status de bloqueo
        if http_status in HTTP_BLOQUEO:
            r.exito = False
            r.bloqueado = True
            r.motivo = f"HTTP {http_status}"
            if self._modo == "auto" and self.nivel_actual.es_automatico():
                r.escalar = True
                r.nivel_sugerido = NivelAntiBot(min(self.nivel_actual.value + 1, 5))
            return r

        # 3. Cloudflare / CAPTCHA en contenido
        html_lower = contenido_html.lower()
        for marker in CLOUDFLARE_MARKERS + CAPTCHA_MARKERS:
            if marker.lower() in html_lower:
                r.exito = False
                r.bloqueado = True
                r.motivo = f"Challenge detectado: '{marker}'"
                if self._modo == "auto" and self.nivel_actual.es_automatico():
                    r.escalar = True
                    r.nivel_sugerido = NivelAntiBot(min(self.nivel_actual.value + 1, 5))
                return r

        # 4. Consistencia de URL
        if url_actual:
            r.url_sospechosa = self._detectar_url_sospechosa(url_actual)
            if r.url_sospechosa:
                r.motivo = f"URL sospechosa detectada: {url_actual}"
                # La URL sospechosa no escala automáticamente, pero avisa
                self.log(f"[!] {r.motivo}")

        return r

    def _detectar_url_sospechosa(self, url: str) -> bool:
        """
        Detecta si la URL navegada se desvía del patrón esperado de capítulos.
        Aprende el patrón de la primera URL de capítulo y compara las siguientes.

        Señales sospechosas:
          - URL contiene /login, /auth, /signin, /register
          - URL contiene /captcha, /verify, /challenge
          - URL cambia de dominio repentinamente
          - URL rompe el patrón numérico (ej: /chapter/5 → /chapter/login)
        """
        # URLs que claramente no son capítulos
        patrones_sospechosos = [
            r'/login', r'/auth', r'/signin', r'/register', r'/signup',
            r'/captcha', r'/verify', r'/challenge', r'/blocked',
            r'/error', r'/denied', r'/banned', r'/suspended',
            r'logout', r'redirect',
        ]
        url_lower = url.lower()
        for p in patrones_sospechosos:
            if re.search(p, url_lower):
                return True

        # Aprender/verificar patrón de capítulo
        return self._verificar_patron_capitulo(url)

    def _verificar_patron_capitulo(self, url: str) -> bool:
        """
        Aprende el patrón de URL de la primera visita y detecta desviaciones.
        Ej: si el patrón es /novel-name/chapter-(\d+) y la URL actual no coincide,
        es sospechosa.
        """
        if not self._url_anterior:
            # Primera URL: intentar extraer patrón
            self._patron_url = self._extraer_patron(url)
            self._url_anterior = url
            return False

        if self._patron_url is None:
            # No se pudo extraer patrón (URL muy variable) — no marcar como sospechosa
            self._url_anterior = url
            return False

        if self._patron_url.match(url):
            self._url_anterior = url
            return False

        # La URL no coincide con el patrón esperado → sospechosa
        return True

    def _extraer_patron(self, url: str) -> re.Pattern | None:
        """
        Intenta extraer un patrón genérico de la URL reemplazando números
        y slugs variables por grupos de captura.
        """
        try:
            # Reemplazar números por \d+
            patron_str = re.sub(r'\d+', r'\\d+', url)
            # Reemplazar posibles slugs largos (palabras con guiones)
            # pero mantener la estructura base
            patron_str = re.escape(url)
            # Reemplazar secuencias de dígitos escapadas
            patron_str = re.sub(r'\\\\d\+', r'\\d+', patron_str)
            # Hacer los números opcionales para flexibilidad
            patron_str = re.sub(r'(\\d\+)', r'(\\d+)', patron_str)
            return re.compile('^' + patron_str + '$')
        except Exception:
            return None

    def aprender_url(self, url: str):
        """Registra una URL como válida para el aprendizaje de patrón."""
        if not self._url_anterior:
            self._url_anterior = url
            self._patron_url = self._extraer_patron(url)

    # ── Estado para la GUI ────────────────────────────────────────────────────

    def estado_gui(self) -> dict:
        """Devuelve un diccionario con el estado actual para la GUI."""
        return {
            "modo": self._modo,
            "nivel_actual": self.nivel_num,
            "nivel_nombre": self.nivel_actual.nombre_corto(),
            "nivel_descripcion": self.nivel_descripcion,
            "nivel_max": self.nivel_max,
            "es_automatico": self.es_automatico,
            "requiere_visible": self.requiere_visible,
            "requiere_cookies": self.requiere_cookies,
            "requiere_cdp": self.requiere_cdp,
            "cookies_cargadas": len(self.cookies),
            "chrome_port": self.chrome_port,
            "historial": [n.value for n in self.historial],
        }

    @staticmethod
    def listar_niveles() -> list[dict]:
        """Lista todos los niveles con metadatos para mostrar en GUI."""
        return [
            {
                "nivel": n.value,
                "nombre": n.nombre_corto(),
                "descripcion": n.descripcion(),
                "automatico": n.es_automatico(),
                "requiere_config": n.requiere_config(),
            }
            for n in NivelAntiBot
        ]

    @staticmethod
    def resumen_niveles() -> str:
        """Resumen en texto de todos los niveles."""
        lineas = []
        for n in NivelAntiBot:
            auto = "✅ Auto" if n.es_automatico() else "🔧 Manual"
            lineas.append(
                f"  Nivel {n.value} - {n.nombre_corto():<16} {auto}\n"
                f"         {n.descripcion()}"
            )
        return "\n".join(lineas)
