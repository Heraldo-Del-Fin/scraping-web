"""
Traductor + Exportador PDF
===========================
Lee el TXT generado por novelbin_scraper.py, lo traduce al español
y lo exporta como PDF bien formateado.

Uso:
    python traducir_a_pdf.py <archivo.txt> [opciones]

Ejemplos:
    # Traducir un TXT al español (por defecto)
    python traducir_a_pdf.py novelas/supreme-magus.txt

    # Traducir a otro idioma
    python traducir_a_pdf.py novelas/supreme-magus.txt --idioma pt  # portugués

    # Cambiar carpeta de salida
    python traducir_a_pdf.py novelas/supreme-magus.txt --salida ./pdfs

    # Ver idiomas disponibles
    python traducir_a_pdf.py --idiomas

Instalación de dependencias:
    pip install deep-translator reportlab
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

# Forzar UTF-8 en la salida estándar (necesario en Windows con cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Verificar dependencias ────────────────────────────────────────────────────
try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("ERROR: Falta deep-translator. Ejecuta: pip install deep-translator")
    exit(1)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    print("ERROR: Falta reportlab. Ejecuta: pip install reportlab")
    exit(1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def limpiar_nombre_archivo(nombre: str) -> str:
    """Elimina caracteres inválidos para nombres de archivo."""
    import re as _re
    return _re.sub(r'[\\/*?:"<>|]', "", nombre).strip()


# ── Configuración ─────────────────────────────────────────────────────────────

CHUNK_SIZE       = 4500   # caracteres por fragmento (límite de Google Translate ~5000)
DELAY_TRADUCCION = 0.8    # segundos entre requests al traductor
MAX_REINTENTOS   = 3      # reintentos si falla la traducción


IDIOMAS = {
    "es": "Español",
    "pt": "Portugués",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "ja": "Japonés",
    "ko": "Coreano",
    "zh-CN": "Chino Simplificado",
    "ru": "Ruso",
    "ar": "Árabe",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

_MODO_PROGRESO = False

def log(msg, nivel="INFO"):
    iconos = {"INFO": "📄", "OK": "✅", "WARN": "⚠️", "ERROR": "❌", "TRAD": "🌐"}
    print(f"{iconos.get(nivel, '·')} {msg}", flush=True)

def log_progreso(actual: int, total: int, titulo: str = "", estado: str = "traduciendo"):
    if _MODO_PROGRESO:
        import json as _json
        data = {"tipo": "progreso", "actual": actual, "total": total,
                "titulo": titulo, "estado": estado}
        print(f"PROGRESO:{_json.dumps(data, ensure_ascii=False)}", flush=True)


def dividir_en_chunks(texto: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    """
    Divide el texto en fragmentos respetando párrafos y oraciones,
    para no cortar palabras en el medio.
    """
    if len(texto) <= max_chars:
        return [texto]

    chunks = []
    parrafos = texto.split("\n")
    chunk_actual = ""

    for parrafo in parrafos:
        # Si el párrafo solo ya es demasiado largo, dividir por oraciones
        if len(parrafo) > max_chars:
            oraciones = re.split(r'(?<=[.!?])\s+', parrafo)
            for oracion in oraciones:
                if len(chunk_actual) + len(oracion) + 1 <= max_chars:
                    chunk_actual += oracion + " "
                else:
                    if chunk_actual:
                        chunks.append(chunk_actual.strip())
                    chunk_actual = oracion + " "
        else:
            if len(chunk_actual) + len(parrafo) + 1 <= max_chars:
                chunk_actual += parrafo + "\n"
            else:
                if chunk_actual:
                    chunks.append(chunk_actual.strip())
                chunk_actual = parrafo + "\n"

    if chunk_actual.strip():
        chunks.append(chunk_actual.strip())

    return chunks


def traducir_texto(texto: str, idioma_destino: str) -> str:
    """Traduce un texto dividiendo en chunks si es necesario."""
    if not texto.strip():
        return texto

    translator = GoogleTranslator(source="auto", target=idioma_destino)
    chunks = dividir_en_chunks(texto)

    if len(chunks) == 1:
        # Texto corto, traducir directo
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                resultado = translator.translate(texto)
                time.sleep(DELAY_TRADUCCION)
                return resultado or texto
            except Exception as e:
                if intento < MAX_REINTENTOS:
                    time.sleep(2 * intento)
                else:
                    log(f"Fallo traducción tras {MAX_REINTENTOS} intentos: {e}", "WARN")
                    return texto  # devolver original si falla
    else:
        # Texto largo: traducir chunk a chunk
        partes_traducidas = []
        for i, chunk in enumerate(chunks):
            for intento in range(1, MAX_REINTENTOS + 1):
                try:
                    traducido = translator.translate(chunk)
                    partes_traducidas.append(traducido or chunk)
                    time.sleep(DELAY_TRADUCCION)
                    break
                except Exception as e:
                    if intento < MAX_REINTENTOS:
                        time.sleep(2 * intento)
                    else:
                        log(f"  Chunk {i+1} falló, usando original: {e}", "WARN")
                        partes_traducidas.append(chunk)

        return "\n".join(partes_traducidas)


# ── Parser del TXT ────────────────────────────────────────────────────────────

def parsear_txt(ruta: Path) -> list[dict]:
    """
    Lee el TXT generado por novelbin_scraper.py y lo divide en capítulos.
    Estructura: separador ===, título, separador ===, contenido
    """
    contenido = ruta.read_text(encoding="utf-8")

    # Dividir por el separador de capítulos
    bloques = re.split(r'\n={50,}\n', contenido)
    capitulos = []

    i = 0
    while i < len(bloques):
        bloque = bloques[i].strip()
        if not bloque:
            i += 1
            continue

        # El patrón es: [vacío/sep] título [sep] contenido
        # Después del split, los bloques alternan: título, contenido
        lineas = bloque.split("\n")
        titulo = lineas[0].strip()

        # El contenido puede estar en el mismo bloque o en el siguiente
        if len(lineas) > 1:
            texto = "\n".join(lineas[1:]).strip()
        elif i + 1 < len(bloques):
            texto = bloques[i + 1].strip()
            i += 1
        else:
            texto = ""

        if titulo and texto:
            capitulos.append({"titulo": titulo, "texto": texto})

        i += 1

    # Fallback: si no se detectaron capítulos con el patrón, tratar todo como uno
    if not capitulos and contenido.strip():
        log("No se detectaron separadores de capítulo, procesando como texto único.", "WARN")
        capitulos = [{"titulo": ruta.stem, "texto": contenido.strip()}]

    return capitulos


# ── Generador de PDF ──────────────────────────────────────────────────────────

def registrar_fuentes():
    """Intenta registrar DejaVu (soporta español/Unicode). Fallback a Helvetica."""
    fuentes_candidatas = [
        # Windows
        ("C:/Windows/Fonts/DejaVuSans.ttf", "DejaVuSans"),
        ("C:/Windows/Fonts/Arial.ttf", "ArialUnicode"),
        ("C:/Windows/Fonts/calibri.ttf", "Calibri"),
        # Linux
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "LiberationSans"),
        # macOS
        ("/Library/Fonts/Arial.ttf", "ArialUnicode"),
        ("/System/Library/Fonts/Helvetica.ttc", "HelveticaMac"),
    ]
    for ruta_fuente, nombre in fuentes_candidatas:
        if os.path.exists(ruta_fuente):
            try:
                pdfmetrics.registerFont(TTFont(nombre, ruta_fuente))
                log(f"Fuente registrada: {nombre}", "OK")
                return nombre
            except Exception:
                continue

    log("Usando fuente Helvetica (caracteres especiales pueden verse mal)", "WARN")
    return "Helvetica"


def crear_estilos(fuente: str) -> dict:
    """Crea los estilos del PDF."""
    estilos_base = getSampleStyleSheet()

    titulo_novela = ParagraphStyle(
        "TituloNovela",
        parent=estilos_base["Title"],
        fontName=fuente,
        fontSize=22,
        leading=28,
        spaceAfter=20,
        textColor=colors.HexColor("#1a1a2e"),
        alignment=1,  # centrado
    )
    titulo_capitulo = ParagraphStyle(
        "TituloCapitulo",
        parent=estilos_base["Heading1"],
        fontName=fuente,
        fontSize=15,
        leading=20,
        spaceBefore=10,
        spaceAfter=14,
        textColor=colors.HexColor("#16213e"),
        alignment=1,
    )
    cuerpo = ParagraphStyle(
        "Cuerpo",
        parent=estilos_base["Normal"],
        fontName=fuente,
        fontSize=11,
        leading=17,
        spaceAfter=8,
        firstLineIndent=20,
        textColor=colors.HexColor("#2c2c2c"),
        alignment=4,  # justificado
    )
    nota = ParagraphStyle(
        "Nota",
        parent=estilos_base["Italic"],
        fontName=fuente,
        fontSize=9,
        textColor=colors.gray,
        alignment=1,
    )

    return {
        "titulo_novela": titulo_novela,
        "titulo_capitulo": titulo_capitulo,
        "cuerpo": cuerpo,
        "nota": nota,
    }


def escapar_xml(texto: str) -> str:
    """Escapa caracteres especiales para ReportLab Paragraph."""
    return (
        texto
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generar_pdf(
    capitulos: list[dict],
    ruta_salida: Path,
    titulo_novela: str,
    idioma_destino: str,
):
    """Genera el PDF final con todos los capítulos traducidos."""
    fuente = registrar_fuentes()
    estilos = crear_estilos(fuente)

    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=titulo_novela,
        author="NovelBin Scraper",
    )

    historia = []

    # ── Portada ────────────────────────────────────────────────────────────────
    historia.append(Spacer(1, 3 * cm))
    historia.append(Paragraph(escapar_xml(titulo_novela), estilos["titulo_novela"]))
    historia.append(Spacer(1, 0.5 * cm))
    historia.append(HRFlowable(width="60%", thickness=2, color=colors.HexColor("#16213e"), hAlign="CENTER"))
    historia.append(Spacer(1, 0.5 * cm))
    historia.append(Paragraph(
        f"Traducido al {IDIOMAS.get(idioma_destino, idioma_destino)} · {len(capitulos)} capítulos",
        estilos["nota"]
    ))
    historia.append(PageBreak())

    # ── Capítulos ──────────────────────────────────────────────────────────────
    for i, cap in enumerate(capitulos, 1):
        log(f"  Escribiendo capítulo {i}/{len(capitulos)}: {cap['titulo'][:50]}")

        historia.append(Paragraph(escapar_xml(cap["titulo"]), estilos["titulo_capitulo"]))
        historia.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        historia.append(Spacer(1, 0.3 * cm))

        # Dividir el contenido en párrafos
        parrafos = cap["texto"].split("\n")
        for parrafo in parrafos:
            parrafo = parrafo.strip()
            if parrafo:
                historia.append(Paragraph(escapar_xml(parrafo), estilos["cuerpo"]))

        if i < len(capitulos):
            historia.append(PageBreak())

    doc.build(historia)
    log(f"PDF generado: {ruta_salida}", "OK")


def guardar_txt_traducido(capitulos: list[dict], ruta: Path):
    """Guarda los capítulos traducidos como TXT manteniendo la estructura."""
    with open(ruta, "w", encoding="utf-8") as f:
        for cap in capitulos:
            f.write(f"\n{'='*70}\n")
            f.write(f"{cap['titulo']}\n")
            f.write(f"{'='*70}\n\n")
            f.write(cap["texto"])
            f.write("\n\n")
    log(f"TXT guardado: {ruta}", "OK")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Traductor + exportador PDF para novelas de novelbin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("archivo", nargs="?", help="Ruta al archivo TXT generado por el scraper")
    parser.add_argument("--idioma", "-i", default="es", help="Código de idioma destino (default: es)")
    parser.add_argument("--salida", "-o", default="./pdfs", help="Carpeta de salida (default: ./pdfs)")
    parser.add_argument("--idiomas", action="store_true", help="Mostrar idiomas disponibles y salir")
    parser.add_argument(
        "--formato-salida", choices=["pdf", "txt"], default="pdf",
        help="Formato del archivo traducido: pdf o txt (default: pdf)"
    )
    parser.add_argument(
        "--nombre", "-n", default="",
        help="Nombre personalizado para el archivo de salida (sin extensión)"
    )
    parser.add_argument(
        "--progreso", action="store_true",
        help="Emitir líneas JSON de progreso (usado por la GUI)"
    )

    args = parser.parse_args()

    global _MODO_PROGRESO
    _MODO_PROGRESO = args.progreso

    if args.idiomas:
        print("\nIdiomas disponibles:")
        for cod, nombre in IDIOMAS.items():
            print(f"  {cod:<10} {nombre}")
        return

    if not args.archivo:
        parser.print_help()
        return

    ruta_txt = Path(args.archivo)
    if not ruta_txt.exists():
        log(f"Archivo no encontrado: {ruta_txt}", "ERROR")
        return

    carpeta_salida = Path(args.salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    titulo_novela = ruta_txt.stem.replace("-", " ").replace("_", " ").title()
    nombre_base = limpiar_nombre_archivo(args.nombre) if args.nombre else ruta_txt.stem
    extension = ".pdf" if args.formato_salida == "pdf" else f"_{args.idioma}.txt"
    ruta_salida = carpeta_salida / f"{nombre_base}{extension}"

    log(f"Leyendo: {ruta_txt}")
    capitulos = parsear_txt(ruta_txt)
    log(f"Capítulos encontrados: {len(capitulos)}", "OK")

    if not capitulos:
        log("No se encontraron capítulos en el archivo.", "ERROR")
        return

    idioma_nombre = IDIOMAS.get(args.idioma, args.idioma)
    log(f"Traduciendo al {idioma_nombre}...")
    print()

    for i, cap in enumerate(capitulos, 1):
        log(f"[{i}/{len(capitulos)}] {cap['titulo'][:60]}", "TRAD")
        log_progreso(i, len(capitulos), titulo=cap["titulo"], estado="traduciendo")

        cap["titulo"] = traducir_texto(cap["titulo"], args.idioma)
        cap["texto"]  = traducir_texto(cap["texto"],  args.idioma)

        log_progreso(i, len(capitulos), titulo=cap["titulo"], estado="ok")

    print()
    if args.formato_salida == "pdf":
        log("Generando PDF...")
        generar_pdf(capitulos, ruta_salida, titulo_novela, args.idioma)
    else:
        log("Guardando TXT traducido...")
        guardar_txt_traducido(capitulos, ruta_salida)

    print()
    log(f"¡Listo! Archivo guardado en: {ruta_salida}", "OK")
    log(f"Capítulos: {len(capitulos)} | Idioma: {idioma_nombre}")


if __name__ == "__main__":
    main()