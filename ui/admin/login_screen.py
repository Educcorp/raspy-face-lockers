"""Pantalla de login para el panel administrativo."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from auth.session import authenticate_admin_user, set_current_user
from core.i18n import t, register_observer, unregister_observer
from ui.admin_app import PALETTE, get_icon
from ui.components.language_button import LanguageToggleButton


class LoginScreen(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._lang_reg: list = []

        self._matricula_var = tk.StringVar()
        self._pin_var = tk.StringVar()
        self._show_pin_var = tk.BooleanVar(value=False)

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
        # Also refresh placeholder text for entries
        try:
            if self.entry_matricula.winfo_exists():
                self.entry_matricula.configure(placeholder_text=t("login_placeholder_mat"))
        except Exception:
            pass

    def destroy(self) -> None:
        unregister_observer(self._on_lang_change)
        super().destroy()

    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            width=340,
            height=340,
            corner_radius=170,
            border_width=0,
        ).place(relx=-0.03, rely=0.03, anchor="nw")

        ctk.CTkFrame(
            self,
            fg_color=PALETTE["BORDER"],
            width=190,
            height=190,
            corner_radius=95,
            border_width=0,
        ).place(relx=0.98, rely=0.33, anchor="ne")

        ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            width=220,
            height=220,
            corner_radius=110,
            border_width=0,
        ).place(relx=1.0, rely=1.0, anchor="se")

        top = ctk.CTkFrame(self, fg_color=PALETTE["BG"], corner_radius=0, height=184)
        top.pack(fill="x")
        top.pack_propagate(False)

        hero = ctk.CTkFrame(
            top,
            fg_color=PALETTE["CARD"],
            corner_radius=14,
            border_width=0,
        )
        hero.pack(fill="both", expand=True, padx=16, pady=(12, 8))

        top_inner = ctk.CTkFrame(top, fg_color="transparent", border_width=0, corner_radius=0)
        top_inner.place(in_=hero, relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
        top_inner.pack_propagate(False)

        ctk.CTkLabel(
            top_inner,
            text="Smart Locker",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
        ).pack(anchor="w", pady=(16, 0))

        lbl_title = ctk.CTkLabel(
            top_inner,
            text=t("login_title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        )
        lbl_title.pack(anchor="w", pady=(2, 4))
        self._lang_reg.append((lbl_title, "login_title", {}))

        lbl_subtitle = ctk.CTkLabel(
            top_inner,
            text=t("login_subtitle"),
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            justify="left",
            wraplength=300,
        )
        lbl_subtitle.pack(anchor="w")
        self._lang_reg.append((lbl_subtitle, "login_subtitle", {}))

        # ── Botón de idioma (esquina superior derecha) ────────────────────────
        LanguageToggleButton(
            top,
            text_color=PALETTE["TEXT"],
            border_color=PALETTE["BORDER"],
            hover_color=PALETTE["BORDER"],
        ).place(in_=hero, relx=0.965, rely=0.75, anchor="e")

        mode = getattr(self.controller, "_mode", "light")
        theme_icon = "moon" if mode == "light" else "sun"
        self._theme_icon = get_icon(theme_icon, size=22, color=PALETTE["TEXT"])
        ctk.CTkButton(
            top,
            text="",
            image=self._theme_icon,
            width=44,
            height=44,
            fg_color=PALETTE["BG"],
            hover_color=PALETTE["BORDER"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            corner_radius=12,
            command=self.controller.toggle_theme,
        ).place(in_=hero, relx=0.965, rely=0.20, anchor="e")

        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            corner_radius=26,
            border_width=1,
            border_color=PALETTE["BORDER"],
            width=434,
            height=540,
        )
        card.place(relx=0.5, rely=0.61, anchor="center")
        card.pack_propagate(False)

        ctk.CTkFrame(
            card,
            fg_color=PALETTE["ACCENT"],
            corner_radius=4,
            height=5,
            width=86,
        ).pack(pady=(18, 14))

        lbl_hello = ctk.CTkLabel(
            card,
            text=t("login_hello"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        )
        lbl_hello.pack()
        self._lang_reg.append((lbl_hello, "login_hello", {}))

        lbl_desc = ctk.CTkLabel(
            card,
            text=t("login_description"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
            wraplength=340,
            justify="center",
        )
        lbl_desc.pack(pady=(8, 18))
        self._lang_reg.append((lbl_desc, "login_description", {}))

        form = ctk.CTkFrame(
            card,
            fg_color=PALETTE["BG"],
            corner_radius=16,
            border_width=1,
            border_color=PALETTE["BORDER"],
        )
        form.pack(fill="x", padx=24, pady=(0, 14))

        input_font = ctk.CTkFont(size=16, weight="normal")

        lbl_mat = ctk.CTkLabel(
            form,
            text=t("login_matricula"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        )
        lbl_mat.pack(anchor="w", padx=14, pady=(12, 0))
        self._lang_reg.append((lbl_mat, "login_matricula", {}))

        self._user_icon = get_icon("user", size=17, color=PALETTE["TEXT"])
        matricula_row = self._build_icon_input(form, self._user_icon, pady=(4, 8))

        self.entry_matricula = ctk.CTkEntry(
            matricula_row,
            textvariable=self._matricula_var,
            font=input_font,
            fg_color=PALETTE["CARD"],
            border_color=PALETTE["BORDER"],
            border_width=0,
            text_color=PALETTE["TEXT"],
            placeholder_text_color=PALETTE["MUTED"],
            placeholder_text=t("login_placeholder_mat"),
            height=38,
        )
        self.entry_matricula.grid(row=0, column=2, sticky="nsew", padx=(8, 8), pady=3)

        lbl_pin_label = ctk.CTkLabel(
            form,
            text=t("login_pin"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        )
        lbl_pin_label.pack(anchor="w", padx=14, pady=(4, 0))
        self._lang_reg.append((lbl_pin_label, "login_pin", {}))

        self._lock_icon = get_icon("lock", size=18, color=PALETTE["TEXT"])
        pin_row = self._build_icon_input(form, self._lock_icon, pady=(4, 12))

        self.entry_pin = ctk.CTkEntry(
            pin_row,
            textvariable=self._pin_var,
            show="*",
            font=input_font,
            fg_color=PALETTE["CARD"],
            border_color=PALETTE["BORDER"],
            border_width=0,
            text_color=PALETTE["TEXT"],
            placeholder_text_color=PALETTE["MUTED"],
            placeholder_text="••••",
            height=38,
        )
        self.entry_pin.grid(row=0, column=2, sticky="nsew", padx=(8, 8), pady=3)

        self._eye_closed_icon = get_icon("eye-off", size=16, color=PALETTE["TEXT"])
        self._eye_open_icon = get_icon("eye", size=16, color=PALETTE["TEXT"])
        self._pin_toggle = ctk.CTkButton(
            pin_row,
            text="",
            image=self._eye_closed_icon,
            width=38,
            height=32,
            fg_color=PALETTE["BG"],
            hover_color=PALETTE["BORDER"],
            corner_radius=10,
            command=self._toggle_pin_visibility,
        )
        self._pin_toggle.grid(row=0, column=3, padx=(0, 8), pady=6)

        self.lbl_error = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["DANGER"],
            fg_color="transparent",
        )
        self.lbl_error.pack(pady=(2, 8))

        btn_enter = ctk.CTkButton(
            card,
            text=t("login_enter_btn"),
            font=ctk.CTkFont(size=17, weight="bold"),
            fg_color=PALETTE["ACCENT"],
            hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"],
            height=56,
            corner_radius=16,
            command=self._login,
        )
        btn_enter.pack(fill="x", padx=24, pady=(4, 8))
        self._lang_reg.append((btn_enter, "login_enter_btn", {}))

        lbl_note = ctk.CTkLabel(
            card,
            text=t("login_note"),
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            wraplength=320,
            justify="center",
        )
        lbl_note.pack(pady=(0, 4))
        self._lang_reg.append((lbl_note, "login_note", {}))

        self.entry_matricula.bind("<Return>", lambda _e: self._login())
        self.entry_pin.bind("<Return>", lambda _e: self._login())

    def _build_icon_input(
        self,
        parent: ctk.CTkFrame,
        icon: ctk.CTkImage,
        pady: tuple[int, int],
    ) -> ctk.CTkFrame:
        """Input de una sola pieza: icono interno + entrada sin doble borde."""
        row = ctk.CTkFrame(
            parent,
            fg_color=PALETTE["CARD"],
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["BORDER"],
            height=50,
        )
        row.pack(fill="x", padx=10, pady=pady)
        row.pack_propagate(False)
        row.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            row,
            text="",
            image=icon,
            width=28,
            height=28,
            fg_color="transparent",
        ).grid(row=0, column=0, padx=(10, 6), pady=6)

        ctk.CTkFrame(
            row,
            fg_color=PALETTE["TEXT"],
            width=2,
            height=20,
        ).grid(row=0, column=1, padx=(0, 4), pady=10)

        return row

    def _toggle_pin_visibility(self) -> None:
        visible = not self._show_pin_var.get()
        self._show_pin_var.set(visible)
        self.entry_pin.configure(show="" if visible else "*")
        self._pin_toggle.configure(image=self._eye_open_icon if visible else self._eye_closed_icon)

    def _login(self) -> None:
        matricula = self._matricula_var.get().strip()
        pin = self._pin_var.get().strip()

        if not matricula or not pin:
            self.lbl_error.configure(text=t("login_err_empty"))
            return

        user = authenticate_admin_user(matricula, pin)
        if not user:
            self.lbl_error.configure(text=t("login_err_invalid"))
            return

        set_current_user(user)
        self._pin_var.set("")
        self._show_pin_var.set(False)
        self.entry_pin.configure(show="*")
        self._pin_toggle.configure(image=self._eye_closed_icon)
        self.lbl_error.configure(text="")
        self.controller.on_login_success()
