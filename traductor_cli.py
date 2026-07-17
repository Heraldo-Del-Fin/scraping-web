"""
traductor_cli.py
----------------
Punto de entrada CLI para el traductor + exportador.
La GUI lo llama como subproceso; también funciona desde la terminal.

Uso:
    python traductor_cli.py <archivo.txt|pdf> [opciones]
    python traductor_cli.py novelas/mi-novela.txt --idioma es --formato-salida pdf
    python traductor_cli.py novelas/mi-novela.pdf --idioma es --formato-salida pdf
"""

import argparse
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from traductor.exportar_pdf import guardar as exportar_traducido
from traductor.traducir import IDIOMAS, set_modo_progreso, traducir_capitulos


# ── Parser de TXT scrapeado ───────────────────────────────────────────────────

def parsear_txt(ruta: Path) -> list[dict]:
    """Lee el TXT generado por scraper_cli.py y lo separa en capítulos."""
    contenido = ruta.read_text(encoding="utf-8", errors="replace")
    bloques   = re.split(r'\n={50,}\n', contenido)
    caps      = []
    i         = 0

    while i < len(bloques):
        bloque = bloques[i].strip()
        if not bloque:
            i += 1
            continue
        lineas = bloque.split("\n")
        titulo = lineas[0].strip()
        texto  = "\n".join(lineas[1:]).strip() if len(lineas) > 1 else ""
        if not texto and i + 1 < len(bloques):
            texto = bloques[i + 1].strip()
            i += 1
        if titulo and texto:
            caps.append({"titulo": titulo, "texto": texto})
        i += 1

    if not caps and contenido.strip():
        caps = [{"titulo": ruta.stem, "texto": contenido.strip()}]
    return caps


# ── Parser de PDF ─────────────────────────────────────────────────────────────

def parsear_pdf(ruta: Path) -> list[dict]:
    """
    Extrae texto de un PDF y lo separa en capítulos.
    Estrategia:
      1. Busca separadores de capítulo comunes en el texto (Chapter N, Capítulo N,
         líneas en mayúsculas cortas, etc.)
      2. Si no encuentra ninguno, trata cada página como un capítulo.
      3. Si el PDF tiene una sola página, lo trata como texto único.
    """
    try:
        import pypdf
    except ImportError:
        print("[X] Falta pypdf. Ejecuta: pip install pypdf", flush=True)
        sys.exit(1)

    print(f"[i] Extrayendo texto del PDF ({ruta.name})...", flush=True)

    # Extraer texto página a página
    paginas = []
    try:
        reader = pypdf.PdfReader(str(ruta))
        total  = len(reader.pages)
        print(f"[i] Paginas encontradas: {total}", flush=True)
        for i, pagina in enumerate(reader.pages, 1):
            texto = pagina.extract_text() or ""
            texto = texto.strip()
            if texto:
                paginas.append(texto)
    except Exception as e:
        print(f"[X] Error leyendo PDF: {e}", flush=True)
        sys.exit(1)

    if not paginas:
        print("[X] No se pudo extraer texto del PDF. "
              "Puede estar escaneado (solo imagenes).", flush=True)
        sys.exit(1)

    texto_completo = "\n\n".join(paginas)

    # ── Intentar detectar separadores de capítulo ─────────────────────────────
    # Patrones comunes de encabezados de capítulo
    patron_capitulo = re.compile(
        r'(?:^|\n)'
        r'(?:'
        r'Chapter\s+\d+[^\n]*|'       # Chapter 1 / Chapter 1: Title
        r'CHAPTER\s+\d+[^\n]*|'       # CHAPTER 1
        r'Cap[ií]tulo\s+\d+[^\n]*|'   # Capítulo 1 / Capitulo 1
        r'CAP[IÍ]TULO\s+\d+[^\n]*|'  # CAPÍTULO 1
        r'Part\s+\d+[^\n]*|'          # Part 1
        r'Parte\s+\d+[^\n]*|'         # Parte 1
        r'Prologue[^\n]*|'             # Prologue
        r'Epilogue[^\n]*|'             # Epilogue
        r'Prólogo[^\n]*|'              # Prólogo
        r'Epílogo[^\n]*'               # Epílogo
        r')',
        re.IGNORECASE | re.MULTILINE
    )

    matches = list(patron_capitulo.finditer(texto_completo))

    if len(matches) >= 2:
        # Encontró separadores — dividir por ellos
        caps = []
        for idx, match in enumerate(matches):
            titulo = match.group().strip()
            inicio = match.end()
            fin    = matches[idx + 1].start() if idx + 1 < len(matches) else len(texto_completo)
            texto  = texto_completo[inicio:fin].strip()
            if texto:
                caps.append({"titulo": titulo, "texto": texto})
        if caps:
            print(f"[OK] {len(caps)} capitulos detectados por encabezados.", flush=True)
            return caps

    # ── Fallback: una página = un capítulo ───────────────────────────────────
    if len(paginas) > 1:
        caps = []
        for i, texto in enumerate(paginas, 1):
            if texto.strip():
                caps.append({"titulo": f"Página {i}", "texto": texto})
        print(f"[OK] {len(caps)} paginas como capitulos (sin encabezados detectados).",
              flush=True)
        return caps

    # ── Último fallback: todo el texto como un único bloque ──────────────────
    print("[OK] PDF procesado como bloque único.", flush=True)
    return [{"titulo": ruta.stem, "texto": texto_completo}]


