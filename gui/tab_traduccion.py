"""
gui/tab_traduccion.py
---------------------
Pestaña "Traducir" — interfaz para traducir y exportar novelas.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from gui.widgets import (
    BG2, BG3, FONT_MAIN, FONT_TITLE,
    ProcessRunner, action_button, append_log,
    folder_row, labeled_entry, log_box,
    progress_section, radio_group,
)

BASE_DIR  = Path(__file__).parent.parent
TRADUCTOR = BASE_DIR / "traductor_cli.py"

IDIOMAS = {
    "Español": "es",   "Portugués": "pt",  "Francés": "fr",
    "Alemán":  "de",   "Italiano":  "it",  "Japonés": "ja",
    "Coreano": "ko",   "Chino Simplificado": "zh-CN",
    "Ruso":    "ru",   "Árabe":     "ar",
}


class TabTraduccion(tk.Frame):

    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.grid_columnconfigure(1, weight=1)
        self._runner = ProcessRunner()
        self._build()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build(self):
        tk.Label(self, text="🌐  Traducir y Exportar", bg=BG2, fg="#eaeaea",
                 font=FONT_TITLE).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8))

        inn = tk.Frame(self, bg=BG2)
        inn.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16)
        inn.grid_columnconfigure(1, weight=1)

        # Archivo de entrada
        tk.Label(inn, text="Archivo (TXT o PDF):", bg=BG2, fg="#a0a0b0",
                 font=FONT_MAIN, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.v_archivo = tk.StringVar()
        tk.Entry(inn, textvariable=self.v_archivo, bg="#0d1b2a", fg="#eaeaea",
                 insertbackground="#eaeaea", font=FONT_MAIN, width=36,
                 relief="flat", bd=4).grid(row=0, column=1, sticky="ew", pady=4)
        tk.Button(inn, text="📂", bg=BG3, fg="#eaeaea", activebackground="#e94560",
                  relief="flat", bd=0, cursor="hand2",
                  command=self._elegir_archivo).grid(
            row=0, column=2, padx=(6, 0), pady=4)

        self.v_nombre = labeled_entry(inn, "Nombre del archivo:", 1, "")

        # Idioma
        tk.Label(inn, text="Idioma destino:", bg=BG2, fg="#a0a0b0",
                 font=FONT_MAIN, anchor="w").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.v_idioma = tk.StringVar(value="Español")
        ttk.Combobox(inn, textvariable=self.v_idioma,
                     values=list(IDIOMAS.keys()),
                     state="readonly", width=22, font=FONT_MAIN).grid(
            row=2, column=1, sticky="w", pady=4)

        # Formato salida
        tk.Label(inn, text="Formato de salida:", bg=BG2, fg="#a0a0b0",
                 font=FONT_MAIN, anchor="w").grid(
            row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.v_fmt = tk.StringVar(value="pdf")
        radio_group(inn, self.v_fmt, [("PDF", "pdf"), ("TXT traducido", "txt")], row=3)

        self.v_salida = folder_row(inn, "Carpeta de destino:", 4,
                                    str(Path.home() / "pdfs"))

        # Progreso
        self.pvar, self.lbl_cap = progress_section(self, row=2)

        # Botones
        bf = tk.Frame(self, bg=BG2)
        bf.grid(row=4, column=0, columnspan=3, pady=10, padx=16, sticky="w")
        self.btn_start = action_button(bf, "▶  Iniciar traducción", self._iniciar)
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_stop = action_button(bf, "⏹ Detener", self._detener,
                                      width=12, color=BG3)
        self.btn_stop.configure(state="disabled")
        self.btn_stop.pack(side="left")

        # Log
        tk.Label(self, text="Registro:", bg=BG2, fg="#a0a0b0",
                 font=FONT_MAIN).grid(row=5, column=0, sticky="w", padx=16)
        self.log = log_box(self, row=6)
        self.grid_rowconfigure(6, weight=1)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _elegir_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo a traducir",
            filetypes=[
                ("Archivos compatibles", "*.txt *.pdf"),
                ("Texto", "*.txt"),
                ("PDF", "*.pdf"),
                ("Todos", "*.*"),
            ],
        )
        if ruta:
            self.v_archivo.set(ruta)
            if not self.v_nombre.get():
                self.v_nombre.set(Path(ruta).stem)

    def _limpiar(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.pvar.set(0)
        self.lbl_cap.configure(text="")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

    def _finalizar(self):
        self.pvar.set(100)
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _iniciar(self):
        archivo = self.v_archivo.get().strip()
        if not archivo:
            messagebox.showerror("Error", "Selecciona un archivo TXT.")
            return
        if not Path(archivo).exists():
            messagebox.showerror("Error", "El archivo no existe.")
            return

        self._limpiar()
        codigo = IDIOMAS.get(self.v_idioma.get(), "es")
        cmd = [sys.executable, str(TRADUCTOR), archivo,
               "--idioma",         codigo,
               "--formato-salida", self.v_fmt.get(),
               "--salida",         self.v_salida.get().strip(),
               "--progreso"]
        if self.v_nombre.get().strip():
            cmd += ["--nombre", self.v_nombre.get().strip()]

        self._runner.run(cmd, self.log, self.pvar, self.lbl_cap,
                         self._finalizar, self)

    def _detener(self):
        self._runner.stop()
        append_log(self.log, "Proceso detenido por el usuario.")
        self._finalizar()