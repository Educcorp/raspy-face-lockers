"""Pantalla de login para el panel administrativo."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from auth.session import authenticate_admin_user, set_current_user
from ui.admin_app import PALETTE


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

        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            corner_radius=18,
            border_width=1,
            border_color=PALETTE["BORDER"],
            width=420,
            height=460,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
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
            font=ctk.CTkFont(size=14),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(pady=(0, 18))

        ctk.CTkLabel(
            card,
            text="Matrícula",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(anchor="w", padx=28)

        self.entry_matricula = ctk.CTkEntry(
            card,
            textvariable=self._matricula_var,
            font=ctk.CTkFont(size=16),
            fg_color=PALETTE["BG"],
            border_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            height=50,
        )
        self.entry_matricula.pack(fill="x", padx=28, pady=(4, 12))

        ctk.CTkLabel(
            card,
            text="PIN",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(anchor="w", padx=28)

        self.entry_pin = ctk.CTkEntry(
            card,
            textvariable=self._pin_var,
            show="*",
            font=ctk.CTkFont(size=16),
            fg_color=PALETTE["BG"],
            border_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            height=50,
        )
        self.entry_pin.pack(fill="x", padx=28, pady=(4, 8))

        self.lbl_error = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["DANGER"],
            fg_color="transparent",
        )
        self.lbl_error.pack(pady=(4, 6))

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
        ).pack(fill="x", padx=28, pady=(10, 4))

        ctk.CTkLabel(
            card,
            text="Tip: también puedes iniciar con SMART_LOCKER_ROLE",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(pady=(10, 0))

        self.entry_matricula.bind("<Return>", lambda _e: self._login())
        self.entry_pin.bind("<Return>", lambda _e: self._login())

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
