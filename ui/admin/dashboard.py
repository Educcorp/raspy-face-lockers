"""
DashboardScreen – pantalla de inicio del super-admin (480×800 px).

Muestra tarjetas touch-friendly para cada catálogo principal.
Los contadores se actualizan en on_show() cada vez que se navega aquí.

Catálogos:
  ● Usuarios          (tabla usuarios)
  ● Lockers           (tabla lockers)
  ● Áreas / Zonas     (tabla area_lockers)
  ● Unidades Acad.    (tabla unidad_academica)
  ● Tipos de Usuario  (tabla tipo_usuarios)
  ● Historial         (tabla historial_accesos)
"""

import customtkinter as ctk
from database.connection import fetch_one
from core.i18n import t, register_observer, unregister_observer
from ui.admin_app import PALETTE, get_icon
from ui.components.language_button import LanguageToggleButton
from auth.session import can_create_users, get_current_full_name, get_current_role_label


# Catálogos con ícono, claves i18n, consulta SQL de conteo y pantalla destino
_CATALOGS = [
    {
        "icon":       "USR",
        "label_key":  "dash_users",
        "hint_key":   "dash_accounts",
        "sql":        "SELECT COUNT(*) AS n FROM usuarios WHERE estado='activo'",
        "target":     "UsersCatalogScreen",
    },
    {
        "icon":       "LCK",
        "label_key":  "dash_lockers",
        "hint_key":   "dash_inventory",
        "sql":        "SELECT COUNT(*) AS n FROM lockers",
        "target":     "LockersCatalogScreen",
    },
    {
        "icon":       "ZNA",
        "label_key":  "dash_areas",
        "hint_key":   "dash_location",
        "sql":        "SELECT COUNT(*) AS n FROM area_lockers",
        "target":     "AreasCatalogScreen",
    },
    {
        "icon":       "UND",
        "label_key":  "dash_academic",
        "hint_key":   "dash_faculties",
        "sql":        "SELECT COUNT(*) AS n FROM unidad_academica WHERE estado='activo'",
        "target":     "AreasCatalogScreen",   # misma pantalla, tab diferente
    },
    {
        "icon":       "TIP",
        "label_key":  "dash_user_types",
        "hint_key":   "dash_roles",
        "sql":        "SELECT COUNT(*) AS n FROM tipo_usuarios WHERE estado='activo'",
        "target":     "AreasCatalogScreen",
    },
    {
        "icon":       "ASG",
        "label_key":  "dash_assignments",
        "hint_key":   "dash_in_use",
        "sql":        "SELECT COUNT(*) AS n FROM asignacion_locker WHERE estado='activo'",
        "target":     "LockerAssignmentScreen",
    },
]