# ── Selección automática de parser ────────────────────────────────────────────

def parsear_archivo(ruta: Path) -> list[dict]:
    """Selecciona el parser según la extensión del archivo."""
    ext = ruta.suffix.lower()
    if ext == ".pdf":
        return parsear_pdf(ruta)
    elif ext in (".txt", ".text", ""):
        return parsear_txt(ruta)
    else:
        # Intentar como TXT para otros formatos de texto plano
        print(f"[!] Extension '{ext}' no reconocida, intentando como TXT.", flush=True)
        return parsear_txt(ruta)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Traductor + exportador para novelas scrapeadas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("archivo",  nargs="?",
                        help="Ruta al archivo a traducir (.txt o .pdf)")
    parser.add_argument("--idioma",         "-i", default="es")
    parser.add_argument("--formato-salida", choices=["pdf", "txt"], default="pdf")
    parser.add_argument("--salida",         "-o", default="./pdfs")
    parser.add_argument("--nombre",         "-n", default="")
    parser.add_argument("--listar-idiomas", action="store_true")
    parser.add_argument("--progreso",       action="store_true")
    args = parser.parse_args()

    set_modo_progreso(args.progreso)

    if args.listar_idiomas:
        print("\nIdiomas disponibles:")
        for cod, nombre in IDIOMAS.items():
            print(f"  {cod:<12} {nombre}")
        return

    if not args.archivo:
        parser.print_help()
        return

    ruta = Path(args.archivo)
    if not ruta.exists():
        print(f"[X] Archivo no encontrado: {ruta}", flush=True)
        sys.exit(1)

    carpeta = Path(args.salida)
    carpeta.mkdir(parents=True, exist_ok=True)

    nombre_base   = args.nombre or ruta.stem
    titulo_novela = nombre_base.replace("-", " ").replace("_", " ").title()
    extension     = ".pdf" if args.formato_salida == "pdf" else f"_{args.idioma}.txt"
    ruta_salida   = carpeta / f"{nombre_base}{extension}"

    print(f"[i] Leyendo: {ruta} ({ruta.suffix.upper()[1:] or 'TXT'})", flush=True)
    caps = parsear_archivo(ruta)

    if not caps:
        print("[X] No se encontraron capitulos.", flush=True)
        sys.exit(1)

    print(f"[OK] {len(caps)} capitulos listos para traducir.", flush=True)

    idioma_nombre = IDIOMAS.get(args.idioma, args.idioma)
    print(f"[i] Traduciendo al {idioma_nombre}...\n", flush=True)
    caps = traducir_capitulos(caps, args.idioma)

    print(f"\n[i] Exportando como {args.formato_salida.upper()}...", flush=True)
    exportar_traducido(caps, args.formato_salida, ruta_salida, titulo_novela, args.idioma)
    print(f"\n[OK] Listo: {ruta_salida}", flush=True)


if __name__ == "__main__":
    main()