"""Pantalla de login para el panel administrativo."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from auth.session import authenticate_admin_user, set_current_user
from ui.admin_app import PALETTE, get_icon


class LoginScreen(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller

        self._matricula_var = tk.StringVar()
        self._pin_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=0, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Iniciar sesión",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
        ).pack(side="left", padx=20, pady=16)

        mode = getattr(self.controller, "_mode", "light")
        theme_icon = "moon" if mode == "light" else "sun"
        self._theme_icon = get_icon(theme_icon, size=22, color=PALETTE["TEXT"])
        ctk.CTkButton(
            header,
            text="",
            image=self._theme_icon,
            width=48,
            height=48,
            fg_color="transparent",
            hover_color=PALETTE["BORDER"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            command=self.controller.toggle_theme,
        ).pack(side="right", padx=12, pady=12)

        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            corner_radius=18,
            border_width=1,
            border_color=PALETTE["BORDER"],
            width=430,
            height=520,
        )
        card.place(relx=0.5, rely=0.58, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(
            card,
            text="Smart Locker",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
        ).pack(pady=(28, 2))

        ctk.CTkLabel(
            card,
            text="Iniciar sesión administrativa",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(pady=(0, 18))

        ctk.CTkLabel(
            card,
            text="Acceso",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=28)

        fields = ctk.CTkFrame(card, fg_color=PALETTE["BG"], corner_radius=14, border_width=1, border_color=PALETTE["BORDER"])
        fields.pack(fill="x", padx=28, pady=(8, 14))

        ctk.CTkLabel(
            fields,
            text="Matrícula",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=14, pady=(12, 0))

        input_font = ctk.CTkFont(size=16, weight="normal")

        self._user_icon = get_icon("user", size=17, color=PALETTE["TEXT"])
        matricula_row = self._build_icon_input(fields, self._user_icon, pady=(4, 8))

        self.entry_matricula = ctk.CTkEntry(
            matricula_row,
            textvariable=self._matricula_var,
            font=input_font,
            fg_color=PALETTE["CARD"],
            border_color=PALETTE["BORDER"],
            border_width=0,
            text_color=PALETTE["TEXT"],
            placeholder_text_color=PALETTE["MUTED"],
            placeholder_text="Ej. A01234567",
            height=38,
        )
        self.entry_matricula.grid(row=0, column=2, sticky="nsew", padx=(8, 8), pady=3)

        ctk.CTkLabel(
            fields,
            text="PIN",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=14)

        self._lock_icon = get_icon("lock", size=18, color=PALETTE["TEXT"])
        pin_row = self._build_icon_input(fields, self._lock_icon, pady=(4, 12))

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

        self.lbl_error = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["DANGER"],
            fg_color="transparent",
        )
        self.lbl_error.pack(pady=(2, 8))

        ctk.CTkButton(
            card,
            text="Ingresar",
            font=ctk.CTkFont(size=17, weight="bold"),
            fg_color=PALETTE["ACCENT"],
            hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"],
            height=56,
            corner_radius=14,
            command=self._login,
        ).pack(fill="x", padx=28, pady=(4, 6))

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
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["BORDER"],
            height=48,
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

    def _login(self) -> None:
        matricula = self._matricula_var.get().strip()
        pin = self._pin_var.get().strip()

        if not matricula or not pin:
            self.lbl_error.configure(text="Ingresa matrícula y PIN")
            return

        user = authenticate_admin_user(matricula, pin)
        if not user:
            self.lbl_error.configure(text="Credenciales inválidas o cuenta inactiva")
            return

        set_current_user(user)
        self._pin_var.set("")
        self.lbl_error.configure(text="")
        self.controller.on_login_success()