class _CatalogCard(ctk.CTkFrame):
    """Tarjeta táctil individual del dashboard."""

    def __init__(self, parent, label: str, hint: str, count: int,
                 on_click, **kwargs):
        super().__init__(
            parent,
            fg_color=PALETTE["CARD"],
            corner_radius=16,
            border_width=1,
            border_color=PALETTE["BORDER"],
            cursor="hand2",
            **kwargs,
        )
        self._on_click = on_click
        self._default_fg = PALETTE["CARD"]
        self._hover_fg = PALETTE["BG"]

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        body = ctk.CTkFrame(
            self,
            fg_color="transparent",
            border_width=0,
            corner_radius=0,
        )
        body.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=0)
        body.grid_rowconfigure(1, weight=1)
        body.grid_rowconfigure(2, weight=0)

        self.lbl_label = ctk.CTkLabel(
            body,
            text=label,
            font=ctk.CTkFont(size=17, weight="bold"),
            fg_color="transparent",
            text_color=PALETTE["ACCENT"],
            justify="left",
            anchor="w",
            wraplength=150,
        )
        self.lbl_label.grid(row=0, column=0, sticky="ew")

        self.lbl_hint = ctk.CTkLabel(
            body,
            text=hint,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=PALETTE["MUTED"],
            justify="left",
            anchor="w",
            wraplength=150,
        )
        self.lbl_hint.grid(row=1, column=0, sticky="nw", pady=(5, 0))

        self.lbl_count = ctk.CTkLabel(
            body, text=str(count),
            font=ctk.CTkFont(size=28, weight="bold"),
            fg_color="transparent",
            text_color=PALETTE["TEXT"],
        )
        self.lbl_count.grid(row=2, column=0, sticky="w", pady=(8, 0))

        self.lbl_active = ctk.CTkLabel(
            body,
            text=t("dash_active_records"),
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=PALETTE["MUTED"],
        )
        self.lbl_active.grid(row=3, column=0, sticky="w", pady=(1, 0))

        # Binding táctil en todos los widgets hijo
        self.bind("<Button-1>", self._clicked)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._clicked)
            child.bind("<Enter>", self._on_enter)
            child.bind("<Leave>", self._on_leave)
            for grandchild in child.winfo_children():
                grandchild.bind("<Button-1>", self._clicked)
                grandchild.bind("<Enter>", self._on_enter)
                grandchild.bind("<Leave>", self._on_leave)

    def _clicked(self, _event=None):
        if self._on_click:
            self._on_click()

    def set_count(self, n: int):
        self.lbl_count.configure(text=str(n))

    def update_labels(self, label: str, hint: str) -> None:
        self.lbl_label.configure(text=label)
        self.lbl_hint.configure(text=hint)

    def _on_enter(self, _event=None):
        self.configure(fg_color=self._hover_fg)

    def _on_leave(self, _event=None):
        self.configure(fg_color=self._default_fg)


