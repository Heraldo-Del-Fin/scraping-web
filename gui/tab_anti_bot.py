"""
gui/tab_anti_bot.py
-------------------
Pestaña "Anti-Bot" — visualización y control del sistema de evasión por capas.
Muestra los 6 niveles, permite elegir entre modo automático o manual,
configurar nivel máximo, cookies, y puerto Chrome CDP.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.anti_bot import AntiBotManager, DESCRIPCIONES, NOMBRES_CORTOS
from gui.widgets import (
    ACCENT, BG2, BG3, ENTRY_BG, FG, FG2, GREEN, YELLOW,
    FONT_MAIN, FONT_HEAD, FONT_TITLE, action_button,
)


class TabAntiBot(tk.Frame):
    """
    Pestaña que muestra y controla la configuración anti-bot.
    No ejecuta scraping directamente; configura el AntiBotManager
    que luego usarán las otras pestañas.
    """

    def __init__(self, parent):
        super().__init__(parent, bg=BG2)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Estado actual
        self._modo      = tk.StringVar(value="auto")
        self._nivel_fijo = tk.IntVar(value=0)
        self._nivel_max  = tk.IntVar(value=5)
        self._cookies_path = tk.StringVar()
        self._chrome_port  = tk.StringVar(value="")
        self._nivel_activo = tk.IntVar(value=0)

        self._build()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build(self):
        # ── Header ───────────────────────────────────────────────────────────
        tk.Label(self, text="🛡  Sistema Anti-Bot", bg=BG2, fg=FG,
                 font=FONT_TITLE).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 4))

        tk.Label(self,
                 text="Evasión progresiva de detección de bots: medidas básicas "
                      "→ stealth JS → comportamiento humano → cookies → "
                      "resolución manual → Chrome real (CDP).",
                 bg=BG2, fg=FG2, font=("Segoe UI", 9, "italic"),
                 wraplength=700, justify="left").grid(
            row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        # ── Marco principal con scroll ───────────────────────────────────────
        canvas = tk.Canvas(self, bg=BG2, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._scroll_frame = tk.Frame(canvas, bg=BG2)

        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=2, column=0, sticky="nsew", padx=(16, 0), pady=(0, 8))
        scrollbar.grid(row=2, column=1, sticky="ns", pady=(0, 8))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Sección 1: Estrategia ────────────────────────────────────────────
        self._build_estrategia()
        ttk.Separator(self._scroll_frame, orient="horizontal").pack(
            fill="x", pady=(8, 4))

        # ── Sección 2: Tabla de niveles ──────────────────────────────────────
        self._build_tabla_niveles()
        ttk.Separator(self._scroll_frame, orient="horizontal").pack(
            fill="x", pady=(4, 8))

        # ── Sección 3: Configuración manual ──────────────────────────────────
        self._build_config_manual()
        ttk.Separator(self._scroll_frame, orient="horizontal").pack(
            fill="x", pady=(8, 4))

        # ── Sección 4: Instrucciones CDP ─────────────────────────────────────
        self._build_instrucciones_cdp()

        # ── Footer ───────────────────────────────────────────────────────────
        footer = tk.Frame(self, bg=BG2)
        footer.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=8)

        self._lbl_estado = tk.Label(
            footer, text=self._texto_estado(), bg=BG2, fg=GREEN,
            font=("Segoe UI", 10, "bold"), anchor="w")
        self._lbl_estado.pack(side="left", fill="x", expand=True)

        action_button(footer, "🔄 Restablecer niveles",
                      self._reset, width=20, color=BG3).pack(side="right",
                                                              padx=(8, 0))

    def _build_estrategia(self):
        frame = tk.LabelFrame(
            self._scroll_frame, text="  🎯  Estrategia  ",
            bg=BG2, fg=FG2, font=FONT_HEAD, relief="flat", bd=1)
        frame.pack(fill="x", padx=0, pady=(0, 4))

        inner = tk.Frame(frame, bg=BG2)
        inner.pack(fill="x", padx=12, pady=8)

        # Modo automático
        tk.Radiobutton(
            inner, text="Automática (escalación progresiva 0→1→2)",
            variable=self._modo, value="auto",
            command=self._on_modo_change,
            bg=BG2, fg=FG, selectcolor=BG3, activebackground=BG2,
            font=FONT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=2)

        # Nivel máximo para auto
        tk.Label(inner, text="Nivel máximo:", bg=BG2, fg=FG2,
                 font=FONT_MAIN).grid(row=0, column=1, padx=(24, 4), sticky="e")
        self._spin_max = tk.Spinbox(
            inner, from_=0, to=5, textvariable=self._nivel_max,
            width=3, font=FONT_MAIN, bg=ENTRY_BG, fg=FG,
            buttonbackground=BG3, relief="flat", bd=3,
            command=self._on_modo_change,
        )
        self._spin_max.grid(row=0, column=2, sticky="w")

        tk.Label(inner,
                 text="(0 = básico, 2 = máx. automático, 5 = Chrome real)",
                 bg=BG2, fg=FG2, font=("Segoe UI", 8, "italic")).grid(
            row=0, column=3, padx=8, sticky="w")

        # Modo manual (nivel fijo)
        tk.Radiobutton(
            inner, text="Manual (nivel fijo):",
            variable=self._modo, value="manual",
            command=self._on_modo_change,
            bg=BG2, fg=FG, selectcolor=BG3, activebackground=BG2,
            font=FONT_MAIN,
        ).grid(row=1, column=0, sticky="w", pady=2)

        self._spin_fijo = tk.Spinbox(
            inner, from_=0, to=5, textvariable=self._nivel_fijo,
            width=3, font=FONT_MAIN, bg=ENTRY_BG, fg=FG,
            buttonbackground=BG3, relief="flat", bd=3,
            command=self._on_modo_change,
        )
        self._spin_fijo.grid(row=1, column=1, columnspan=2, sticky="w", padx=(24, 0))

    def _build_tabla_niveles(self):
        frame = tk.LabelFrame(
            self._scroll_frame, text="  📊  Niveles de evasión  ",
            bg=BG2, fg=FG2, font=FONT_HEAD, relief="flat", bd=1)
        frame.pack(fill="x", padx=0, pady=(0, 4))

        # Cabecera
        hdr = tk.Frame(frame, bg=BG3)
        hdr.pack(fill="x", padx=6, pady=(6, 0))
        for txt, w in [("Nivel", 5), ("Nombre", 14), ("Tipo", 10),
                        ("Descripción", 60)]:
            tk.Label(hdr, text=txt, bg=BG3, fg=FG,
                     font=("Segoe UI", 9, "bold"), width=w, anchor="w").pack(
                side="left", padx=2)

        # Filas de niveles
        self._nivel_widgets = []
        for n in range(6):
            es_auto = "Auto" if n <= 2 else "Manual"
            color_tipo = GREEN if n <= 2 else YELLOW
            desc = DESCRIPCIONES[n]

            row = tk.Frame(frame, bg=BG2)
            row.pack(fill="x", padx=6, pady=1)

            tk.Label(row, text=str(n), bg=BG2, fg=ACCENT,
                     font=("Segoe UI", 11, "bold"), width=5, anchor="center").pack(
                side="left", padx=2)

            tk.Label(row, text=NOMBRES_CORTOS[n], bg=BG2, fg=FG,
                     font=FONT_MAIN, width=14, anchor="w").pack(
                side="left", padx=2)

            tk.Label(row, text=es_auto, bg=BG2, fg=color_tipo,
                     font=("Segoe UI", 9, "bold"), width=10, anchor="w").pack(
                side="left", padx=2)

            tk.Label(row, text=desc, bg=BG2, fg=FG2,
                     font=("Segoe UI", 9), wraplength=520,
                     justify="left", anchor="w").pack(
                side="left", padx=2, fill="x", expand=True)

            self._nivel_widgets.append(row)

    def _build_config_manual(self):
        frame = tk.LabelFrame(
            self._scroll_frame, text="  🔧  Configuración para niveles manuales  ",
            bg=BG2, fg=FG2, font=FONT_HEAD, relief="flat", bd=1)
        frame.pack(fill="x", padx=0, pady=(0, 4))

        inner = tk.Frame(frame, bg=BG2)
        inner.pack(fill="x", padx=12, pady=8)

        # Cookies (nivel 3)
        tk.Label(inner, text="🍪  Cookies (nivel 3):", bg=BG2, fg=FG,
                 font=FONT_MAIN, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        tk.Entry(inner, textvariable=self._cookies_path,
                 bg=ENTRY_BG, fg=FG, insertbackground=FG,
                 font=FONT_MAIN, width=38, relief="flat", bd=3).grid(
            row=0, column=1, sticky="ew", pady=4)
        btn_cf = tk.Frame(inner, bg=BG2)
        btn_cf.grid(row=0, column=2, padx=(6, 0))
        tk.Button(btn_cf, text="📂", bg=BG3, fg=FG, activebackground=ACCENT,
                  relief="flat", bd=0, cursor="hand2",
                  command=self._elegir_cookies).pack(side="left", padx=(0, 2))
        tk.Button(btn_cf, text="✖", bg=BG3, fg=FG2, activebackground=ACCENT,
                  relief="flat", bd=0, cursor="hand2", width=2,
                  command=lambda: self._cookies_path.set("")).pack(side="left")

        tk.Label(inner,
                 text="Exporta cookies de tu navegador con 'Cookie-Editor' "
                      "(extensión Chrome/Firefox) y guarda como JSON.",
                 bg=BG2, fg=FG2, font=("Segoe UI", 8, "italic"),
                 wraplength=560, justify="left").grid(
            row=1, column=1, sticky="w", pady=(0, 6))

        inner.grid_columnconfigure(1, weight=1)

        # Chrome CDP (nivel 5)
        tk.Label(inner, text="🔗  Chrome CDP (nivel 5):", bg=BG2, fg=FG,
                 font=FONT_MAIN, anchor="w").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        tk.Label(inner, text="Puerto:", bg=BG2, fg=FG2,
                 font=FONT_MAIN).grid(row=2, column=1, sticky="w", pady=4)
        tk.Entry(inner, textvariable=self._chrome_port,
                 bg=ENTRY_BG, fg=FG, insertbackground=FG,
                 font=FONT_MAIN, width=8, relief="flat", bd=3).grid(
            row=2, column=1, sticky="w", padx=(50, 0), pady=4)

    def _build_instrucciones_cdp(self):
        frame = tk.LabelFrame(
            self._scroll_frame, text="  📖  Cómo usar Chrome real (nivel 5)  ",
            bg=BG2, fg=FG2, font=FONT_HEAD, relief="flat", bd=1)
        frame.pack(fill="x", padx=0, pady=(0, 4))

        inner = tk.Frame(frame, bg=BG2)
        inner.pack(fill="x", padx=12, pady=8)

        pasos = [
            "1. Cierra TODAS las ventanas de Chrome.",
            "2. Abre Chrome desde terminal con:",
            '   chrome.exe --remote-debugging-port=9222',
            "3. Navega al sitio de novelas e inicia sesión normalmente.",
            "4. Resuelve cualquier challenge de Cloudflare manualmente.",
            "5. Configura puerto '9222' en el campo de arriba.",
            "6. Selecciona nivel 5 manual o deja el máximo en auto en 5.",
            "7. El scraper usará tu sesión real de Chrome — indetectable.",
        ]
        for paso in pasos:
            color = FG if paso.startswith("   ") else FG2
            font = ("Consolas", 9) if paso.startswith("   ") else FONT_MAIN
            tk.Label(inner, text=paso, bg=BG2, fg=color, font=font,
                     anchor="w", justify="left").pack(fill="x")

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _on_modo_change(self, *_):
        modo = self._modo.get()
        if modo == "manual":
            self._spin_max.configure(state="disabled")
            self._spin_fijo.configure(state="normal")
        else:
            self._spin_max.configure(state="normal")
            self._spin_fijo.configure(state="disabled")

        self._lbl_estado.configure(text=self._texto_estado())
        self._resaltar_nivel_activo()

    def _elegir_cookies(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo de cookies",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if ruta:
            self._cookies_path.set(ruta)

    def _reset(self):
        self._modo.set("auto")
        self._nivel_max.set(5)
        self._nivel_fijo.set(0)
        self._on_modo_change()
        messagebox.showinfo("Restablecido",
                            "Configuración anti-bot restablecida a valores por defecto.")

    def _texto_estado(self) -> str:
        if self._modo.get() == "auto":
            return (f"⚡ Modo: Automático | "
                    f"Nivel actual: 0 (Básico) | "
                    f"Máximo: {self._nivel_max.get()} | "
                    f"Listo para escalar si hay bloqueos")
        else:
            n = self._nivel_fijo.get()
            return (f"🔒 Modo: Manual | "
                    f"Nivel fijo: {n} ({NOMBRES_CORTOS[n]})")

    def _resaltar_nivel_activo(self):
        """Resalta visualmente el nivel que estaría activo."""
        for i, row in enumerate(self._nivel_widgets):
            if self._modo.get() == "auto":
                activo = i == 0  # empieza en 0
            else:
                activo = i == self._nivel_fijo.get()

            color = ACCENT if activo else BG2
            for widget in row.winfo_children():
                try:
                    widget.configure(bg=color)
                except Exception:
                    pass

    # ── API pública para otras pestañas ───────────────────────────────────────

    def construir_manager(self) -> AntiBotManager:
        """
        Construye y devuelve un AntiBotManager con la configuración actual.
        Lo usan tab_scraping y scraper_cli al iniciar scraping.
        """
        import json
        from pathlib import Path

        modo = self._modo.get()
        if modo == "manual":
            modo = self._nivel_fijo.get()

        cookies = []
        ruta = self._cookies_path.get().strip()
        if ruta and Path(ruta).exists():
            try:
                datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
                if isinstance(datos, list):
                    cookies = datos
                elif isinstance(datos, dict) and "cookies" in datos:
                    cookies = datos["cookies"]
            except Exception:
                pass

        chrome_port = 0
        try:
            chrome_port = int(self._chrome_port.get().strip() or "0")
        except ValueError:
            pass

        return AntiBotManager(
            modo=modo,
            nivel_max=self._nivel_max.get(),
            cookies=cookies,
            chrome_port=chrome_port,
        )

    def config_cmd_args(self, cmd: list[str]):
        """
        Añade argumentos anti-bot a un comando CLI existente.
        Modifica el comando in-place.
        """
        modo = self._modo.get()
        if modo == "manual":
            cmd += ["--anti-bot", str(self._nivel_fijo.get())]
        elif self._nivel_max.get() != 5:
            cmd += ["--nivel-max", str(self._nivel_max.get())]

        ruta = self._cookies_path.get().strip()
        if ruta:
            cmd += ["--cookies", ruta]

        port = self._chrome_port.get().strip()
        if port:
            cmd += ["--chrome-port", port]
