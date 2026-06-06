"""
gui/widgets.py
--------------
Constantes de tema y widgets reutilizables para todas las pestañas.
"""

import json
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

# ── Paleta de colores ─────────────────────────────────────────────────────────

BG       = "#1a1a2e"
BG2      = "#16213e"
BG3      = "#0f3460"
ACCENT   = "#e94560"
FG       = "#eaeaea"
FG2      = "#a0a0b0"
ENTRY_BG = "#0d1b2a"
BTN_FG   = "#ffffff"
BTN_ACT  = "#c73652"
GREEN    = "#4ecca3"
YELLOW   = "#f5a623"

# ── Fuentes ───────────────────────────────────────────────────────────────────

FONT_MAIN  = ("Segoe UI", 10)
FONT_HEAD  = ("Segoe UI", 12, "bold")
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_MONO  = ("Consolas", 9)


# ── Tema ttk ──────────────────────────────────────────────────────────────────

def aplicar_tema(root: tk.Tk):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure("Accent.Horizontal.TProgressbar",
                 troughcolor=BG3, background=ACCENT,
                 bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)
    s.configure("TNotebook", background=BG, borderwidth=0)
    s.configure("TNotebook.Tab", background=BG3, foreground=FG2,
                 padding=[16, 6], font=("Segoe UI", 10, "bold"))
    s.map("TNotebook.Tab",
          background=[("selected", BG2)], foreground=[("selected", FG)])
    s.configure("TCombobox", fieldbackground=ENTRY_BG,
                 background=BG3, foreground=FG, arrowcolor=FG, selectbackground=BG3)
    s.configure("Treeview", background=ENTRY_BG, foreground=FG,
                 fieldbackground=ENTRY_BG, rowheight=22)
    s.configure("Treeview.Heading", background=BG3, foreground=FG2,
                 font=("Segoe UI", 9, "bold"))
    s.map("Treeview",
          background=[("selected", BG3)], foreground=[("selected", FG)])


# ── Widgets de formulario ─────────────────────────────────────────────────────

def labeled_entry(parent, label: str, row: int,
                  default: str = "", width: int = 46, colspan: int = 2) -> tk.StringVar:
    """Label + Entry en una fila de grid. Devuelve el StringVar."""
    tk.Label(parent, text=label, bg=BG2, fg=FG2, font=FONT_MAIN, anchor="w") \
        .grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
    var = tk.StringVar(value=default)
    tk.Entry(parent, textvariable=var, bg=ENTRY_BG, fg=FG,
             insertbackground=FG, font=FONT_MAIN, width=width,
             relief="flat", bd=4) \
        .grid(row=row, column=1, columnspan=colspan, sticky="ew", pady=4)
    return var


def folder_row(parent, label: str, row: int, default: str = "") -> tk.StringVar:
    """Label + Entry + botón de carpeta en una fila de grid."""
    tk.Label(parent, text=label, bg=BG2, fg=FG2, font=FONT_MAIN, anchor="w") \
        .grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
    var = tk.StringVar(value=default)
    tk.Entry(parent, textvariable=var, bg=ENTRY_BG, fg=FG,
             insertbackground=FG, font=FONT_MAIN, width=36,
             relief="flat", bd=4) \
        .grid(row=row, column=1, sticky="ew", pady=4)
    tk.Button(parent, text="📂", bg=BG3, fg=FG, activebackground=ACCENT,
              relief="flat", bd=0, cursor="hand2",
              command=lambda: var.set(filedialog.askdirectory() or var.get())) \
        .grid(row=row, column=2, padx=(6, 0), pady=4)
    return var


def action_button(parent, text: str, command,
                  width: int = 18, color: str = ACCENT) -> tk.Button:
    """Botón estilizado con el tema de la app."""
    return tk.Button(
        parent, text=text, command=command,
        bg=color, fg=BTN_FG, activebackground=BTN_ACT,
        font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
        cursor="hand2", width=width, pady=6,
    )


