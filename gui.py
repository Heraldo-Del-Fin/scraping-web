"""
NovelBin GUI
============
Interfaz gráfica para novelbin_scraper.py y traducir_a_pdf.py.
Requiere que ambos scripts estén en la misma carpeta que este archivo.

Dependencias (además de las de los otros scripts):
    - tkinter  (incluido en Python estándar en Windows/macOS)
    - En Linux: sudo apt install python3-tk

Uso:
    python gui.py
"""

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# ── Ruta base (misma carpeta que gui.py) ──────────────────────────────────────
BASE_DIR = Path(__file__).parent
SCRAPER  = BASE_DIR / "scraping.py"
TRADUCTOR = BASE_DIR / "traducir_pdf.py"

IDIOMAS = {
    "Español":             "es",
    "Portugués":           "pt",
    "Francés":             "fr",
    "Alemán":              "de",
    "Italiano":            "it",
    "Japonés":             "ja",
    "Coreano":             "ko",
    "Chino Simplificado":  "zh-CN",
    "Ruso":                "ru",
    "Árabe":               "ar",
}

# ── Colores / tema ─────────────────────────────────────────────────────────────
BG        = "#1a1a2e"
BG2       = "#16213e"
BG3       = "#0f3460"
ACCENT    = "#e94560"
FG        = "#eaeaea"
FG2       = "#a0a0b0"
ENTRY_BG  = "#0d1b2a"
BTN_BG    = "#e94560"
BTN_FG    = "#ffffff"
BTN_ACT   = "#c73652"
GREEN     = "#4ecca3"
YELLOW    = "#f5a623"
FONT_MAIN = ("Segoe UI", 10)
FONT_HEAD = ("Segoe UI", 12, "bold")
FONT_MONO = ("Consolas", 9)


# ══════════════════════════════════════════════════════════════════════════════
#  Widgets reutilizables
# ══════════════════════════════════════════════════════════════════════════════

def labeled_entry(parent, label, row, default="", width=48, colspan=2):
    tk.Label(parent, text=label, bg=BG2, fg=FG2, font=FONT_MAIN, anchor="w")\
        .grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
    var = tk.StringVar(value=default)
    e = tk.Entry(parent, textvariable=var, bg=ENTRY_BG, fg=FG, insertbackground=FG,
                 font=FONT_MAIN, width=width, relief="flat", bd=4)
    e.grid(row=row, column=1, columnspan=colspan, sticky="ew", pady=4)
    return var


def folder_row(parent, label, row, default=""):
    tk.Label(parent, text=label, bg=BG2, fg=FG2, font=FONT_MAIN, anchor="w")\
        .grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
    var = tk.StringVar(value=default)
    e = tk.Entry(parent, textvariable=var, bg=ENTRY_BG, fg=FG, insertbackground=FG,
                 font=FONT_MAIN, width=38, relief="flat", bd=4)
    e.grid(row=row, column=1, sticky="ew", pady=4)
    btn = tk.Button(parent, text="📂", bg=BG3, fg=FG, activebackground=ACCENT,
                    relief="flat", bd=0, cursor="hand2",
                    command=lambda: var.set(filedialog.askdirectory() or var.get()))
    btn.grid(row=row, column=2, padx=(6, 0), pady=4)
    return var


def action_button(parent, text, command, width=18):
    return tk.Button(parent, text=text, command=command,
                     bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACT,
                     font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                     cursor="hand2", width=width, pady=6)


def log_box(parent, row, colspan=3, height=12):
    frame = tk.Frame(parent, bg=BG)
    frame.grid(row=row, column=0, columnspan=colspan, sticky="nsew", pady=(12, 0))
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    txt = tk.Text(frame, bg="#0a0e1a", fg=GREEN, font=FONT_MONO,
                  relief="flat", bd=6, height=height, wrap="word",
                  state="disabled")
    txt.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
    sb.grid(row=0, column=1, sticky="ns")
    txt.configure(yscrollcommand=sb.set)
    # Tags de color
    txt.tag_configure("ok",    foreground=GREEN)
    txt.tag_configure("warn",  foreground=YELLOW)
    txt.tag_configure("error", foreground=ACCENT)
    txt.tag_configure("info",  foreground=FG2)
    return txt