class DashboardScreen(ctk.CTkFrame):
    """Pantalla principal del panel de administración."""

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._cards: list[_CatalogCard] = []
        self._lang_reg: list = []
        register_observer(self._on_lang_change)
        self._build_ui()

    def _reg(self, widget, key: str, **kwargs) -> None:
        self._lang_reg.append((widget, key, kwargs))
        widget.configure(text=t(key, **kwargs))

    def _on_lang_change(self) -> None:
        for widget, key, kwargs in self._lang_reg:
            try:
                if widget.winfo_exists():
                    widget.configure(text=t(key, **kwargs))
            except Exception:
                pass
        # Update card labels/hints
        for card, cat in zip(self._cards, _CATALOGS):
            try:
                if card.winfo_exists():
                    card.update_labels(t(cat["label_key"]), t(cat["hint_key"]))
            except Exception:
                pass

    def destroy(self) -> None:
        unregister_observer(self._on_lang_change)
        super().destroy()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            width=250,
            height=250,
            corner_radius=125,
            border_width=0,
        ).place(relx=0.98, rely=0.08, anchor="ne")

        ctk.CTkFrame(
            self,
            fg_color=PALETTE["BG"],
            width=170,
            height=170,
            corner_radius=85,
            border_width=0,
        ).place(relx=0.02, rely=0.98, anchor="sw")

        # ── Header ────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=0,
                  height=90)
        header.pack(fill="x")
        header.pack_propagate(False)

        identity = ctk.CTkFrame(
            header,
            fg_color="transparent",
            border_width=0,
            corner_radius=0,
        )
        identity.pack(side="left", padx=18, pady=(8, 6))

        ctk.CTkLabel(
            identity,
            text=get_current_role_label(),
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
            height=24,
            anchor="w",
        ).pack(anchor="w", pady=(0, 2))

        full_name = get_current_full_name()
        subtitle = f"Usuario: {full_name}" if full_name else "Usuario: Sesión activa"
        ctk.CTkLabel(
            identity,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            height=14,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkFrame(
            identity,
            fg_color=PALETTE["ACCENT"],
            corner_radius=4,
            height=4,
            width=56,
        ).pack(anchor="w", pady=(6, 0))

        # ── Botón alternar tema (iconos vectoriales) ─────────────────────────
        _mode = getattr(self.controller, "_mode", "light")
        icon_name = "moon" if _mode == "light" else "sun"
        self._theme_icon = get_icon(icon_name, size=22, color=PALETTE["TEXT"])
        ctk.CTkButton(
            header,
            text="",
            image=self._theme_icon,
            width=46, height=46,
            fg_color=PALETTE["BG"],
            hover_color=PALETTE["BORDER"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            corner_radius=12,
            command=self.controller.toggle_theme,
        ).pack(side="right", padx=(6, 12), pady=10)

        self._logout_icon = get_icon("logout", size=20, color=PALETTE["TEXT"])
        ctk.CTkButton(
            header,
            text="",
            image=self._logout_icon,
            width=46,
            height=46,
            fg_color=PALETTE["BG"],
            hover_color=PALETTE["BORDER"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            corner_radius=12,
            command=self._confirm_logout,
        ).pack(side="right", padx=(0, 6), pady=10)

        # ── Botón de idioma en el header ──────────────────────────────────────
        LanguageToggleButton(
            header,
            text_color=PALETTE["TEXT"],
            border_color=PALETTE["BORDER"],
            hover_color=PALETTE["BORDER"],
        ).pack(side="right", padx=(0, 6), pady=10)

        # ── Resumen operativo ───────────────────────────────────────────────
        summary = ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            corner_radius=16,
            border_width=1,
            border_color=PALETTE["BORDER"],
            height=86,
        )
        summary.pack(fill="x", padx=18, pady=(8, 8))
        summary.pack_propagate(False)

        summary.grid_columnconfigure(0, weight=1)
        summary.grid_columnconfigure(1, weight=1)
        summary.grid_rowconfigure(0, weight=1)

        total_catalogs = len(_CATALOGS)
        total_records = sum(self._get_count(cat["sql"]) for cat in _CATALOGS)

        left_metric = ctk.CTkFrame(
            summary,
            fg_color=PALETTE["BG"],
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["BORDER"],
            height=62,
        )
        left_metric.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left_metric.pack_propagate(False)
        ctk.CTkLabel(
            left_metric,
            text=str(total_catalogs),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=10, pady=(5, 0))
        lbl_modules = ctk.CTkLabel(
            left_metric,
            text=t("dash_modules"),
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        )
        lbl_modules.pack(anchor="w", padx=10, pady=(0, 6))
        self._lang_reg.append((lbl_modules, "dash_modules", {}))

        right_metric = ctk.CTkFrame(
            summary,
            fg_color=PALETTE["BG"],
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["BORDER"],
            height=62,
        )
        right_metric.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right_metric.pack_propagate(False)
        ctk.CTkLabel(
            right_metric,
            text=str(total_records),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=10, pady=(5, 0))
        lbl_total = ctk.CTkLabel(
            right_metric,
            text=t("dash_total_records"),
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        )
        lbl_total.pack(anchor="w", padx=10, pady=(0, 6))
        self._lang_reg.append((lbl_total, "dash_total_records", {}))

        # ── Botón destacado: Registrar Usuario ────────────────────────────────
        can_register = can_create_users()
        reg_btn = ctk.CTkButton(
            self,
            text=t("dash_register_user"),
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color=PALETTE["ACCENT"] if can_register else PALETTE["BORDER"],
            hover_color=PALETTE.get("ACCENT_HOVER", PALETTE["ACCENT"]) if can_register else PALETTE["BORDER"],
            text_color=PALETTE["WHITE"],
            height=60,
            corner_radius=18,
            command=self._go_register if can_register else None,
        )
        reg_btn.pack(fill="x", padx=18, pady=(0, 8))
        self._lang_reg.append((reg_btn, "dash_register_user", {}))

        # ── Sección catálogos ─────────────────────────────────────────────────
        lbl_catalogs = ctk.CTkLabel(
            self, text=t("dash_catalogs"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        )
        lbl_catalogs.pack(anchor="w", padx=22, pady=(0, 4))
        self._lang_reg.append((lbl_catalogs, "dash_catalogs", {}))

        # Grid 2×3 de tarjetas
        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=14, pady=(0, 2))

        for col in range(2):
            grid_frame.grid_columnconfigure(col, weight=1, uniform="col")
        for row in range(3):
            grid_frame.grid_rowconfigure(row, weight=1, uniform="row")

        for idx, cat in enumerate(_CATALOGS):
            row, col = divmod(idx, 2)
            count = self._get_count(cat["sql"])
            target_name = cat["target"]

            def make_callback(tname=target_name):
                return lambda: self._navigate(tname)

            card = _CatalogCard(
                grid_frame,
                label=t(cat["label_key"]),
                hint=t(cat["hint_key"]),
                count=count,
                on_click=make_callback(),
            )
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self._cards.append(card)

      

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_count(self, sql: str) -> int:
        try:
            row = fetch_one(sql)
            return row["n"] if row else 0
        except Exception:
            return 0

    def _navigate(self, target_name: str | None) -> None:
        if not target_name:
            return
        from ui.admin import users_catalog, lockers_catalog, areas_catalog, locker_assignment
        mapping = {
            "UsersCatalogScreen":   users_catalog.UsersCatalogScreen,
            "LockersCatalogScreen": lockers_catalog.LockersCatalogScreen,
            "AreasCatalogScreen":   areas_catalog.AreasCatalogScreen,
            "LockerAssignmentScreen": locker_assignment.LockerAssignmentScreen,
        }
        cls = mapping.get(target_name)
        if cls:
            self.controller.show_frame(cls)

    def _go_register(self) -> None:
        from ui.admin.register_user import RegisterUserScreen
        self.controller.show_frame(RegisterUserScreen)

    def _confirm_logout(self) -> None:
        _LogoutConfirmDialog(
            self,
            on_confirm=self.controller.logout,
        )

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def on_show(self, **_kwargs) -> None:
        """Recarga los contadores cada vez que se vuelve al dashboard."""
        for idx, cat in enumerate(_CATALOGS):
            count = self._get_count(cat["sql"])
            self._cards[idx].set_count(count)


class _LogoutConfirmDialog(ctk.CTkFrame):
    """Confirmación superpuesta dentro del panel (sin abrir ventana externa)."""

    def __init__(self, parent, on_confirm):
        root = parent.winfo_toplevel()
        super().__init__(
            root,
            width=404,
            height=258,
            fg_color=PALETTE["CARD"],
            corner_radius=20,
            border_width=2,
            border_color=PALETTE["ACCENT"],
        )
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.pack_propagate(False)

        # Borde interior suave para resaltar sin crear fondo cuadrado externo.
        inner = ctk.CTkFrame(
            self,
            fg_color="transparent",
            corner_radius=16,
            border_width=1,
            border_color=PALETTE["BORDER"],
            width=388,
            height=242,
        )
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkFrame(
            self,
            fg_color=PALETTE["ACCENT"],
            corner_radius=8,
            height=4,
            width=90,
        ).pack(pady=(10, 4))

        ctk.CTkLabel(
            self,
            text=t("dash_logout"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
        ).pack(pady=(8, 8))

        ctk.CTkLabel(
            self,
            text=t("dash_logout_confirm"),
            font=ctk.CTkFont(size=14),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
            wraplength=360,
            justify="center",
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            self,
            text=t("dash_logout_detail"),
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            wraplength=360,
            justify="center",
        ).pack()

        btn_row = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], border_width=0)
        btn_row.pack(fill="x", padx=18, pady=(16, 14))
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=0, minsize=14)
        btn_row.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            btn_row,
            text=t("dash_logout_no"),
            height=48,
            fg_color=PALETTE["BORDER"],
            hover_color=PALETTE["MUTED"],
            text_color=PALETTE["TEXT"],
            border_width=0,
            corner_radius=12,
            command=self._close,
        ).grid(row=0, column=0, sticky="nsew")

        ctk.CTkFrame(
            btn_row,
            fg_color=PALETTE["CARD"],
            width=14,
            height=1,
            border_width=0,
            corner_radius=0,
        ).grid(row=0, column=1)

        ctk.CTkButton(
            btn_row,
            text=t("dash_logout_yes"),
            height=48,
            fg_color=PALETTE["DANGER"],
            hover_color="#922b21",
            text_color=PALETTE["WHITE"],
            border_width=0,
            corner_radius=12,
            command=lambda: (on_confirm(), self._close()),
        ).grid(row=0, column=2, sticky="nsew")

    def _close(self) -> None:
        if self.winfo_exists():
            self.destroy()