def radio_group(parent, variable: tk.StringVar,
                opciones: list[tuple[str, str]], row: int, col: int = 1):
    """Grupo de radiobuttons en una fila."""
    frame = tk.Frame(parent, bg=BG2)
    frame.grid(row=row, column=col, sticky="w")
    for texto, valor in opciones:
        tk.Radiobutton(
            frame, text=texto, variable=variable, value=valor,
            bg=BG2, fg=FG, selectcolor=BG3, activebackground=BG2,
            font=FONT_MAIN,
        ).pack(side="left", padx=6)
    return frame


# ── Log box ───────────────────────────────────────────────────────────────────

def log_box(parent, row: int, colspan: int = 3, height: int = 10) -> tk.Text:
    """Área de log con scrollbar y colores por nivel."""
    frame = tk.Frame(parent, bg=BG)
    frame.grid(row=row, column=0, columnspan=colspan, sticky="nsew", pady=(10, 0))
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    txt = tk.Text(frame, bg="#0a0e1a", fg=GREEN, font=FONT_MONO,
                  relief="flat", bd=6, height=height,
                  wrap="word", state="disabled")
    txt.grid(row=0, column=0, sticky="nsew")

    sb = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
    sb.grid(row=0, column=1, sticky="ns")
    txt.configure(yscrollcommand=sb.set)

    txt.tag_configure("ok",    foreground=GREEN)
    txt.tag_configure("warn",  foreground=YELLOW)
    txt.tag_configure("error", foreground=ACCENT)
    txt.tag_configure("info",  foreground=FG2)
    return txt


def append_log(widget: tk.Text, line: str):
    """Añade una línea al log con color según el contenido."""
    tag = (
        "ok"    if any(x in line for x in ["[OK]", "✅"]) else
        "warn"  if any(x in line for x in ["[!]",  "⚠️"]) else
        "error" if any(x in line for x in ["[X]",  "❌"]) else
        "info"
    )
    widget.configure(state="normal")
    widget.insert("end", line + "\n", tag)
    widget.see("end")
    widget.configure(state="disabled")


def progress_section(parent, row: int) -> tuple[tk.DoubleVar, tk.Label]:
    """Barra de progreso + label de estado. Devuelve (DoubleVar, Label)."""
    tk.Label(parent, text="Progreso:", bg=BG2, fg=FG2, font=FONT_MAIN) \
        .grid(row=row, column=0, sticky="w", padx=16, pady=(8, 0))
    pvar = tk.DoubleVar(value=0)
    ttk.Progressbar(parent, variable=pvar, maximum=100, mode="determinate",
                    style="Accent.Horizontal.TProgressbar") \
        .grid(row=row, column=1, columnspan=2, sticky="ew", padx=(8, 16), pady=(8, 0))
    lbl = tk.Label(parent, text="", bg=BG2, fg=FG2, font=FONT_MAIN)
    lbl.grid(row=row + 1, column=0, columnspan=3, sticky="w", padx=16, pady=(2, 0))
    return pvar, lbl


# ── Runner de subprocesos ─────────────────────────────────────────────────────

class ProcessRunner:
    """
    Ejecuta un subproceso en un hilo secundario.
    Lee líneas PROGRESO:{json} y las traduce a actualizaciones de barra.
    """

    def __init__(self):
        self._proc = None

    def run(self, cmd: list[str], log_widget: tk.Text,
            pvar: tk.DoubleVar, lbl: tk.Label,
            on_done, window: tk.Widget):

        def _worker():
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=flags,
                )
                for line in self._proc.stdout:
                    line = line.rstrip()
                    if line.startswith("PROGRESO:"):
                        try:
                            d   = json.loads(line[9:])
                            pct = d["actual"] / max(d["total"], 1) * 100
                            txt = (f"Capítulo {d['actual']}/{d['total']}  "
                                   f"{d.get('titulo','')[:50]}")
                            window.after(0, lambda p=pct, t=txt: (
                                pvar.set(p), lbl.configure(text=t)
                            ))
                        except Exception:
                            pass
                    else:
                        window.after(0, append_log, log_widget, line)
                self._proc.wait()
            except Exception as e:
                window.after(0, append_log, log_widget, f"[X] Error: {e}")
            finally:
                window.after(0, on_done)

        threading.Thread(target=_worker, daemon=True).start()

    def stop(self):
        if self._proc:
            self._proc.terminate()
            self._proc = None