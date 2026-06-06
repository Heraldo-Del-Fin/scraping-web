"""
gui/tab_scraping.py
-------------------
Pestaña "Descargar" — interfaz para lanzar el scraper.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.perfiles import ids_disponibles
from gui.widgets import (
    BG2, BG3, FONT_MAIN, FONT_TITLE,
    ProcessRunner, action_button, append_log,
    folder_row, labeled_entry, log_box,
    progress_section, radio_group,
)

BASE_DIR = Path(__file__).parent.parent
SCRAPER  = BASE_DIR / "scraper_cli.py"


class TabScraping(tk.Frame):

    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.grid_columnconfigure(1, weight=1)
        self._runner = ProcessRunner()
        self._build()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build(self):
        tk.Label(self, text="📥  Descargar Novela", bg=BG2, fg="#eaeaea",
                 font=FONT_TITLE).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8))

        # Formulario
        inn = tk.Frame(self, bg=BG2)
        inn.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16)
        inn.grid_columnconfigure(1, weight=1)

        self.v_url    = labeled_entry(inn, "URL de la novela:", 0,
                                      "https://novelbin.me/novel-book/")
        self.v_nombre = labeled_entry(inn, "Nombre del archivo:", 1, "")
        self.v_caps   = labeled_entry(inn, "Capítulos a descargar:", 2, "10", width=10)
        self.v_salida = folder_row(inn, "Carpeta de destino:", 3,
                                   str(Path.home() / "novelas"))

        # Formato
        tk.Label(inn, text="Formato de salida:", bg=BG2, fg="#a0a0b0",
                 font=FONT_MAIN, anchor="w").grid(
            row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        self.v_fmt = tk.StringVar(value="txt")
        radio_group(inn, self.v_fmt,
                    [("TXT", "txt"), ("JSON", "json"), ("TXT por capítulo", "separados")],
                    row=4)

        # Perfil
        tk.Label(inn, text="Perfil de sitio:", bg=BG2, fg="#a0a0b0",
                 font=FONT_MAIN, anchor="w").grid(
            row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        self.v_perfil = tk.StringVar(value="(automático)")
        self._combo = ttk.Combobox(inn, textvariable=self.v_perfil,
                                    state="readonly", width=28, font=FONT_MAIN)
        self._combo.grid(row=5, column=1, sticky="w", pady=4)
        self.recargar_perfiles()

        # Opciones
        self.v_visible = tk.BooleanVar(value=False)
        tk.Checkbutton(inn, text="Mostrar navegador (debug)",
                       variable=self.v_visible,
                       bg=BG2, fg="#a0a0b0", selectcolor=BG3,
                       activebackground=BG2, font=FONT_MAIN).grid(
            row=6, column=1, sticky="w", pady=(2, 8))

        # Progreso
        self.pvar, self.lbl_cap = progress_section(self, row=2)

        # Botones
        bf = tk.Frame(self, bg=BG2)
        bf.grid(row=4, column=0, columnspan=3, pady=10, padx=16, sticky="w")
        self.btn_start = action_button(bf, "▶  Iniciar descarga", self._iniciar)
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_detect = action_button(bf, "🔍 Detectar selectores",
                                        self._detectar, width=20, color=BG3)
        self.btn_detect.pack(side="left", padx=(0, 8))
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

    def recargar_perfiles(self):
        vals = ["(automático)"] + ids_disponibles()
        self._combo["values"] = vals
        if self.v_perfil.get() not in vals:
            self.v_perfil.set("(automático)")

    def _limpiar(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.pvar.set(0)
        self.lbl_cap.configure(text="")
        self.btn_start.configure(state="disabled")
        self.btn_detect.configure(state="disabled")
        self.btn_stop.configure(state="normal")

    def _finalizar(self):
        self.pvar.set(100)
        self.btn_start.configure(state="normal")
        self.btn_detect.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def _validar(self) -> bool:
        if not self.v_url.get().strip().startswith("http"):
            messagebox.showerror("Error", "Ingresa una URL válida.")
            return False
        try:
            assert int(self.v_caps.get()) > 0
        except Exception:
            messagebox.showerror("Error", "Capítulos debe ser un número positivo.")
            return False
        return True

    def _cmd_base(self) -> list[str]:
        cmd = [sys.executable, str(SCRAPER),
               self.v_url.get().strip(),
               "--capitulos", self.v_caps.get().strip(),
               "--formato",   self.v_fmt.get(),
               "--salida",    self.v_salida.get().strip(),
               "--progreso"]
        if self.v_nombre.get().strip():
            cmd += ["--nombre", self.v_nombre.get().strip()]
        if self.v_perfil.get() != "(automático)":
            cmd += ["--sitio", self.v_perfil.get()]
        if self.v_visible.get():
            cmd.append("--visible")
        return cmd

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _iniciar(self):
        if not self._validar():
            return
        self._limpiar()
        self._runner.run(self._cmd_base(), self.log,
                         self.pvar, self.lbl_cap, self._finalizar, self)

    def _detectar(self):
        url = self.v_url.get().strip()
        if not url.startswith("http"):
            messagebox.showerror("Error", "Ingresa una URL de capítulo válida.")
            return
        self._limpiar()
        cmd = [sys.executable, str(SCRAPER), url, "--detectar"]
        if self.v_visible.get():
            cmd.append("--visible")

        def done():
            self._finalizar()
            self.recargar_perfiles()
            append_log(self.log, "[OK] Perfil guardado. Combo actualizado.")

        self._runner.run(cmd, self.log, self.pvar, self.lbl_cap, done, self)

    def _detener(self):
        self._runner.stop()
        append_log(self.log, "Proceso detenido por el usuario.")
        self._finalizar()