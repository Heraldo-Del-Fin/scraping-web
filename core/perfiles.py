"""
core/perfiles.py
----------------
Carga, búsqueda y persistencia de perfiles de sitios en perfiles.json.
No depende de tkinter ni de Playwright.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

# perfiles.json vive en la raíz del proyecto (un nivel arriba de core/)
RUTA_PERFILES = Path(__file__).parent.parent / "perfiles.json"


# ── Perfil genérico de fallback ───────────────────────────────────────────────

def perfil_generico() -> dict:
    return {
        "id": "generico",
        "nombre": "Genérico",
        "dominios": [],
        "activo": True,
        "descripcion": "Fallback automático",
        "patron_indice": "",
        "patron_capitulo": "",
        "selectores": {
            "titulo": [
                "h1", "h2", "h3", ".chapter-title", "#chapter-title",
                ".chapter-name", ".title", "#title", ".post-title",
                ".chr-title", ".entry-title",
            ],
            "contenido": [
                "#chapter-content", ".chapter-content", "#chr-content", ".chr-c",
                ".chp-raw", ".chapter-text", ".entry-content", ".post-content",
                "article", ".content", "main", ".fiction-body",
                ".wi_news_body", ".text-left", ".fr-view",
            ],
            "siguiente": [
                "a[rel='next']", "a.next_page", "a.next-chapter", "a.btn-next",
                "a#btn_next", "a:has-text('Next Chapter')",
                "a:has-text('Next')", "a:has-text('Siguiente')",
            ],
            "indice_primer_cap": [
                "a:has-text('Start Reading')", "a:has-text('Read Now')",
                "a:has-text('Chapter 1')", "a.btn-read-now", "a.read-btn",
                ".chapter-list a:first-child", "a[href*='chapter-1']",
            ],
            "eliminar_anuncios": [
                ".ads", ".ad", ".adsbox", ".adsbygoogle",
                ".google-auto-placed", ".ad-container",
            ],
        },
        "opciones": {
            "delay_entre_paginas": 2.5,
            "espera_carga": 2.0,
            "base_url": "",
        },
    }


# ── Lectura / escritura ───────────────────────────────────────────────────────

def cargar_todos() -> list[dict]:
    """Lee perfiles.json y devuelve todos los perfiles activos."""
    if not RUTA_PERFILES.exists():
        return [perfil_generico()]
    try:
        data = json.loads(RUTA_PERFILES.read_text(encoding="utf-8"))
        return [p for p in data.get("perfiles", []) if p.get("activo", True)]
    except Exception as e:
        print(f"[!] Error leyendo perfiles.json: {e}. Usando genérico.")
        return [perfil_generico()]


def cargar_raw() -> dict:
    """Devuelve el JSON completo (para edición en la GUI)."""
    if RUTA_PERFILES.exists():
        try:
            return json.loads(RUTA_PERFILES.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"_version": "1.0", "perfiles": []}


def guardar_raw(data: dict):
    """Escribe el JSON completo en perfiles.json."""
    RUTA_PERFILES.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def guardar_perfil(perfil: dict):
    """Inserta o actualiza un perfil en perfiles.json."""
    data = cargar_raw()
    lista = data.get("perfiles", [])
    idx = next((i for i, p in enumerate(lista) if p["id"] == perfil["id"]), None)
    if idx is not None:
        lista[idx] = perfil
    else:
        # Insertar antes del genérico (último elemento)
        lista.insert(max(0, len(lista) - 1), perfil)
    data["perfiles"] = lista
    guardar_raw(data)


def eliminar_perfil(pid: str):
    """Elimina un perfil por ID (el genérico no puede eliminarse)."""
    if pid == "generico":
        raise ValueError("El perfil genérico no puede eliminarse.")
    data = cargar_raw()
    data["perfiles"] = [p for p in data["perfiles"] if p["id"] != pid]
    guardar_raw(data)


def toggle_activo(pid: str):
    """Activa o desactiva un perfil."""
    data = cargar_raw()
    for p in data["perfiles"]:
        if p["id"] == pid:
            p["activo"] = not p.get("activo", True)
            break
    guardar_raw(data)


# ── Búsqueda por URL ──────────────────────────────────────────────────────────

def buscar_por_url(url: str, perfiles: list[dict], forzar_id: str = "") -> dict:
    """
    Devuelve el perfil más adecuado para una URL.
    Orden de prioridad: forzar_id > dominio exacto > genérico.
    """
    if forzar_id:
        encontrado = next((p for p in perfiles if p["id"] == forzar_id), None)
        if encontrado:
            return encontrado
        print(f"[!] Perfil '{forzar_id}' no encontrado. Usando genérico.")

    dominio = urlparse(url).netloc.lower().lstrip("www.")
    for p in perfiles:
        for d in p.get("dominios", []):
            d_norm = d.lstrip("www.")
            if dominio == d_norm or dominio.endswith("." + d_norm):
                return p

    # Fallback al genérico incluido en la lista
    gen = next((p for p in perfiles if p["id"] == "generico"), None)
    return gen or perfil_generico()


def ids_disponibles() -> list[str]:
    """Devuelve la lista de IDs de perfiles activos."""
    return [p["id"] for p in cargar_todos()]