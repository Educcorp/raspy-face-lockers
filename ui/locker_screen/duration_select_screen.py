"""
DurationSelectScreen – elige por cuánto tiempo se usará el recurso (480×800 px).

Flujo: ModeSelectScreen → ResourceSelectScreen (elegir recurso, sin
autenticar) → aquí (elegir tiempo) → confirma → ScanningScreen en modo
FLOW_RESOURCE_CLAIM_AUTH, que autentica y RECIÉN AHÍ valida autorización y
reclama la sesión/activa el relé — a pedido explícito del usuario
(2026-09-30), autenticarse es el último paso, no el primero.

El tiempo se elige con 3 bandas HH:MM:SS — tocar una abre un teclado numérico
para escribir el valor con precisión, en vez de botones fijos o un spinner de
un solo paso.
"""

import logging

import customtkinter as ctk

from ui.i18n import t
from ui import theme
from ui.theme import PALETTE
from ui.locker_screen.resource_select_screen import resource_display_name

logger = logging.getLogger(__name__)

# Tope de 3 horas por préstamo — pedido explícitamente para no dejar una
# herramienta activa indefinidamente. Piso de 1 minuto (evita una sesión de
# 1 segundo por error de captura).
MAX_SECONDS = 3 * 3600
MIN_SECONDS = 60
DEFAULT_HMS = (0, 30, 0)   # 30 min por defecto, igual que antes

_UNIT_LABELS = {"h": "duration.hours", "m": "duration.minutes", "s": "duration.seconds"}
_UNIT_MAX = {"h": 3, "m": 59, "s": 59}


def duration_display_label(total_seconds: int | None) -> str:
    """Etiqueta localizada de una duración a partir de segundos totales."""
    if not total_seconds:
        return "—"
    h, rem = divmod(int(total_seconds), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} h")
    if m or h:
        parts.append(f"{m} min")
    if s:
        parts.append(f"{s} s")
    if not parts:
        parts.append(f"{s} s")
    return " ".join(parts)


