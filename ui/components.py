"""
ui/components.py – Widgets reutilizables que replican los componentes CSS del
panel web (webapp/static/css/style.css) en CustomTkinter: tarjetas, badges de
estado, botones tipo "pill", filas de formulario, diálogo de confirmación
(reemplaza los `confirm()` nativos de JS del web) y el shell de navegación
(TopHeader + NavDrawer) que sustituye el header "← volver" que cada pantalla
dibujaba por su cuenta.

Todas las pantallas de ui/admin/*.py deben construirse sobre estos widgets en
vez de crear CTkFrame/CTkButton sueltos con colores propios.
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from ui import theme
from ui.theme import PALETTE, get_icon
from ui.i18n import t, lang_btn_text


# ── Card ───────────────────────────────────────────────────────────────────

class Card(ctk.CTkFrame):
    """Superficie redondeada equivalente a `.card` en el web."""

    def __init__(self, parent, large: bool = False, **kwargs):
        radius = theme.RADIUS_CARD_LG if large else theme.RADIUS_CARD
        kwargs.setdefault("fg_color", PALETTE["CARD"])
        kwargs.setdefault("corner_radius", radius)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", PALETTE["BORDER"])
        super().__init__(parent, **kwargs)


# ── StatusBadge ────────────────────────────────────────────────────────────

class StatusBadge(ctk.CTkFrame):
    """Pill coloreada por estado, equivalente a `.badge.<estado>` en el web."""

    def __init__(self, parent, text: str, status: str, **kwargs):
        fg, bg = theme.status_colors(status)
        kwargs.setdefault("fg_color", bg)
        kwargs.setdefault("corner_radius", theme.RADIUS_PILL)
        super().__init__(parent, **kwargs)
        self._label = ctk.CTkLabel(
            self, text=f"●  {text}", text_color=fg,
            font=theme.font_body(12, "bold"),
            fg_color="transparent",
        )
        self._label.pack(padx=12, pady=4)

    def set_status(self, text: str, status: str) -> None:
        fg, bg = theme.status_colors(status)
        self.configure(fg_color=bg)
        self._label.configure(text=f"●  {text}", text_color=fg)


# ── PillButton ─────────────────────────────────────────────────────────────

_VARIANT_KEYS = {
    "primary": ("ACCENT", "ACCENT_HOVER", "WHITE"),
    "danger":  ("DANGER", "DANGER", "WHITE"),
    "muted":   ("SURFACE_ALT", "BORDER", "TEXT"),
}


class PillButton(ctk.CTkButton):
    """Botón redondeado equivalente a `.btn` / `.btn-danger` / `.btn-muted`."""

    def __init__(self, parent, text: str, variant: str = "primary",
                 small: bool = False, **kwargs):
        fg_key, hover_key, text_key = _VARIANT_KEYS.get(variant, _VARIANT_KEYS["primary"])
        kwargs.setdefault("fg_color", PALETTE[fg_key])
        kwargs.setdefault("hover_color", PALETTE[hover_key])
        kwargs.setdefault("text_color", PALETTE[text_key])
        kwargs.setdefault("corner_radius", theme.RADIUS_PILL)
        kwargs.setdefault("height", 38 if small else 48)
        kwargs.setdefault("font", theme.font_body(13 if small else 15, "bold"))
        super().__init__(parent, text=text, **kwargs)
        self._variant = variant

    def set_disabled(self, disabled: bool) -> None:
        self.configure(state="disabled" if disabled else "normal")


# ── FormRow ────────────────────────────────────────────────────────────────

class FormRow(ctk.CTkFrame):
    """Label arriba + input abajo, equivalente a `.form-row` en el web."""

    def __init__(self, parent, label: str, widget_factory: Callable[[ctk.CTkFrame], ctk.CTkBaseClass],
                 required: bool = False, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)
        label_text = f"{label} *" if required else label
        ctk.CTkLabel(
            self, text=label_text, anchor="w",
            font=theme.font_body(12, "bold"),
            text_color=PALETTE["MUTED"],
        ).pack(fill="x", pady=(0, 4))
        self.input = widget_factory(self)
        self.input.pack(fill="x")


# ── ConfirmDialog ──────────────────────────────────────────────────────────

class ConfirmDialog:
    """Overlay de confirmación de pantalla completa; reemplaza los `confirm()`
    nativos que usa el panel web antes de borrar/liberar/etc."""

    @staticmethod
    def ask(host: ctk.CTk, title: str, message: str,
            on_confirm: Callable[[], None],
            confirm_text: str = "Confirmar",
            cancel_text: str = "Cancelar",
            danger: bool = True) -> None:
        overlay = ctk.CTkFrame(host, fg_color="gray20", corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()

        card = Card(overlay, large=True, width=380)
        card.place(relx=0.5, rely=0.5, anchor="center")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=26, pady=26, fill="both")

        ctk.CTkLabel(
            inner, text=title, font=theme.font_display(18, "bold"),
            text_color=PALETTE["TEXT"], wraplength=320, justify="left",
        ).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            inner, text=message, font=theme.font_body(13),
            text_color=PALETTE["MUTED"], wraplength=320, justify="left",
        ).pack(anchor="w", pady=(0, 20))

        def _close() -> None:
            overlay.destroy()

        def _confirm() -> None:
            _close()
            on_confirm()

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")
        PillButton(btn_row, cancel_text, variant="muted", small=True,
                   command=_close).pack(side="left", expand=True, fill="x", padx=(0, 6))
        PillButton(btn_row, confirm_text, variant="danger" if danger else "primary",
                   small=True, command=_confirm).pack(side="left", expand=True, fill="x", padx=(6, 0))


# ── TopHeader ──────────────────────────────────────────────────────────────

class TopHeader(ctk.CTkFrame):
    """Header compacto (marca + título + botón de menú) que reemplaza el
    patrón anterior de header-por-pantalla con botón "←". Equivalente
    funcional a la topbar del web, adaptado a una pantalla angosta: en vez
    de mostrar los 6 enlaces en línea, el botón hamburguesa abre el
    NavDrawer con el mismo listado y el mismo orden que la topbar web."""

    HEIGHT = 64

    def __init__(self, parent, controller, title: str, show_menu: bool = True, **kwargs):
        kwargs.setdefault("fg_color", PALETTE["CARD"])
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("height", self.HEIGHT)
        super().__init__(parent, **kwargs)
        self.pack_propagate(False)
        self.controller = controller

        if show_menu:
            ctk.CTkButton(
                self, text="", image=get_icon("bars", 20, PALETTE["TEXT"]),
                width=44, height=44, corner_radius=999,
                fg_color=PALETTE["SURFACE_ALT"], hover_color=PALETTE["BORDER"],
                command=self._open_nav,
            ).pack(side="left", padx=(14, 6))

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(0, 6))

        brand = ctk.CTkFrame(left, fg_color=PALETTE["ACCENT"], corner_radius=999,
                              width=34, height=34)
        brand.pack(side="left", pady=15)
        brand.pack_propagate(False)
        ctk.CTkLabel(brand, text="SL", text_color=PALETTE["WHITE"],
                     font=theme.font_display(13, "bold"),
                     fg_color="transparent").place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            left, text=title, font=theme.font_display(17, "bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=(10, 0))

        # Presente solo cuando se llegó al panel admin desde el puente del
        # kiosco (LockerApp.confirm_kiosk_exit) — sin equivalente en el web.
        if hasattr(controller, "confirm_kiosk_exit"):
            ctk.CTkButton(
                self, text="", image=get_icon("times", 16, PALETTE["TEXT"]),
                width=40, height=40, corner_radius=999,
                fg_color=PALETTE["SURFACE_ALT"], hover_color=PALETTE["DANGER"],
                command=controller.confirm_kiosk_exit,
            ).pack(side="right", padx=(0, 0))

    def _open_nav(self) -> None:
        NavDrawer(self.winfo_toplevel(), self.controller).open()


# ── NavDrawer ──────────────────────────────────────────────────────────────

# (label_key, icon, frame_module, frame_attr, superadmin_only)
_NAV_ITEMS = [
    ("nav.inicio",       "home",  "ui.admin.dashboard",         "DashboardScreen",       False),
    ("nav.usuarios",     "user",  "ui.admin.users_catalog",     "UsersCatalogScreen",    False),
    ("nav.lockers",      "box",   "ui.admin.lockers_catalog",   "LockersCatalogScreen",  False),
    ("nav.asignaciones", "link",  "ui.admin.locker_assignment", "LockerAssignmentScreen",False),
    ("nav.historial",    "clock", "ui.admin.access_history",    "AccessHistoryScreen",   False),
]

_CATALOG_ITEMS = [
    ("nav.unidades",      "ui.admin.faculty_catalog",    "FacultyCatalogScreen"),
    ("nav.areas",         "ui.admin.areas_catalog",      "AreasCatalogScreen"),
    ("nav.tipos_usuario", "ui.admin.user_types_catalog", "UserTypesCatalogScreen"),
]


class NavDrawer(ctk.CTkFrame):
    """Panel de navegación anclado al borde IZQUIERDO, angosto (no cubre toda
    la ventana): el contenido de la pantalla de atrás queda visible en el
    resto del ancho, sin overlay opaco encima. Mismo listado y mismo orden
    que la topbar del web (Inicio, Usuarios, Lockers, Asignaciones,
    Historial, Catálogos[superadmin]), con el menú de usuario (Mi perfil /
    Cerrar sesión) al fondo."""

    WIDTH = 300

    def __init__(self, host: ctk.CTk, controller):
        super().__init__(
            host, fg_color=PALETTE["BG"], corner_radius=0,
            border_width=1, border_color=PALETTE["BORDER"], width=self.WIDTH,
        )
        self.host = host
        self.controller = controller
        self._catalogs_open = False
        self.pack_propagate(False)
        self._build()

    def open(self) -> None:
        self.place(x=0, y=0, relheight=1.0, anchor="nw")
        self.lift()

    def _close(self) -> None:
        self.destroy()

    def _navigate(self, module_path: str, class_name: str) -> None:
        import importlib
        module = importlib.import_module(module_path)
        frame_class = getattr(module, class_name)
        self._close()
        self.controller.show_frame(frame_class)

    def _build(self) -> None:
        from auth.session import is_superadmin, get_current_full_name, get_current_role_label

        panel = self

        header = ctk.CTkFrame(panel, fg_color="transparent", height=64)
        header.pack(fill="x", padx=18, pady=(18, 6))
        ctk.CTkLabel(header, text="Smart Locker", font=theme.font_display(18, "bold"),
                     text_color=PALETTE["TEXT"]).pack(side="left")
        ctk.CTkButton(
            header, text="", image=get_icon("times", 16, PALETTE["MUTED"]),
            width=36, height=36, corner_radius=999,
            fg_color=PALETTE["SURFACE_ALT"], hover_color=PALETTE["BORDER"],
            command=self._close,
        ).pack(side="right")

        # Utilidades propias del Pi sin equivalente en la topbar del web
        # (tema claro/oscuro, idioma ES/EN) — se agrupan aparte del listado
        # de navegación para no romper el mapeo 1:1 con el web.
        utils_row = ctk.CTkFrame(panel, fg_color="transparent")
        utils_row.pack(fill="x", padx=18, pady=(0, 10))
        _mode = getattr(self.controller, "_mode", "light")
        theme_icon = "moon" if _mode == "light" else "sun"
        if hasattr(self.controller, "toggle_theme"):
            ctk.CTkButton(
                utils_row, text="", image=get_icon(theme_icon, 18, PALETTE["TEXT"]),
                width=40, height=40, corner_radius=999,
                fg_color=PALETTE["SURFACE_ALT"], hover_color=PALETTE["BORDER"],
                command=lambda: (self._close(), self.controller.toggle_theme()),
            ).pack(side="left", padx=(0, 8))
        if hasattr(self.controller, "toggle_lang"):
            ctk.CTkButton(
                utils_row, text=lang_btn_text(), font=theme.font_body(12),
                height=40, corner_radius=999,
                fg_color=PALETTE["SURFACE_ALT"], hover_color=PALETTE["BORDER"],
                text_color=PALETTE["TEXT"],
                command=lambda: (self._close(), self.controller.toggle_lang()),
            ).pack(side="left")

        body = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10)

        for label_key, icon, module_path, class_name, superadmin_only in _NAV_ITEMS:
            if superadmin_only and not is_superadmin():
                continue
            self._nav_button(body, t(label_key), icon,
                              lambda m=module_path, c=class_name: self._navigate(m, c))

        # ── Catálogos (solo superadmin, expandible como el <details> del web) ──
        if is_superadmin():
            toggle_row = ctk.CTkFrame(body, fg_color="transparent")
            toggle_row.pack(fill="x", pady=(4, 0))
            self._catalog_chevron = ctk.CTkLabel(
                toggle_row, image=get_icon("chevron-down", 14, PALETTE["MUTED"]), text="")
            btn = ctk.CTkButton(
                toggle_row, text=t("nav.catalogos"), image=get_icon("layers", 18, PALETTE["TEXT"]),
                anchor="w", compound="left", fg_color="transparent", hover_color=PALETTE["SURFACE_ALT"],
                text_color=PALETTE["TEXT"], font=theme.font_body(14),
                height=46, corner_radius=10, command=self._toggle_catalogs,
            )
            btn.pack(side="left", fill="x", expand=True)
            self._catalog_chevron.pack(in_=toggle_row, side="right", padx=10)

            self._catalog_sub = ctk.CTkFrame(body, fg_color="transparent")
            for label_key, module_path, class_name in _CATALOG_ITEMS:
                self._nav_button(self._catalog_sub, t(label_key), None,
                                  lambda m=module_path, c=class_name: self._navigate(m, c),
                                  indent=True)

        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(6, 18), side="bottom")

        avatar = ctk.CTkFrame(footer, fg_color=PALETTE["ACCENT_SOFT"], corner_radius=999,
                               width=38, height=38)
        avatar.pack(side="left")
        avatar.pack_propagate(False)
        initial = (get_current_full_name() or "?")[:1].upper()
        ctk.CTkLabel(avatar, text=initial, text_color=PALETTE["ACCENT"],
                     font=theme.font_body(14, "bold")).place(relx=0.5, rely=0.5, anchor="center")

        name_box = ctk.CTkFrame(footer, fg_color="transparent")
        name_box.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkLabel(name_box, text=get_current_full_name() or "—", anchor="w",
                     font=theme.font_body(13, "bold"), text_color=PALETTE["TEXT"]).pack(fill="x")
        ctk.CTkLabel(name_box, text=get_current_role_label(), anchor="w",
                     font=theme.font_body(11), text_color=PALETTE["MUTED"]).pack(fill="x")

        self._nav_button(panel, t("nav.mi_perfil"), "user", self._open_profile, pad_bottom=True)
        self._nav_button(panel, t("nav.cerrar_sesion"), "logout", self._logout,
                          danger=True, pad_bottom=True)

    def _toggle_catalogs(self) -> None:
        self._catalogs_open = not self._catalogs_open
        if self._catalogs_open:
            self._catalog_sub.pack(fill="x", padx=0, pady=(0, 4))
        else:
            self._catalog_sub.pack_forget()

    def _nav_button(self, parent, text: str, icon: str | None, command,
                     indent: bool = False, danger: bool = False, pad_bottom: bool = False) -> None:
        color = PALETTE["DANGER"] if danger else PALETTE["TEXT"]
        kwargs = dict(
            text=text, anchor="w", compound="left",
            fg_color="transparent", hover_color=PALETTE["SURFACE_ALT"],
            text_color=color, font=theme.font_body(14),
            height=44, corner_radius=10, command=command,
        )
        if icon:
            kwargs["image"] = get_icon(icon, 18, color)
        btn = ctk.CTkButton(parent, **kwargs)
        padx = (28, 4) if indent else (4, 4)
        pady = (0, 12) if pad_bottom else (2, 0)
        btn.pack(fill="x", padx=padx, pady=pady)

    def _open_profile(self) -> None:
        # UsersCatalogScreen.on_show acepta open_user_id para abrir directo
        # el overlay de detalle del usuario en sesión (ver Fase 3).
        from auth.session import get_current_user_id
        import importlib

        module = importlib.import_module("ui.admin.users_catalog")
        frame_class = module.UsersCatalogScreen
        self._close()
        self.controller.show_frame(frame_class, open_user_id=get_current_user_id())

    def _logout(self) -> None:
        self._close()
        ConfirmDialog.ask(
            self.host,
            title=t("logout.dialog_title"),
            message=t("logout.message"),
            confirm_text=t("logout.yes"),
            cancel_text=t("logout.no"),
            on_confirm=self.controller.logout,
        )
