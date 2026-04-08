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

        ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            width=300,
            height=300,
            corner_radius=150,
            border_width=0,
        ).place(relx=0.02, rely=0.12, anchor="w")

        ctk.CTkFrame(
            self,
            fg_color=PALETTE["BORDER"],
            width=210,
            height=210,
            corner_radius=105,
            border_width=0,
        ).place(relx=0.98, rely=0.92, anchor="e")

        top = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=0, height=92)
        top.pack(fill="x")
        top.pack_propagate(False)

        top_inner = ctk.CTkFrame(top, fg_color="transparent")
        top_inner.pack(fill="both", expand=True, padx=18, pady=(10, 10))

        ctk.CTkLabel(
            top_inner,
            text="Smart Locker",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETTE["ACCENT"],
            fg_color="transparent",
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_inner,
            text="Panel administrativo",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(anchor="w")

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
        ).place(relx=0.94, rely=0.5, anchor="e")

        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["CARD"],
            corner_radius=24,
            border_width=1,
            border_color=PALETTE["BORDER"],
            width=430,
            height=548,
        )
        card.place(relx=0.5, rely=0.57, anchor="center")
        card.pack_propagate(False)

        ctk.CTkFrame(
            card,
            fg_color=PALETTE["ACCENT"],
            corner_radius=4,
            height=5,
            width=86,
        ).pack(pady=(18, 14))

        ctk.CTkLabel(
            card,
            text="Acceso administrativo",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack()

        ctk.CTkLabel(
            card,
            text="Ingresa para gestionar usuarios, catálogos y asignaciones.",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
            wraplength=340,
            justify="center",
        ).pack(pady=(8, 18))

        form = ctk.CTkFrame(
            card,
            fg_color=PALETTE["BG"],
            corner_radius=18,
            border_width=1,
            border_color=PALETTE["BORDER"],
        )
        form.pack(fill="x", padx=24, pady=(0, 14))

        input_font = ctk.CTkFont(size=16, weight="normal")

        ctk.CTkLabel(
            form,
            text="Matrícula",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=14, pady=(12, 0))

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
            placeholder_text="Ej. 20260001",
            height=38,
        )
        self.entry_matricula.grid(row=0, column=2, sticky="nsew", padx=(8, 8), pady=3)

        ctk.CTkLabel(
            form,
            text="PIN",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=14, pady=(4, 0))

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
            height=58,
            corner_radius=16,
            command=self._login,
        ).pack(fill="x", padx=24, pady=(4, 8))

        ctk.CTkLabel(
            card,
            text="La sesión se valida en la base de datos local.",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            wraplength=320,
            justify="center",
        ).pack(pady=(0, 4))

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
