"""
traductor/traducir.py
---------------------
Lógica de traducción por chunks usando deep-translator (Google Translate).
No depende de tkinter.
"""

import json
import re
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("ERROR: Falta deep-translator. Ejecuta: pip install deep-translator")
    raise

# ── Configuración ─────────────────────────────────────────────────────────────

CHUNK_SIZE     = 4_500   # caracteres por fragmento (límite Google ~5000)
DELAY_REQUEST  = 0.8     # segundos entre requests
MAX_REINTENTOS = 3

IDIOMAS = {
    "es": "Español",    "pt": "Portugués",  "fr": "Francés",
    "de": "Alemán",     "it": "Italiano",   "ja": "Japonés",
    "ko": "Coreano",    "zh-CN": "Chino Simplificado",
    "ru": "Ruso",       "ar": "Árabe",
}

# ── Logger ────────────────────────────────────────────────────────────────────

_modo_progreso = False

def set_modo_progreso(activo: bool):
    global _modo_progreso
    _modo_progreso = activo

def log(msg: str, nivel: str = "INFO"):
    iconos = {"INFO": "[i]", "OK": "[OK]", "WARN": "[!]", "ERROR": "[X]", "TRAD": "[~]"}
    print(f"{iconos.get(nivel, '·')} {msg}", flush=True)

def log_progreso(actual: int, total: int, titulo: str = "", estado: str = "traduciendo"):
    if _modo_progreso:
        data = {"tipo": "progreso", "actual": actual, "total": total,
                "titulo": titulo, "estado": estado}
        print(f"PROGRESO:{json.dumps(data, ensure_ascii=False)}", flush=True)


# ── Utilidades ────────────────────────────────────────────────────────────────

def _dividir_chunks(texto: str) -> list[str]:
    """Divide el texto respetando párrafos para no cortar frases a la mitad."""
    if len(texto) <= CHUNK_SIZE:
        return [texto]

    chunks, actual = [], ""
    for parrafo in texto.split("\n"):
        if len(parrafo) > CHUNK_SIZE:
            # Párrafo gigante: dividir por oraciones
            for oracion in re.split(r'(?<=[.!?])\s+', parrafo):
                if len(actual) + len(oracion) + 1 <= CHUNK_SIZE:
                    actual += oracion + " "
                else:
                    if actual: chunks.append(actual.strip())
                    actual = oracion + " "
        else:
            if len(actual) + len(parrafo) + 1 <= CHUNK_SIZE:
                actual += parrafo + "\n"
            else:
                if actual: chunks.append(actual.strip())
                actual = parrafo + "\n"

    if actual.strip():
        chunks.append(actual.strip())
    return chunks


def _traducir_chunk(chunk: str, idioma: str) -> str:
    """Traduce un fragmento con reintentos."""
    translator = GoogleTranslator(source="auto", target=idioma)
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            resultado = translator.translate(chunk)
            time.sleep(DELAY_REQUEST)
            return resultado or chunk
        except Exception as e:
            if intento < MAX_REINTENTOS:
                time.sleep(2 * intento)
            else:
                log(f"Fallo al traducir chunk tras {MAX_REINTENTOS} intentos: {e}", "WARN")
                return chunk   # devolver original si falla
    return chunk


# ── API pública ───────────────────────────────────────────────────────────────

def traducir_texto(texto: str, idioma: str) -> str:
    """Traduce un texto de cualquier longitud al idioma dado."""
    if not texto.strip():
        return texto
    chunks = _dividir_chunks(texto)
    if len(chunks) == 1:
        return _traducir_chunk(texto, idioma)
    return "\n".join(_traducir_chunk(c, idioma) for c in chunks)


def traducir_capitulos(
    capitulos: list[dict],
    idioma: str,
) -> list[dict]:
    """
    Traduce una lista de capítulos {titulo, texto, ...} in-place.
    Emite PROGRESO: para que la GUI pueda leer el avance.
    """
    total = len(capitulos)
    for i, cap in enumerate(capitulos, 1):
        log(f"[{i}/{total}] {cap['titulo'][:60]}", "TRAD")
        log_progreso(i, total, titulo=cap["titulo"], estado="traduciendo")

        cap["titulo"] = traducir_texto(cap["titulo"], idioma)
        cap["texto"]  = traducir_texto(cap["texto"],  idioma)

        log_progreso(i, total, titulo=cap["titulo"], estado="ok")

    return capitulos