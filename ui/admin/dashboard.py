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
from ui.admin_app import PALETTE
from auth.session import can_create_users, get_current_role_label


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
        "icon":   "ASG",
        "label":  "Asignaciones",
        "sql":    "SELECT COUNT(*) AS n FROM asignacion_locker WHERE estado='activo'",
        "target": "LockerAssignmentScreen",
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
                              height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text=get_current_role_label(),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
        ).pack(side="left", padx=20, pady=16)

        # ── Botón alternar tema (🌙 / ☀️) ─────────────────────────────────────
        _mode = getattr(self.controller, "_mode", "light")
        theme_icon = "Noche" if _mode == "light" else "Dia"
        ctk.CTkButton(
            header,
            text=theme_icon,
            width=48, height=48,
            font=ctk.CTkFont(size=24),
            fg_color="transparent",
            hover_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            command=self.controller.toggle_theme,
        ).pack(side="right", padx=12, pady=12)

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
        from ui.admin import locker_assignment
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

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def on_show(self, **_kwargs) -> None:
        """Recarga los contadores cada vez que se vuelve al dashboard."""
        for idx, cat in enumerate(_CATALOGS):
            count = self._get_count(cat["sql"])
            self._cards[idx].set_count(count)