def append_log(txt_widget, line):
    """Añade una línea al log con color según el tipo."""
    tag = "info"
    if "✅" in line or "OK" in line:
        tag = "ok"
    elif "⚠️" in line or "WARN" in line:
        tag = "warn"
    elif "❌" in line or "ERROR" in line:
        tag = "error"

    txt_widget.configure(state="normal")
    txt_widget.insert("end", line + "\n", tag)
    txt_widget.see("end")
    txt_widget.configure(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
#  Pestaña 1 — Scraping
# ══════════════════════════════════════════════════════════════════════════════

class PestañaScraping(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self._proceso = None
        self._construir()

    def _construir(self):
        self.grid_columnconfigure(1, weight=1)

        # ── Título ─────────────────────────────────────────────────────────────
        tk.Label(self, text="📥  Descargar Novela", bg=BG2, fg=FG,
                 font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8))

        inner = tk.Frame(self, bg=BG2)
        inner.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16)
        inner.grid_columnconfigure(1, weight=1)

        # ── Campos ─────────────────────────────────────────────────────────────
        self.url     = labeled_entry(inner, "URL de la novela:", 0,
                                     "https://novelbin.me/novel-book/")
        self.nombre  = labeled_entry(inner, "Nombre del archivo:", 1, "")
        self.caps    = labeled_entry(inner, "Capítulos a descargar:", 2, "10", width=10)
        self.salida  = folder_row(inner, "Carpeta de destino:", 3,
                                   str(Path.home() / "novelas"))

        # ── Formato ────────────────────────────────────────────────────────────
        tk.Label(inner, text="Formato de salida:", bg=BG2, fg=FG2,
                 font=FONT_MAIN, anchor="w").grid(
            row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        self.formato = tk.StringVar(value="txt")
        fmt_frame = tk.Frame(inner, bg=BG2)
        fmt_frame.grid(row=4, column=1, sticky="w")
        for txt, val in [("TXT (un archivo)", "txt"),
                          ("JSON", "json"),
                          ("TXT por capítulo", "separados")]:
            tk.Radiobutton(fmt_frame, text=txt, variable=self.formato, value=val,
                           bg=BG2, fg=FG, selectcolor=BG3, activebackground=BG2,
                           font=FONT_MAIN).pack(side="left", padx=8)

        # ── Opciones ───────────────────────────────────────────────────────────
        self.visible = tk.BooleanVar(value=False)
        tk.Checkbutton(inner, text="Mostrar navegador (debug)",
                       variable=self.visible, bg=BG2, fg=FG2,
                       selectcolor=BG3, activebackground=BG2,
                       font=FONT_MAIN).grid(
            row=5, column=1, sticky="w", pady=(2, 8))

        # ── Barra de progreso ──────────────────────────────────────────────────
        tk.Label(self, text="Progreso:", bg=BG2, fg=FG2, font=FONT_MAIN).grid(
            row=2, column=0, sticky="w", padx=16, pady=(8, 0))
        self.progreso_var = tk.DoubleVar(value=0)
        self.barra = ttk.Progressbar(self, variable=self.progreso_var,
                                     maximum=100, mode="determinate",
                                     style="Accent.Horizontal.TProgressbar")
        self.barra.grid(row=2, column=1, columnspan=2, sticky="ew",
                        padx=(8, 16), pady=(8, 0))
        self.lbl_cap = tk.Label(self, text="", bg=BG2, fg=FG2, font=FONT_MAIN)
        self.lbl_cap.grid(row=3, column=0, columnspan=3, sticky="w",
                          padx=16, pady=(2, 0))

        # ── Botones ────────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=BG2)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=10, padx=16, sticky="w")
        self.btn_start = action_button(btn_frame, "▶  Iniciar descarga",
                                       self._iniciar)
        self.btn_start.pack(side="left", padx=(0, 10))
        self.btn_stop = action_button(btn_frame, "⏹  Detener",
                                      self._detener, width=12)
        self.btn_stop.configure(bg=BG3, state="disabled")
        self.btn_stop.pack(side="left")

        # ── Log ────────────────────────────────────────────────────────────────
        tk.Label(self, text="Registro:", bg=BG2, fg=FG2, font=FONT_MAIN).grid(
            row=5, column=0, sticky="w", padx=16)
        self.log = log_box(self, row=6, colspan=3)
        self.grid_rowconfigure(6, weight=1)

    # ── Lógica ─────────────────────────────────────────────────────────────────

    def _validar(self):
        url = self.url.get().strip()
        if not url.startswith("http"):
            messagebox.showerror("Error", "Ingresa una URL válida.")
            return False
        try:
            caps = int(self.caps.get())
            assert caps > 0
        except Exception:
            messagebox.showerror("Error", "La cantidad de capítulos debe ser un número positivo.")
            return False
        return True

    def _iniciar(self):
        if not self._validar():
            return

        # Limpiar log y barra
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.progreso_var.set(0)
        self.lbl_cap.configure(text="")

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        # Construir comando
        cmd = [sys.executable, str(SCRAPER),
               self.url.get().strip(),
               "--capitulos", self.caps.get().strip(),
               "--formato", self.formato.get(),
               "--salida", self.salida.get().strip(),
               "--progreso"]
        nombre = self.nombre.get().strip()
        if nombre:
            cmd += ["--nombre", nombre]
        if self.visible.get():
            cmd.append("--visible")

        threading.Thread(target=self._correr, args=(cmd,), daemon=True).start()

    def _correr(self, cmd):
        try:
            self._proceso = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            caps_total = int(self.caps.get().strip())
            for linea in self._proceso.stdout:
                linea = linea.rstrip()
                if linea.startswith("PROGRESO:"):
                    try:
                        data = json.loads(linea[9:])
                        pct = (data["actual"] / max(data["total"], 1)) * 100
                        titulo = data.get("titulo", "")[:55]
                        self.after(0, self._actualizar_barra, pct,
                                   f"Capítulo {data['actual']}/{data['total']}  {titulo}")
                    except Exception:
                        pass
                else:
                    self.after(0, append_log, self.log, linea)
            self._proceso.wait()
        except Exception as e:
            self.after(0, append_log, self.log, f"❌ Error al ejecutar el scraper: {e}")
        finally:
            self.after(0, self._finalizar)

    def _actualizar_barra(self, pct, texto):
        self.progreso_var.set(pct)
        self.lbl_cap.configure(text=texto)

    def _finalizar(self):
        self.progreso_var.set(100)
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._proceso = None

    def _detener(self):
        if self._proceso:
            self._proceso.terminate()
            append_log(self.log, "⏹ Proceso detenido por el usuario.")
        self._finalizar()


# ══════════════════════════════════════════════════════════════════════════════
#  Pestaña 2 — Traducción
# ══════════════════════════════════════════════════════════════════════════════

class PestañaTraduccion(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self._proceso = None
        self._construir()

    def _construir(self):
        self.grid_columnconfigure(1, weight=1)

        tk.Label(self, text="🌐  Traducir y Exportar", bg=BG2, fg=FG,
                 font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8))

        inner = tk.Frame(self, bg=BG2)
        inner.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16)
        inner.grid_columnconfigure(1, weight=1)

        # ── Archivo de entrada ─────────────────────────────────────────────────
        tk.Label(inner, text="Archivo TXT a traducir:", bg=BG2, fg=FG2,
                 font=FONT_MAIN, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.archivo = tk.StringVar()
        tk.Entry(inner, textvariable=self.archivo, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, font=FONT_MAIN, width=38,
                 relief="flat", bd=4).grid(row=0, column=1, sticky="ew", pady=4)
        tk.Button(inner, text="📂", bg=BG3, fg=FG, activebackground=ACCENT,
                  relief="flat", bd=0, cursor="hand2",
                  command=self._elegir_archivo).grid(
            row=0, column=2, padx=(6, 0), pady=4)

        # ── Nombre salida ──────────────────────────────────────────────────────
        self.nombre = labeled_entry(inner, "Nombre del archivo:", 1, "")

        # ── Idioma ─────────────────────────────────────────────────────────────
        tk.Label(inner, text="Idioma destino:", bg=BG2, fg=FG2,
                 font=FONT_MAIN, anchor="w").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.idioma_nombre = tk.StringVar(value="Español")
        combo = ttk.Combobox(inner, textvariable=self.idioma_nombre,
                             values=list(IDIOMAS.keys()),
                             state="readonly", width=22,
                             font=FONT_MAIN)
        combo.grid(row=2, column=1, sticky="w", pady=4)

        # ── Formato salida ─────────────────────────────────────────────────────
        tk.Label(inner, text="Formato de salida:", bg=BG2, fg=FG2,
                 font=FONT_MAIN, anchor="w").grid(
            row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.fmt_salida = tk.StringVar(value="pdf")
        fmt_frame = tk.Frame(inner, bg=BG2)
        fmt_frame.grid(row=3, column=1, sticky="w")
        for txt, val in [("PDF", "pdf"), ("TXT traducido", "txt")]:
            tk.Radiobutton(fmt_frame, text=txt, variable=self.fmt_salida, value=val,
                           bg=BG2, fg=FG, selectcolor=BG3, activebackground=BG2,
                           font=FONT_MAIN).pack(side="left", padx=8)

        # ── Carpeta de salida ──────────────────────────────────────────────────
        self.salida = folder_row(inner, "Carpeta de destino:", 4,
                                  str(Path.home() / "pdfs"))

        # ── Barra de progreso ──────────────────────────────────────────────────
        tk.Label(self, text="Progreso:", bg=BG2, fg=FG2, font=FONT_MAIN).grid(
            row=2, column=0, sticky="w", padx=16, pady=(8, 0))
        self.progreso_var = tk.DoubleVar(value=0)
        self.barra = ttk.Progressbar(self, variable=self.progreso_var,
                                     maximum=100, mode="determinate",
                                     style="Accent.Horizontal.TProgressbar")
        self.barra.grid(row=2, column=1, columnspan=2, sticky="ew",
                        padx=(8, 16), pady=(8, 0))
        self.lbl_cap = tk.Label(self, text="", bg=BG2, fg=FG2, font=FONT_MAIN)
        self.lbl_cap.grid(row=3, column=0, columnspan=3, sticky="w",
                          padx=16, pady=(2, 0))

        # ── Botones ────────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=BG2)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=10, padx=16, sticky="w")
        self.btn_start = action_button(btn_frame, "▶  Iniciar traducción",
                                       self._iniciar)
        self.btn_start.pack(side="left", padx=(0, 10))
        self.btn_stop = action_button(btn_frame, "⏹  Detener",
                                      self._detener, width=12)
        self.btn_stop.configure(bg=BG3, state="disabled")
        self.btn_stop.pack(side="left")

        # ── Log ────────────────────────────────────────────────────────────────
        tk.Label(self, text="Registro:", bg=BG2, fg=FG2, font=FONT_MAIN).grid(
            row=5, column=0, sticky="w", padx=16)
        self.log = log_box(self, row=6, colspan=3)
        self.grid_rowconfigure(6, weight=1)

    # ── Lógica ─────────────────────────────────────────────────────────────────

    def _elegir_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo TXT",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos", "*.*")]
        )
        if ruta:
            self.archivo.set(ruta)
            # Auto-rellenar nombre si está vacío
            if not self.nombre.get().strip():
                self.nombre.set(Path(ruta).stem)

    def _validar(self):
        if not self.archivo.get().strip():
            messagebox.showerror("Error", "Selecciona un archivo TXT.")
            return False
        if not Path(self.archivo.get()).exists():
            messagebox.showerror("Error", "El archivo seleccionado no existe.")
            return False
        return True

    def _iniciar(self):
        if not self._validar():
            return

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.progreso_var.set(0)
        self.lbl_cap.configure(text="")

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        codigo_idioma = IDIOMAS.get(self.idioma_nombre.get(), "es")

        cmd = [sys.executable, str(TRADUCTOR),
               self.archivo.get().strip(),
               "--idioma", codigo_idioma,
               "--formato-salida", self.fmt_salida.get(),
               "--salida", self.salida.get().strip(),
               "--progreso"]
        nombre = self.nombre.get().strip()
        if nombre:
            cmd += ["--nombre", nombre]

        threading.Thread(target=self._correr, args=(cmd,), daemon=True).start()

    def _correr(self, cmd):
        try:
            self._proceso = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            for linea in self._proceso.stdout:
                linea = linea.rstrip()
                if linea.startswith("PROGRESO:"):
                    try:
                        data = json.loads(linea[9:])
                        pct = (data["actual"] / max(data["total"], 1)) * 100
                        titulo = data.get("titulo", "")[:55]
                        self.after(0, self._actualizar_barra, pct,
                                   f"Capítulo {data['actual']}/{data['total']}  {titulo}")
                    except Exception:
                        pass
                else:
                    self.after(0, append_log, self.log, linea)
            self._proceso.wait()
        except Exception as e:
            self.after(0, append_log, self.log, f"❌ Error al ejecutar el traductor: {e}")
        finally:
            self.after(0, self._finalizar)

    def _actualizar_barra(self, pct, texto):
        self.progreso_var.set(pct)
        self.lbl_cap.configure(text=texto)

    def _finalizar(self):
        self.progreso_var.set(100)
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._proceso = None

    def _detener(self):
        if self._proceso:
            self._proceso.terminate()
            append_log(self.log, "⏹ Proceso detenido por el usuario.")
        self._finalizar()