class DurationSelectScreen(ctk.CTkFrame):
    """
    Selección del tiempo de uso del recurso (modo kiosk).

    Parámetros
    ----------
    parent     : widget padre (la ventana raíz LockerApp)
    controller : LockerApp – expone show_frame() para navegar
    """

    BG_COLOR = PALETTE["BG"]

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._resource: dict | None = None
        self._hours, self._minutes, self._seconds = DEFAULT_HMS
        self._active_unit: str | None = None
        self._numpad_buffer = ""
        self._build_ui()

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent", height=64)
        header.pack(fill="x", padx=18, pady=(18, 6))

        ctk.CTkButton(
            header,
            text=t("common.back"),
            font=theme.font_body(14, "bold"),
            fg_color="transparent",
            hover_color=PALETTE["SURFACE_ALT"],
            text_color=PALETTE["TEXT"],
            width=110, height=40,
            corner_radius=14,
            command=self._go_back,
        ).pack(side="left")

        title_block = ctk.CTkFrame(self, fg_color="transparent")
        title_block.pack(fill="x", padx=24, pady=(10, 4))

        ctk.CTkLabel(
            title_block,
            text=t("duration.page_title"),
            font=theme.font_display(24, "bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w")

        self.lbl_instruction = ctk.CTkLabel(
            title_block,
            text="",
            font=theme.font_body(14),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            wraplength=420,
            justify="left",
        )
        self.lbl_instruction.pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(
            title_block,
            text=t("duration.max_note"),
            font=theme.font_body(12, "bold"),
            text_color=PALETTE["WARN"],
            fg_color="transparent",
        ).pack(anchor="w", pady=(8, 0))

        # ── Bandas HH : MM : SS — tocar una abre el teclado numérico ────────────
        bands = ctk.CTkFrame(self, fg_color="transparent")
        bands.pack(pady=(28, 4))

        self._band_labels: dict[str, ctk.CTkLabel] = {}
        for i, unit in enumerate(("h", "m", "s")):
            if i > 0:
                ctk.CTkLabel(
                    bands, text=":", font=theme.font_display(40, "bold"),
                    text_color=PALETTE["MUTED"], fg_color="transparent",
                ).pack(side="left", padx=4)

            box = ctk.CTkFrame(
                bands, fg_color=PALETTE["CARD"], corner_radius=theme.RADIUS_CARD,
                border_width=1, border_color=PALETTE["BORDER"],
                width=96, height=96,
            )
            box.pack(side="left", padx=6)
            box.pack_propagate(False)

            lbl = ctk.CTkLabel(
                box, text="00", font=theme.font_display(36, "bold"),
                text_color=PALETTE["TEXT"], fg_color="transparent",
            )
            lbl.place(relx=0.5, rely=0.5, anchor="center")
            box.bind("<Button-1>", lambda _e, u=unit: self._open_numpad(u))
            lbl.bind("<Button-1>", lambda _e, u=unit: self._open_numpad(u))
            self._band_labels[unit] = lbl

        unit_captions = ctk.CTkFrame(self, fg_color="transparent")
        unit_captions.pack(pady=(2, 0))
        for unit, key in (("h", "duration.hours"), ("m", "duration.minutes"), ("s", "duration.seconds")):
            ctk.CTkLabel(
                unit_captions, text=t(key), font=theme.font_body(11),
                text_color=PALETTE["MUTED"], fg_color="transparent", width=102,
            ).pack(side="left")

        self.lbl_duration_preview = ctk.CTkLabel(
            self, text="", font=theme.font_body(14, "bold"),
            text_color=PALETTE["ACCENT"], fg_color="transparent",
        )
        self.lbl_duration_preview.pack(pady=(14, 0))

        self.lbl_busy_warning = ctk.CTkLabel(
            self,
            text="",
            font=theme.font_body(13, "bold"),
            text_color=PALETTE["DANGER"],
            fg_color="transparent",
        )
        self.lbl_busy_warning.pack(pady=(8, 0))

        self.btn_confirm = ctk.CTkButton(
            self,
            text=t("duration.confirm"),
            font=theme.font_body(17, "bold"),
            fg_color=PALETTE["ACCENT"],
            hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"],
            height=58,
            corner_radius=theme.RADIUS_PILL,
            command=self._confirm,
        )
        self.btn_confirm.pack(fill="x", side="bottom", padx=18, pady=(0, 18))

        self._build_numpad_overlay()

    def _build_numpad_overlay(self) -> None:
        """Teclado numérico 3×4 para escribir el valor de una banda (horas,
        minutos o segundos) — mismo lenguaje visual que el teclado de PIN de
        ScanningScreen."""
        self.numpad_overlay = ctk.CTkFrame(
            self, fg_color=self.BG_COLOR, corner_radius=0,
            width=480, height=800,
        )

        self.lbl_numpad_title = ctk.CTkLabel(
            self.numpad_overlay, text="", font=theme.font_display(22, "bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        )
        self.lbl_numpad_title.pack(pady=(70, 8))

        display_box = ctk.CTkFrame(
            self.numpad_overlay, fg_color=PALETTE["CARD"], corner_radius=16,
            border_width=1, border_color=PALETTE["BORDER"], width=200, height=64,
        )
        display_box.pack(pady=(0, 20))
        display_box.pack_propagate(False)

        self.lbl_numpad_display = ctk.CTkLabel(
            display_box, text="00", font=theme.font_display(30, "bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        )
        self.lbl_numpad_display.place(relx=0.5, rely=0.5, anchor="center")

        pad = ctk.CTkFrame(self.numpad_overlay, fg_color="transparent")
        pad.pack()

        layout = [("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("⌫", "0", "✓")]
        for row_idx, row in enumerate(layout):
            for col_idx, label in enumerate(row):
                if label == "⌫":
                    cmd = self._numpad_backspace
                    fg, hover, txt = PALETTE["CARD"], PALETTE["DANGER"], PALETTE["TEXT"]
                elif label == "✓":
                    cmd = self._numpad_confirm
                    fg, hover, txt = PALETTE["ACCENT"], PALETTE["ACCENT_HOVER"], PALETTE["WHITE"]
                else:
                    digit = label
                    cmd = lambda d=digit: self._numpad_digit(d)
                    fg, hover, txt = PALETTE["CARD"], PALETTE["ACCENT_SOFT"], PALETTE["TEXT"]

                ctk.CTkButton(
                    pad, text=label, font=theme.font_display(24, "bold"),
                    fg_color=fg, hover_color=hover, text_color=txt,
                    width=92, height=72, corner_radius=999, command=cmd,
                ).grid(row=row_idx, column=col_idx, padx=8, pady=8)

        ctk.CTkButton(
            self.numpad_overlay,
            text=t("common.cancel"),
            font=theme.font_body(14, "bold"),
            fg_color="transparent",
            hover_color=PALETTE["SURFACE_ALT"],
            text_color=PALETTE["MUTED"],
            border_width=1, border_color=PALETTE["BORDER"],
            width=200, height=44, corner_radius=999,
            command=self._close_numpad,
        ).pack(pady=(16, 0))

    # ── Teclado numérico por banda ───────────────────────────────────────────

    def _open_numpad(self, unit: str) -> None:
        self._active_unit = unit
        self._numpad_buffer = ""
        self.lbl_numpad_title.configure(text=t(_UNIT_LABELS[unit]))
        self.lbl_numpad_display.configure(text="00")
        self.numpad_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.numpad_overlay.lift()

    def _close_numpad(self) -> None:
        self.numpad_overlay.place_forget()
        self._active_unit = None

    def _numpad_digit(self, digit: str) -> None:
        if len(self._numpad_buffer) >= 2:
            self._numpad_buffer = self._numpad_buffer[-1:]  # desliza, como un odómetro
        self._numpad_buffer += digit
        self.lbl_numpad_display.configure(text=self._numpad_buffer.rjust(2, "0"))

    def _numpad_backspace(self) -> None:
        self._numpad_buffer = self._numpad_buffer[:-1]
        self.lbl_numpad_display.configure(text=self._numpad_buffer.rjust(2, "0"))

    def _numpad_confirm(self) -> None:
        unit = self._active_unit
        if unit is None:
            return
        value = min(int(self._numpad_buffer or "0"), _UNIT_MAX[unit])
        if unit == "h":
            self._hours = value
        elif unit == "m":
            self._minutes = value
        else:
            self._seconds = value
        self._clamp_total()
        self._close_numpad()
        self._render_bands()

    # ── Total y vista previa ─────────────────────────────────────────────────

    def _total_seconds(self) -> int:
        return self._hours * 3600 + self._minutes * 60 + self._seconds

    def _clamp_total(self) -> None:
        total = self._total_seconds()
        if total > MAX_SECONDS:
            total = MAX_SECONDS
            self._hours, rem = divmod(total, 3600)
            self._minutes, self._seconds = divmod(rem, 60)

    def _render_bands(self) -> None:
        self._band_labels["h"].configure(text=f"{self._hours:02d}")
        self._band_labels["m"].configure(text=f"{self._minutes:02d}")
        self._band_labels["s"].configure(text=f"{self._seconds:02d}")
        self.lbl_duration_preview.configure(text=duration_display_label(self._total_seconds()))

    # ── Navegación ────────────────────────────────────────────────────────────

    def _confirm(self) -> None:
        total_seconds = self._total_seconds()
        if total_seconds < MIN_SECONDS:
            self.lbl_busy_warning.configure(text=t("duration.too_short"))
            return

        recurso = self._resource or {}
        if recurso.get("idRecurso") is None:
            self._go_back()
            return

        # Todavía no hay usuario identificado — eso es lo próximo:
        # ScanningScreen (FLOW_RESOURCE_CLAIM_AUTH) autentica y, ya con la
        # identidad real, valida autorización y reclama la sesión/activa el
        # relé. Nada de eso ocurre en esta pantalla.
        from ui.locker_screen.scanning_screen import ScanningScreen
        self.controller.show_frame(
            ScanningScreen,
            mode=ScanningScreen.FLOW_RESOURCE_CLAIM_AUTH,
            resource=recurso,
            duration_seconds=total_seconds,
        )

    def _go_back(self) -> None:
        from ui.locker_screen.resource_select_screen import ResourceSelectScreen
        self.controller.show_frame(ResourceSelectScreen)

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self, resource: dict | None = None) -> None:
        self._resource = resource
        self._hours, self._minutes, self._seconds = DEFAULT_HMS
        self._close_numpad()
        self.lbl_busy_warning.configure(text="")
        self._render_bands()
        self.lbl_instruction.configure(
            text=t("duration.instruction", resource=resource_display_name(resource))
        )
