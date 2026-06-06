"""
gui/app.py
----------
Ventana principal. Ensambla las pestañas y aplica el tema.
"""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from gui.tab_perfiles import TabPerfiles
from gui.tab_scraping import TabScraping
from gui.tab_traduccion import TabTraduccion
from gui.widgets import BG, BG2, ACCENT, FG, FG2, aplicar_tema

BASE_DIR  = Path(__file__).parent.parent
SCRAPER   = BASE_DIR / "scraper_cli.py"
TRADUCTOR = BASE_DIR / "traductor_cli.py"


class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Novel Scraper & Translator")
        self.configure(bg=BG)
        self.geometry("840x760")
        self.minsize(720, 620)
        aplicar_tema(self)
        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=BG, pady=10)
        hdr.pack(fill="x", padx=20)
        tk.Label(hdr, text="📚  Novel Scraper", bg=BG, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(hdr, text="Descarga · Traduce · Exporta · Multi-sitio",
                 bg=BG, fg=FG2, font=("Segoe UI", 10)).pack(side="left", padx=12)
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x", padx=20, pady=(0, 8))

        # Notebook
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tab_scrap = TabScraping(nb)
        self.tab_trad  = TabTraduccion(nb)
        self.tab_perf  = TabPerfiles(nb)

        nb.add(self.tab_scrap, text="  📥  Descargar  ")
        nb.add(self.tab_trad,  text="  🌐  Traducir  ")
        nb.add(self.tab_perf,  text="  ⚙  Perfiles  ")

        # Recargar combo de perfiles al volver a la pestaña de descarga
        nb.bind("<<NotebookTabChanged>>",
                lambda _: self.tab_scrap.recargar_perfiles())

        self.after(300, self._check_scripts)

    def _check_scripts(self):
        faltantes = [s.name for s in [SCRAPER, TRADUCTOR] if not s.exists()]
        if faltantes:
            messagebox.showwarning(
                "Archivos no encontrados",
                "No se encontraron estos scripts en la carpeta del proyecto:\n\n"
                + "\n".join(f"  • {f}" for f in faltantes)
                + "\n\nAsegúrate de tener scraper_cli.py y traductor_cli.py.",
            )