# ══════════════════════════════════════════════════════════════════════════════
#  Ventana principal
# ══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NovelBin Scraper & Translator")
        self.configure(bg=BG)
        self.geometry("780x680")
        self.minsize(700, 580)
        self._aplicar_tema()
        self._construir()

    def _aplicar_tema(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Progressbar
        style.configure("Accent.Horizontal.TProgressbar",
                         troughcolor=BG3, background=ACCENT,
                         bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)

        # Notebook (pestañas)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG3, foreground=FG2,
                         padding=[16, 6], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", BG2)],
                  foreground=[("selected", FG)])

        # Combobox
        style.configure("TCombobox", fieldbackground=ENTRY_BG,
                         background=BG3, foreground=FG,
                         arrowcolor=FG, selectbackground=BG3)

    def _construir(self):
        # ── Header ─────────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=BG, pady=10)
        header.pack(fill="x", padx=20)
        tk.Label(header, text="📚  NovelBin Scraper", bg=BG, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(header, text="Descarga · Traduce · Exporta",
                 bg=BG, fg=FG2, font=("Segoe UI", 10)).pack(side="left", padx=12)

        sep = tk.Frame(self, bg=ACCENT, height=2)
        sep.pack(fill="x", padx=20, pady=(0, 8))

        # ── Pestañas ───────────────────────────────────────────────────────────
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        tab1 = PestañaScraping(nb)
        tab2 = PestañaTraduccion(nb)

        nb.add(tab1, text="  📥  Descargar  ")
        nb.add(tab2, text="  🌐  Traducir  ")

        # Hacer que las pestañas llenen el espacio
        tab1.pack_propagate(False)
        tab2.pack_propagate(False)

        # ── Verificar scripts ──────────────────────────────────────────────────
        self.after(200, self._verificar_scripts)

    def _verificar_scripts(self):
        faltantes = [s.name for s in [SCRAPER, TRADUCTOR] if not s.exists()]
        if faltantes:
            messagebox.showwarning(
                "Archivos no encontrados",
                f"No se encontraron estos scripts en la carpeta:\n\n"
                + "\n".join(f"  • {f}" for f in faltantes)
                + "\n\nAsegúrate de que todos los archivos estén en la misma carpeta."
            )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()