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
from ui.admin_app import PALETTE, get_icon
from auth.session import can_create_users, get_current_full_name, get_current_role_label


# Catálogos con ícono, nombre, consulta SQL de conteo y pantalla destino
_CATALOGS = [
    {
        "icon":   "USR",
        "label":  "Usuarios",
        "sql":    "SELECT COUNT(*) AS n FROM usuarios WHERE estado='activo'",
        "target": "UsersCatalogScreen",
    },
    {
        "icon":   "LCK",
        "label":  "Lockers",
        "sql":    "SELECT COUNT(*) AS n FROM lockers",
        "target": "LockersCatalogScreen",
    },
    {
        "icon":   "ZNA",
        "label":  "Áreas / Zonas",
        "sql":    "SELECT COUNT(*) AS n FROM area_lockers",
        "target": "AreasCatalogScreen",
    },
    {
        "icon":   "UND",
        "label":  "Unidades Acad.",
        "sql":    "SELECT COUNT(*) AS n FROM unidad_academica WHERE estado='activo'",
        "target": "AreasCatalogScreen",   # misma pantalla, tab diferente
    },
    {
        "icon":   "TIP",
        "label":  "Tipos Usuario",
        "sql":    "SELECT COUNT(*) AS n FROM tipo_usuarios WHERE estado='activo'",
        "target": "AreasCatalogScreen",
    },
    {
        "icon":   "HST",
        "label":  "Historial",
        "sql":    "SELECT COUNT(*) AS n FROM historial_accesos",
        "target": None,   # pendiente
    },
]


class _CatalogCard(ctk.CTkFrame):
    """Tarjeta táctil individual del dashboard."""

    def __init__(self, parent, icon: str, label: str, count: int,
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

        # ── contenido ─────────────────────────────────────────────────────────
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            self, text=icon,
            font=ctk.CTkFont(size=34),
            fg_color="transparent",
            text_color=PALETTE["ACCENT"],
        ).grid(row=0, column=0, pady=(14, 0))

        self.lbl_count = ctk.CTkLabel(
            self, text=str(count),
            font=ctk.CTkFont(size=28, weight="bold"),
            fg_color="transparent",
            text_color=PALETTE["TEXT"],
        )
        self.lbl_count.grid(row=1, column=0)

        ctk.CTkLabel(
            self, text=label,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            text_color=PALETTE["MUTED"],
            wraplength=100,
        ).grid(row=2, column=0, pady=(0, 12))

        # Binding táctil en todos los widgets hijo
        self.bind("<Button-1>", self._clicked)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._clicked)

    def _clicked(self, _event=None):
        if self._on_click:
            self._on_click()

    def set_count(self, n: int):
        self.lbl_count.configure(text=str(n))


class DashboardScreen(ctk.CTkFrame):
    """Pantalla principal del panel de administración."""

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._cards: list[_CatalogCard] = []
        self._build_ui()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Header ────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=0,
                              height=84)
        header.pack(fill="x")
        header.pack_propagate(False)

        identity = ctk.CTkFrame(
            header,
            fg_color="transparent",
            border_width=0,
            corner_radius=0,
        )
        identity.pack(side="left", padx=20, pady=(9, 8))

        ctk.CTkLabel(
            identity,
            text=get_current_role_label(),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
            height=24,
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

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

        # ── Botón alternar tema (iconos vectoriales) ─────────────────────────
        _mode = getattr(self.controller, "_mode", "light")
        icon_name = "moon" if _mode == "light" else "sun"
        self._theme_icon = get_icon(icon_name, size=22, color=PALETTE["TEXT"])
        ctk.CTkButton(
            header,
            text="",
            image=self._theme_icon,
            width=48, height=48,
            fg_color="transparent",
            hover_color=PALETTE["BORDER"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            command=self.controller.toggle_theme,
        ).pack(side="right", padx=(6, 12), pady=12)

        self._logout_icon = get_icon("logout", size=20, color=PALETTE["TEXT"])
        ctk.CTkButton(
            header,
            text="",
            image=self._logout_icon,
            width=48,
            height=48,
            fg_color="transparent",
            hover_color=PALETTE["BORDER"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            command=self._confirm_logout,
        ).pack(side="right", padx=(0, 6), pady=12)

        # ── Botón destacado: Registrar Usuario ────────────────────────────────
        can_register = can_create_users()
        reg_btn = ctk.CTkButton(
            self,
            text="+  Registrar Usuario",
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color=PALETTE["ACCENT"] if can_register else PALETTE["BORDER"],
            hover_color=PALETTE.get("ACCENT_HOVER", PALETTE["ACCENT"]) if can_register else PALETTE["BORDER"],
            text_color=PALETTE["WHITE"],
            height=58,
            corner_radius=14,
            command=self._go_register if can_register else None,
        )
        reg_btn.pack(fill="x", padx=18, pady=(18, 10))

        # ── Sección catálogos ─────────────────────────────────────────────────
        ctk.CTkLabel(
            self, text="Catálogos",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(anchor="w", padx=22, pady=(4, 6))

        # Grid 2×3 de tarjetas
        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=14)

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
                icon=cat["icon"],
                label=cat["label"],
                count=count,
                on_click=make_callback(),
            )
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self._cards.append(card)

        # ── Footer / versión ──────────────────────────────────────────────────
        ctk.CTkLabel(
            self, text=f"Smart Locker v1.0  ·  {get_current_role_label()}",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(pady=(6, 12))

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
        from ui.admin import users_catalog, lockers_catalog, areas_catalog
        mapping = {
            "UsersCatalogScreen":   users_catalog.UsersCatalogScreen,
            "LockersCatalogScreen": lockers_catalog.LockersCatalogScreen,
            "AreasCatalogScreen":   areas_catalog.AreasCatalogScreen,
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
            message="Estás a punto de cerrar sesión. ¿Deseas continuar?",
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

    def __init__(self, parent, message: str, on_confirm):
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
            text="Cerrar sesión",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
        ).pack(pady=(8, 8))

        ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
            wraplength=360,
            justify="center",
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            self,
            text="Si eliges No, continuarás con la sesión activa.",
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
            text="No",
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
            text="Sí",
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
