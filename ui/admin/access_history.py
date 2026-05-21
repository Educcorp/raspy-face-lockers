"""Historial de accesos al locker con buscador y filtros."""

from __future__ import annotations

import customtkinter as ctk

from services import access_log_service
from ui.admin_app import PALETTE
from ui.i18n import t

_MOTIVOS_CONCEDIDOS = {"facial", "pin"}

_MOTIVO_LABELS: dict[str, str] = {
    "facial":               "Rostro",
    "pin":                  "PIN",
    "pin_cancelado":        "Intento fallido",
    "pin_incorrecto":       "PIN incorrecto",
    "limite_intentos_pin":  "Intentos agotados",
    "no_reconocido":        "No reconocido",
    "matricula_incorrecta": "Matrícula incorrecta",
    "sin_asignacion":       "Sin asignación",
}

_ALL      = "Todos"
_GRANTED  = "Concedidos"
_DENIED   = "Denegados"


class AccessHistoryScreen(ctk.CTkFrame):
    """Historial de accesos con buscador de texto y filtros de estado/motivo."""

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._rows: list[dict] = []
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Cabecera ──────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkButton(
            hdr,
            text="←",
            width=46, height=46,
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color="transparent",
            hover_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            command=self._go_back,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            hdr,
            text=t("areas.tab.history"),
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(side="left", padx=4)

        # ── Buscador ──────────────────────────────────────────────────────────
        search_row = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=50, corner_radius=0)
        search_row.pack(fill="x")
        search_row.pack_propagate(False)

        ctk.CTkLabel(
            search_row,
            text="🔍",
            font=ctk.CTkFont(size=16),
            fg_color="transparent",
            text_color=PALETTE["MUTED"],
        ).pack(side="left", padx=(10, 2))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filters())
        ctk.CTkEntry(
            search_row,
            textvariable=self._search_var,
            placeholder_text="Buscar por nombre, locker…",
            height=32,
            font=ctk.CTkFont(size=13),
            fg_color=PALETTE["BG"],
            border_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            placeholder_text_color=PALETTE["MUTED"],
        ).pack(side="left", fill="x", expand=True, padx=(0, 10), pady=9)

        # ── Filtros rápidos (chips) ────────────────────────────────────────────
        chip_row = ctk.CTkFrame(self, fg_color=PALETTE["BG"], height=44, corner_radius=0)
        chip_row.pack(fill="x", padx=10)
        chip_row.pack_propagate(False)

        self._estado_var = ctk.StringVar(value=_ALL)

        for label in (_ALL, _GRANTED, _DENIED):
            ctk.CTkButton(
                chip_row,
                text=label,
                width=90, height=30,
                font=ctk.CTkFont(size=12),
                fg_color=PALETTE["ACCENT"] if label == _ALL else PALETTE["CARD"],
                hover_color=PALETTE["ACCENT"],
                text_color=PALETTE["WHITE"] if label == _ALL else PALETTE["TEXT"],
                corner_radius=15,
                command=lambda lbl=label: self._set_estado(lbl),
            ).pack(side="left", padx=4, pady=7)

        # Guardamos referencia a los chips para actualizar colores
        self._chip_buttons: dict[str, ctk.CTkButton] = {
            btn.cget("text"): btn
            for btn in chip_row.winfo_children()
            if isinstance(btn, ctk.CTkButton)
        }

        # ── Filtro motivo ──────────────────────────────────────────────────────
        motivo_row = ctk.CTkFrame(self, fg_color=PALETTE["BG"], height=40, corner_radius=0)
        motivo_row.pack(fill="x", padx=10)
        motivo_row.pack_propagate(False)

        ctk.CTkLabel(
            motivo_row,
            text="Motivo:",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(side="left", padx=(0, 4))

        self._motivo_var = ctk.StringVar(value=_ALL)
        self._combo_motivo = ctk.CTkComboBox(
            motivo_row,
            variable=self._motivo_var,
            values=[_ALL],
            width=200, height=30,
            font=ctk.CTkFont(size=12),
            fg_color=PALETTE["BG"],
            border_color=PALETTE["BORDER"],
            button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT"],
            dropdown_fg_color=PALETTE["CARD"],
            dropdown_text_color=PALETTE["TEXT"],
            text_color=PALETTE["TEXT"],
            state="readonly",
            command=lambda _: self._apply_filters(),
        )
        self._combo_motivo.pack(side="left")

        # ── Lista scrollable ───────────────────────────────────────────────────
        self._list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=PALETTE["BG"],
            scrollbar_button_color=PALETTE["BORDER"],
            scrollbar_button_hover_color=PALETTE["ACCENT"],
        )
        self._list_frame.pack(fill="both", expand=True, padx=12, pady=(4, 10))

    # ── Navegación ────────────────────────────────────────────────────────────

    def _go_back(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        self._rows = access_log_service.get_access_history(limit=200)

        # Actualizar opciones de motivo con los reales del dataset
        labels = [_ALL]
        seen: set[str] = set()
        for row in self._rows:
            m = row.get("motivo") or ""
            lbl = _MOTIVO_LABELS.get(m, m)
            if lbl and lbl not in seen:
                seen.add(lbl)
                labels.append(lbl)
        self._combo_motivo.configure(values=labels)
        if self._motivo_var.get() not in labels:
            self._motivo_var.set(_ALL)

        self._apply_filters()

    def _set_estado(self, estado: str) -> None:
        self._estado_var.set(estado)
        # Actualizar colores de chips
        for label, btn in self._chip_buttons.items():
            active = label == estado
            btn.configure(
                fg_color=PALETTE["ACCENT"] if active else PALETTE["CARD"],
                text_color=PALETTE["WHITE"] if active else PALETTE["TEXT"],
            )
        self._apply_filters()

    def _is_concedido(self, row: dict) -> bool:
        raw = row.get("accesoPermitido") or ""
        if raw:
            return raw.lower() in ("si", "yes", "1", "true")
        return (row.get("motivo") or "") in _MOTIVOS_CONCEDIDOS

    def _apply_filters(self) -> None:
        query  = self._search_var.get().strip().lower()
        estado = self._estado_var.get()
        motivo_sel = self._motivo_var.get()

        # Invertir label → clave interna
        label_to_key = {v: k for k, v in _MOTIVO_LABELS.items()}

        result: list[dict] = []
        for row in self._rows:
            concedido = self._is_concedido(row)

            # Filtro estado
            if estado == _GRANTED and not concedido:
                continue
            if estado == _DENIED and concedido:
                continue

            # Filtro motivo
            if motivo_sel != _ALL:
                motivo_key = label_to_key.get(motivo_sel, motivo_sel)
                if (row.get("motivo") or "") != motivo_key:
                    continue

            # Búsqueda de texto libre
            if query:
                haystack = " ".join([
                    str(row.get("idLocker") or ""),
                    str(row.get("nombreCompleto") or ""),
                    str(row.get("motivo") or ""),
                    str(row.get("fechaHoraAcceso") or ""),
                ]).lower()
                if query not in haystack:
                    continue

            result.append(row)

        self._render_rows(result)

    # ── Renderizado ───────────────────────────────────────────────────────────

    def _render_rows(self, rows: list[dict]) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()

        if not rows:
            ctk.CTkLabel(
                self._list_frame,
                text=t("hist.no_records"),
                font=ctk.CTkFont(size=15),
                text_color=PALETTE["MUTED"],
                fg_color="transparent",
            ).pack(pady=40)
            return

        for row in rows:
            locker_num  = row.get("idLocker") or "—"
            owner       = row.get("nombreCompleto") or t("hist.unknown_user")
            access_time = row.get("fechaHoraAcceso") or "—"
            motivo_raw  = row.get("motivo") or ""

            date_part, time_part = "—", "—"
            if isinstance(access_time, str):
                parts = access_time.replace("T", " ").split()
                if len(parts) >= 2:
                    date_part, time_part = parts[0], parts[1]
                elif parts:
                    date_part = parts[0]

            concedido    = self._is_concedido(row)
            badge_text   = t("hist.granted") if concedido else t("hist.denied")
            badge_color  = PALETTE["ACCENT"] if concedido else PALETTE["DANGER"]
            motivo_label = _MOTIVO_LABELS.get(motivo_raw, motivo_raw or "—")

            card = ctk.CTkFrame(
                self._list_frame,
                fg_color=PALETTE["CARD"],
                corner_radius=12,
                border_width=1,
                border_color=PALETTE["BORDER"],
            )
            card.pack(fill="x", padx=4, pady=4)

            # Primera línea: locker + badge
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 0))

            ctk.CTkLabel(
                top,
                text=f"Locker {locker_num}",
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=PALETTE["TEXT"],
                fg_color="transparent",
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                top,
                text=badge_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#FFFFFF",
                fg_color=badge_color,
                corner_radius=8,
                width=78, height=22,
            ).pack(side="right")

            ctk.CTkLabel(
                card,
                text=owner,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=PALETTE["TEXT"],
                fg_color="transparent",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(4, 0))

            ctk.CTkLabel(
                card,
                text=f"{date_part}  {time_part}",
                font=ctk.CTkFont(size=12),
                text_color=PALETTE["MUTED"],
                fg_color="transparent",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(2, 0))

            ctk.CTkLabel(
                card,
                text=f"Motivo: {motivo_label}",
                font=ctk.CTkFont(size=12),
                text_color=PALETTE["MUTED"],
                fg_color="transparent",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(2, 10))

    def on_show(self, **_kwargs) -> None:
        self._load()
