"""
DashboardScreen – pantalla de inicio del panel admin (480×800 px).

Réplica de webapp/templates/dashboard.html: un encabezado "Resumen" seguido
de 5 tarjetas de estadística (Usuarios activos, Pendientes de registro
facial, Lockers activos, Asignaciones activas, Accesos hoy) apiladas en una
columna (el web las muestra en grid porque tiene ancho de escritorio; aquí
se apilan por el ancho de 480px), más la tarjeta de aviso condicional cuando
hay usuarios con registro facial pendiente — mismos datos, mismo orden,
mismo mensaje que el web (ver webapp/blueprints/dashboard_bp.py).

La navegación a catálogos (antes una grid de tarjetas en esta pantalla) vive
ahora en el NavDrawer (ui/components.py), igual que en la topbar del web.
"""

import customtkinter as ctk

from database.connection import fetch_one
from ui import theme
from ui.theme import PALETTE, get_icon
from ui.components import Card, PillButton, TopHeader
from ui.i18n import t
from auth.session import get_current_full_name


def _get_stats() -> dict:
    def _count(sql: str) -> int:
        try:
            row = fetch_one(sql)
            return row["n"] if row else 0
        except Exception:
            return 0

    return {
        "usuarios": _count("SELECT COUNT(*) AS n FROM usuarios WHERE estado='activo'"),
        "pendientes": _count(
            """
            SELECT COUNT(*) AS n FROM usuarios u
            WHERE u.estado='activo' AND NOT EXISTS (
                SELECT 1 FROM encoding e WHERE e.idUsuario=u.idUsuario AND e.estado='activo'
            )
            """
        ),
        "lockers": _count("SELECT COUNT(*) AS n FROM lockers WHERE estado='activo'"),
        "asignaciones": _count("SELECT COUNT(*) AS n FROM asignacion_locker WHERE estado='activo'"),
        "accesos_hoy": _count(
            "SELECT COUNT(*) AS n FROM historial_accesos WHERE fechaHoraAcceso::date = now()::date"
        ),
    }


class _StatCard(Card):
    """Tarjeta de estadística: icono en círculo suave + número grande + etiqueta,
    equivalente a .stat-icon/.stat-value/.stat-label en style.css."""

    def __init__(self, parent, icon: str, label: str, value: int):
        super().__init__(parent)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=16)

        bubble = ctk.CTkFrame(row, fg_color=PALETTE["ACCENT_SOFT"], corner_radius=999,
                               width=48, height=48)
        bubble.pack(side="left")
        bubble.pack_propagate(False)
        ctk.CTkLabel(bubble, image=get_icon(icon, 22, PALETTE["ACCENT"]), text="",
                     fg_color="transparent").place(relx=0.5, rely=0.5, anchor="center")

        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", padx=(14, 0), fill="x", expand=True)
        self._value_lbl = ctk.CTkLabel(
            text_col, text=str(value), font=theme.font_display(26, "bold"),
            text_color=PALETTE["TEXT"], anchor="w",
        )
        self._value_lbl.pack(fill="x")
        ctk.CTkLabel(
            text_col, text=label, font=theme.font_body(12),
            text_color=PALETTE["MUTED"], anchor="w",
        ).pack(fill="x")

    def set_value(self, value: int) -> None:
        self._value_lbl.configure(text=str(value))


class DashboardScreen(ctk.CTkFrame):
    """Pantalla de inicio del panel de administración."""

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._stat_cards: dict[str, _StatCard] = {}
        self._notice_card: ctk.CTkFrame | None = None
        self._build_ui()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        TopHeader(self, self.controller, title=t("nav.inicio")).pack(fill="x")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(14, 10))

        ctk.CTkLabel(
            body, text=t("dash.summary_heading"), font=theme.font_display(20, "bold"),
            text_color=PALETTE["TEXT"], anchor="w",
        ).pack(fill="x", pady=(0, 2))
        full_name = get_current_full_name()
        if full_name:
            ctk.CTkLabel(
                body, text=f"{t('dash.user_prefix')} {full_name}", font=theme.font_body(12),
                text_color=PALETTE["MUTED"], anchor="w",
            ).pack(fill="x", pady=(0, 10))

        self._cards_container = ctk.CTkFrame(body, fg_color="transparent")
        self._cards_container.pack(fill="x")

        self._notice_container = ctk.CTkFrame(body, fg_color="transparent")
        self._notice_container.pack(fill="x", pady=(8, 0))

        self._render_stats(_get_stats())

    def _render_stats(self, stats: dict) -> None:
        for card in self._cards_container.winfo_children():
            card.destroy()
        self._stat_cards = {}

        rows = [
            ("usuarios",     "user",    t("dash.stat.usuarios")),
            ("pendientes",   "warning", t("dash.stat.pendientes")),
            ("lockers",      "box",     t("dash.stat.lockers")),
            ("asignaciones", "link",    t("dash.stat.asignaciones")),
            ("accesos_hoy",  "clock",   t("dash.stat.accesos_hoy")),
        ]
        for key, icon, label in rows:
            card = _StatCard(self._cards_container, icon, label, stats.get(key, 0))
            card.pack(fill="x", pady=(0, 10))
            self._stat_cards[key] = card

        self._render_notice(stats.get("pendientes", 0))

    def _render_notice(self, pendientes: int) -> None:
        for w in self._notice_container.winfo_children():
            w.destroy()
        if pendientes <= 0:
            return

        card = Card(self._notice_container, fg_color=PALETTE["WARN_SOFT"], border_width=0)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)

        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, image=get_icon("warning", 18, PALETTE["WARN"]), text="",
                     fg_color="transparent").pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            head, text=t("dash.notice_title", n=pendientes), font=theme.font_body(14, "bold"),
            text_color=PALETTE["WARN"], anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            inner, text=t("dash.notice_body"), font=theme.font_body(12),
            text_color=PALETTE["TEXT"], anchor="w", justify="left", wraplength=380,
        ).pack(fill="x", pady=(8, 12))

        PillButton(inner, t("dash.notice_cta"), variant="primary", small=True,
                   command=self._go_users).pack(anchor="w")

    # ── Navegación ────────────────────────────────────────────────────────────

    def _go_users(self) -> None:
        from ui.admin.users_catalog import UsersCatalogScreen
        self.controller.show_frame(UsersCatalogScreen)

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def on_show(self, **_kwargs) -> None:
        self._render_stats(_get_stats())
