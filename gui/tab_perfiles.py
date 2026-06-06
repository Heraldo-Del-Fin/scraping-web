"""
gui/tab_perfiles.py
-------------------
Pestaña "Perfiles" — tabla + formulario para gestionar perfiles de sitios.
Llama directamente a core/perfiles.py (sin subproceso, es instantáneo).
"""

import tkinter as tk
from tkinter import messagebox, ttk

from core import perfiles as pm
from gui.widgets import (
    ACCENT, BG2, BG3, ENTRY_BG, FG, FG2,
    FONT_HEAD, FONT_MAIN, FONT_TITLE,
    action_button,
)


class TabPerfiles(tk.Frame):

    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build()
        self._cargar_tabla()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build(self):
        tk.Label(self, text="⚙  Gestión de Perfiles", bg=BG2, fg=FG,
                 font=FONT_TITLE).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))

        self._build_tabla()
        self._build_botones_tabla()
        ttk.Separator(self, orient="horizontal").grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=6)
        self._build_formulario()
        self._build_botones_form()

    def _build_tabla(self):
        frame = tk.Frame(self, bg=BG2)
        frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 4))
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        cols = ("id", "nombre", "dominios", "activo", "descripcion")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                   height=10, selectmode="browse")
        for col, ancho, titulo in [
            ("id", 120, "ID"), ("nombre", 150, "Nombre"),
            ("dominios", 190, "Dominios"), ("activo", 60, "Activo"),
            ("descripcion", 300, "Descripción"),
        ]:
            self.tree.heading(col, text=titulo)
            self.tree.column(col, width=ancho, minwidth=50)

        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_botones_tabla(self):
        bf = tk.Frame(self, bg=BG2)
        bf.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 4))
        for texto, cmd, color, w in [
            ("➕ Nuevo",         self._nuevo,          ACCENT, 12),
            ("✏️  Editar",        self._editar,         BG3,   10),
            ("🗑  Eliminar",     self._eliminar,        BG3,   10),
            ("↕  Act/Des",      self._toggle,          BG3,   10),
            ("🔄 Recargar",     self._cargar_tabla,    BG3,   10),
        ]:
            action_button(bf, texto, cmd, width=w, color=color).pack(
                side="left", padx=(0, 6))

    def _build_formulario(self):
        tk.Label(self, text="Editar / Nuevo perfil:", bg=BG2, fg=FG2,
                 font=FONT_HEAD).grid(row=4, column=0, sticky="w", padx=16, pady=(4, 2))

        form = tk.Frame(self, bg=BG2)
        form.grid(row=5, column=0, sticky="ew", padx=16)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)

        # Columna izquierda / derecha
        self.f = {}
        campos_dobles = [
            (0, "ID (único):",        "id",        0, 0),
            (0, "Nombre:",            "nombre",    0, 2),
        ]
        campos_simples = [
            (1, "Dominios (coma):",             "dominios"),
            (2, "Descripción:",                  "desc"),
            (3, "Base URL:",                     "base_url"),
            (4, "Selectores título (coma):",     "titulo"),
            (5, "Selectores contenido (coma):",  "contenido"),
            (6, "Selectores siguiente (coma):",  "siguiente"),
            (7, "Selectores índice (coma):",     "indice"),
        ]
        campos_dobles2 = [
            (8, "Delay entre páginas (seg):", "delay", 0, 0),
            (8, "Espera carga (seg):",        "espera", 0, 2),
        ]

        for row, label, key, _, col in campos_dobles:
            self._campo_form(form, label, key, row, col)

        for row, label, key in campos_simples:
            self._campo_form(form, label, key, row, 0, colspan=3)

        for row, label, key, _, col in campos_dobles2:
            self._campo_form(form, label, key, row, col)

    def _campo_form(self, parent, label: str, key: str,
                    row: int, col: int, colspan: int = 1, width: int = 26):
        pad_left = 0 if col == 0 else 12
        tk.Label(parent, text=label, bg=BG2, fg=FG2, font=FONT_MAIN, anchor="w") \
            .grid(row=row, column=col, sticky="w", padx=(pad_left, 6), pady=3)
        var = tk.StringVar()
        tk.Entry(parent, textvariable=var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, font=FONT_MAIN, width=width,
                 relief="flat", bd=3) \
            .grid(row=row, column=col + 1, columnspan=colspan, sticky="ew", pady=3)
        self.f[key] = var

    def _build_botones_form(self):
        bf = tk.Frame(self, bg=BG2)
        bf.grid(row=6, column=0, sticky="w", padx=16, pady=8)
        action_button(bf, "💾 Guardar perfil", self._guardar, width=16).pack(
            side="left", padx=(0, 8))
        action_button(bf, "✖ Limpiar", self._limpiar_form, width=10, color=BG3).pack(
            side="left")

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _cargar_tabla(self, *_):
        for item in self.tree.get_children():
            self.tree.delete(item)
        data = pm.cargar_raw()
        for p in data.get("perfiles", []):
            self.tree.insert("", "end", iid=p["id"], values=(
                p["id"],
                p.get("nombre", ""),
                ", ".join(p.get("dominios", [])),
                "Sí" if p.get("activo", True) else "No",
                p.get("descripcion", ""),
            ))

    def _on_select(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        data = pm.cargar_raw()
        p = next((x for x in data["perfiles"] if x["id"] == pid), None)
        if not p:
            return
        opts = p.get("opciones", {})
        sels = p.get("selectores", {})
        self.f["id"].set(p.get("id", ""))
        self.f["nombre"].set(p.get("nombre", ""))
        self.f["dominios"].set(", ".join(p.get("dominios", [])))
        self.f["desc"].set(p.get("descripcion", ""))
        self.f["base_url"].set(opts.get("base_url", ""))
        self.f["delay"].set(str(opts.get("delay_entre_paginas", 2.0)))
        self.f["espera"].set(str(opts.get("espera_carga", 2.0)))
        self.f["titulo"].set(", ".join(sels.get("titulo", [])))
        self.f["contenido"].set(", ".join(sels.get("contenido", [])))
        self.f["siguiente"].set(", ".join(sels.get("siguiente", [])))
        self.f["indice"].set(", ".join(sels.get("indice_primer_cap", [])))

    # ── Acciones de tabla ────────────────────────────────────────────────────

    def _nuevo(self):
        self._limpiar_form()
        self.f["delay"].set("2.0")
        self.f["espera"].set("2.0")

    def _editar(self):
        if not self.tree.selection():
            messagebox.showinfo("Info", "Selecciona un perfil de la tabla primero.")

    def _eliminar(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Selecciona un perfil.")
            return
        pid = sel[0]
        if pid == "generico":
            messagebox.showwarning("No permitido",
                                    "El perfil genérico no puede eliminarse.")
            return
        if not messagebox.askyesno("Confirmar", f"¿Eliminar el perfil '{pid}'?"):
            return
        try:
            pm.eliminar_perfil(pid)
            self._cargar_tabla()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _toggle(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Selecciona un perfil.")
            return
        pm.toggle_activo(sel[0])
        self._cargar_tabla()

    # ── Formulario ────────────────────────────────────────────────────────────

    def _guardar(self):
        pid = self.f["id"].get().strip()
        if not pid:
            messagebox.showerror("Error", "El campo ID es obligatorio.")
            return

        def parse_list(s: str) -> list[str]:
            return [x.strip() for x in s.split(",") if x.strip()]

        try:
            delay  = float(self.f["delay"].get() or 2.0)
            espera = float(self.f["espera"].get() or 2.0)
        except ValueError:
            messagebox.showerror("Error", "Delay y Espera deben ser números.")
            return

        perfil = {
            "id":              pid,
            "nombre":          self.f["nombre"].get().strip() or pid,
            "dominios":        parse_list(self.f["dominios"].get()),
            "activo":          True,
            "descripcion":     self.f["desc"].get().strip(),
            "patron_indice":   "",
            "patron_capitulo": "",
            "selectores": {
                "titulo":            parse_list(self.f["titulo"].get()),
                "contenido":         parse_list(self.f["contenido"].get()),
                "siguiente":         parse_list(self.f["siguiente"].get()),
                "indice_primer_cap": parse_list(self.f["indice"].get()),
                "eliminar_anuncios": [".ads", ".ad", ".adsbox", ".adsbygoogle"],
            },
            "opciones": {
                "delay_entre_paginas": delay,
                "espera_carga":        espera,
                "base_url":            self.f["base_url"].get().strip(),
            },
        }
        pm.guardar_perfil(perfil)
        self._cargar_tabla()
        messagebox.showinfo("Guardado", f"Perfil '{pid}' guardado correctamente.")

    def _limpiar_form(self):
        for v in self.f.values():
            v.set("")