"""
ModeSelectScreen – pantalla inicial "Smart Access" (480×800 px).

Primera pantalla que ve el usuario. Reemplaza a StandbyScreen como punto de
entrada de LockerApp: en vez de arrancar directo con el auto-escaneo del
locker, pregunta qué se quiere hacer.

    ModeSelectScreen ──"Abrir locker"────► ScanningScreen (FLOW_LOCKER, directo)
                     └─"Activar recurso"─► ResourceSelectScreen (elegir recurso)

StandbyScreen (la pantalla de "acércate a la cámara" con detección de
proximidad) ya no es parte de este flujo — a pedido explícito del usuario
(2026-09-30) es un paso intermedio innecesario ahora que existe este menú;
"Abrir locker" salta directo a ScanningScreen, igual que "Activar recurso"
salta directo al catálogo de recursos.

No toca cámara ni GPIO — es solo navegación, igual de ligera que un menú.
"""

import customtkinter as ctk
import logging
import os
from PIL import Image

from ui.i18n import t, lang_btn_text
from ui import theme
from ui.theme import PALETTE

logger = logging.getLogger(__name__)


class ModeSelectScreen(ctk.CTkFrame):
    """
    Pantalla de selección de modo (modo kiosk).

    Parámetros
    ----------
    parent     : widget padre (la ventana raíz LockerApp)
    controller : LockerApp – expone show_frame() para navegar
    """

    # Misma identidad visual que StandbyScreen (portada de marca).
    BG_COLOR   = PALETTE["ACCENT"]
    SECONDARY  = PALETTE["ACCENT_SOFT_STRONG"]
    TEXT_COLOR = PALETTE["WHITE"]

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._build_ui()

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Espacio superior ──────────────────────────────────────────────────
        ctk.CTkLabel(self, text="", fg_color="transparent").grid(row=0, column=0)

        # ── Logo ──────────────────────────────────────────────────────────────
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "icons", "smartlocker_logo.png"
        )
        self._logo_image = None
        try:
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path)
                self._logo_image = ctk.CTkImage(
                    light_image=logo_img,
                    dark_image=logo_img,
                    size=(200, 200),
                )
        except Exception as e:
            logger.warning(f"No se pudo cargar logo en ModeSelectScreen: {e}")

        ctk.CTkLabel(
            self, text="", image=self._logo_image, fg_color="transparent",
        ).grid(row=1, column=0)

        # ── Marca + subtítulo ─────────────────────────────────────────────────
        text_block = ctk.CTkFrame(self, fg_color="transparent")
        text_block.grid(row=2, column=0)

        ctk.CTkLabel(
            text_block,
            text=t("mode.brand"),
            font=theme.font_display(30, "bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        ).pack(pady=(0, 6))

        self.lbl_subtitle = ctk.CTkLabel(
            text_block,
            text=t("mode.subtitle"),
            font=theme.font_body(15),
            text_color=self.SECONDARY,
            fg_color="transparent",
        )
        self.lbl_subtitle.pack()

        # ── Opciones principales ──────────────────────────────────────────────
        options = ctk.CTkFrame(self, fg_color="transparent")
        options.grid(row=3, column=0, rowspan=2, pady=(10, 0))

        self.btn_locker = ctk.CTkButton(
            options,
            text=t("mode.open_locker"),
            font=theme.font_body(19, "bold"),
            fg_color=PALETTE["WHITE"],
            hover_color=self.SECONDARY,
            text_color=PALETTE["ACCENT"],
            width=320, height=64,
            corner_radius=18,
            command=self._go_locker_flow,
        )
        self.btn_locker.pack(pady=(0, 16))

        self.btn_resource = ctk.CTkButton(
            options,
            text=t("mode.activate_resource"),
            font=theme.font_body(19, "bold"),
            fg_color="transparent",
            hover_color=self.SECONDARY,
            text_color=PALETTE["WHITE"],
            border_width=2,
            border_color=PALETTE["WHITE"],
            width=320, height=64,
            corner_radius=18,
            command=self._go_resource_flow,
        )
        self.btn_resource.pack()

        # ── Botón de idioma ───────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=5, column=0, pady=(0, 30))

        self.btn_lang = ctk.CTkButton(
            btn_row,
            text=lang_btn_text(),
            font=theme.font_body(14),
            fg_color="transparent",
            hover_color=self.SECONDARY,
            text_color=self.TEXT_COLOR,
            border_width=2,
            border_color=self.TEXT_COLOR,
            width=140, height=48,
            corner_radius=14,
            command=self.controller.toggle_lang,
        )
        self.btn_lang.pack()

    # ── Navegación ────────────────────────────────────────────────────────────

    def _go_locker_flow(self) -> None:
        # Directo a escaneo — la pantalla intermedia de "acércate a la
        # cámara" (StandbyScreen) ya no hace falta con este menú como punto
        # de entrada (a pedido explícito del usuario, 2026-09-30).
        from ui.locker_screen.scanning_screen import ScanningScreen
        self.controller.show_frame(ScanningScreen, mode=ScanningScreen.FLOW_LOCKER)

    def _go_resource_flow(self) -> None:
        # Catálogo primero, sin autenticar — se elige el recurso y el tiempo
        # antes de nada; la autenticación es el último paso, dentro de
        # DurationSelectScreen → ScanningScreen (FLOW_RESOURCE_CLAIM_AUTH),
        # donde recién se valida autorización y se reclama la sesión.
        from ui.locker_screen.resource_select_screen import ResourceSelectScreen
        self.controller.show_frame(ResourceSelectScreen)

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """No hay estado ni hilos que reiniciar — solo navegación."""
        pass
