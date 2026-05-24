"""
LockerApp – ventana raíz CustomTkinter para la pantalla física (480×800 px).

Gestiona la navegación entre pantallas sin abrir ventanas nuevas:
simplemente hace tkraise() sobre el CTkFrame activo.

    standby_screen  →  scanning_screen  →  user_display
         ↑_________________________↑_______________|

Modo kiosco:
    Activado con UI_CONFIG["kiosk_mode"] = True en config.py.
    - Sin barra de título (overrideredirect).
    - La ventana cubre toda la pantalla (posición 0,0).
    - Alt+F4 y el botón ✕ del admin abren un diálogo de confirmación.

Uso desde main.py (--mode locker):
    from ui.app import LockerApp
    LockerApp().mainloop()
"""

import os
import customtkinter as ctk
from config import UI_CONFIG

_THEME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "School.json")

ctk.set_appearance_mode("light")
ctk.set_default_color_theme(_THEME)


class LockerApp(ctk.CTk):
    """Ventana raíz del locker físico — soporta modo kiosco."""

    WIDTH  = UI_CONFIG.get("width",  480)
    HEIGHT = UI_CONFIG.get("height", 800)

    def __init__(self) -> None:
        super().__init__()

        # Ocultar mientras se configura para evitar ventana inicial miniatura.
        self.withdraw()

        self._mode = "light"
        self._admin_frames_built = False
        self._kiosk_mode: bool = UI_CONFIG.get("kiosk_mode", False)

        # Preparar GPIO de switches de puerta desde el arranque.
        try:
            from core.door_switch_controller import get_door_switch_controller
            get_door_switch_controller().ensure_setup()
        except Exception:
            pass

        # ── Configuración de ventana ──────────────────────────────────────────
        self.title("Smart Locker")
        self.resizable(False, False)

        if self._kiosk_mode:
            # IMPORTANTE: NO usar overrideredirect(True) bajo XWayland/Labwc.
            # override-redirect excluye la ventana de la cadena de foco del
            # compositor Wayland → teclado y touch dejan de funcionar al arrancar.
            # attributes("-fullscreen") usa _NET_WM_STATE_FULLSCREEN, que Labwc
            # maneja correctamente y enruta todos los eventos de input.
            # Impedir cierre por el WM
            self.protocol("WM_DELETE_WINDOW", lambda: None)
            # Evitar que Escape salga del fullscreen (algunas compositors lo hacen)
            self.bind_all("<Escape>", lambda e: None)
            # Capturar foco después de que el compositor procese la ventana.
            # 800 ms de margen para que XWayland registre la ventana fullscreen.
            self.after(800, self._kiosk_grab_focus)
        else:
            self.geometry(f"{self.WIDTH}x{self.HEIGHT}")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Registrar pantallas del locker ────────────────────────────────────
        from ui.locker_screen.standby_screen  import StandbyScreen
        from ui.locker_screen.scanning_screen import ScanningScreen
        from ui.locker_screen.user_display    import UserDisplayScreen

        self._frames: dict[type, ctk.CTkFrame] = {}
        for FrameClass in (StandbyScreen, ScanningScreen, UserDisplayScreen):
            frame = FrameClass(parent=self, controller=self)
            self._frames[FrameClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(StandbyScreen)

        # ── Badge de locker abierto (flota sobre todas las pantallas) ─────────
        self._badge_blink_job = None
        self._badge_poll_job = None
        self._badge_frame = ctk.CTkFrame(
            self,
            fg_color="#F3C94A",
            corner_radius=0,
            border_width=0,
        )
        self._badge_label = ctk.CTkLabel(
            self._badge_frame,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#4A3B00",
            fg_color="transparent",
            wraplength=210,
            justify="left",
        )
        self._badge_label.pack(padx=10, pady=7)

        # Alt+F4: siempre interceptado internamente (con kiosco abre confirmación,
        # sin kiosco cierra normalmente a través del diálogo igualmente)
        self.bind_all("<Alt-F4>", self._on_kiosk_exit_key)

        # Mostrar ventana ya configurada (evita el primer flash en miniatura).
        self.after(0, self._reveal_window)

    # ── Navegación ────────────────────────────────────────────────────────────

    def show_frame(self, frame_class: type) -> None:
        """Trae al frente la pantalla indicada y llama on_show() si existe."""
        for frame in self._frames.values():
            if frame.winfo_ismapped():
                if hasattr(frame, "on_hide"):
                    frame.on_hide()
                break

        frame = self._frames[frame_class]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    # ── Badge de locker abierto ───────────────────────────────────────────────

    def show_open_locker_badge(self) -> None:
        """Muestra/actualiza el badge de locker sin cerrar. Seguro llamar varias veces."""
        self._badge_update_text()
        if self._badge_blink_job is None:
            self._badge_blink(visible=True)
        if self._badge_poll_job is None:
            self._badge_poll_job = self.after(1000, self._badge_poll)

    def _badge_update_text(self) -> None:
        from ui.locker_screen.door_state import get_open_lockers
        from ui.i18n import t
        ids = sorted(get_open_lockers())
        id_str = ", ".join(str(i) for i in ids)
        self._badge_label.configure(text=f'{t("door.banner_prefix")} {id_str}')

    def _badge_blink(self, visible: bool = True) -> None:
        if visible:
            self._badge_frame.place(x=8, y=8)
            self._badge_frame.lift()
        else:
            self._badge_frame.place_forget()
        self._badge_blink_job = self.after(500, self._badge_blink, not visible)

    def _badge_poll(self) -> None:
        from ui.locker_screen.door_state import get_open_lockers, remove_open_locker, has_open_lockers
        try:
            from core.door_switch_controller import get_door_switch_controller
            controller = get_door_switch_controller()
            if controller.is_available():
                for lid in list(get_open_lockers()):
                    if controller.read_state(lid) is True:
                        remove_open_locker(lid)
        except Exception:
            pass
        if has_open_lockers():
            self._badge_update_text()
            self._badge_poll_job = self.after(500, self._badge_poll)
        else:
            self._badge_stop()

    def _badge_stop(self) -> None:
        if self._badge_blink_job:
            self.after_cancel(self._badge_blink_job)
            self._badge_blink_job = None
        if self._badge_poll_job:
            self.after_cancel(self._badge_poll_job)
            self._badge_poll_job = None
        self._badge_frame.place_forget()

    # ── Admin bridge ──────────────────────────────────────────────────────────

    def ensure_admin_frames(self) -> None:
        """Registra las pantallas del panel admin la primera vez que se necesitan."""
        if self._admin_frames_built:
            return
        from ui.admin.login_screen      import LoginScreen
        from ui.admin.dashboard         import DashboardScreen
        from ui.admin.users_catalog     import UsersCatalogScreen
        from ui.admin.lockers_catalog   import LockersCatalogScreen
        from ui.admin.areas_catalog     import AreasCatalogScreen
        from ui.admin.access_history    import AccessHistoryScreen
        from ui.admin.locker_assignment import LockerAssignmentScreen
        from ui.admin.register_user     import RegisterUserScreen
        for FrameClass in (
            LoginScreen, DashboardScreen, UsersCatalogScreen,
            LockersCatalogScreen, AreasCatalogScreen,
            AccessHistoryScreen, LockerAssignmentScreen, RegisterUserScreen,
        ):
            frame = FrameClass(parent=self, controller=self)
            self._frames[FrameClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        self._admin_frames_built = True

    def on_login_success(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.show_frame(DashboardScreen)

    def logout(self) -> None:
        from auth.session import clear_session
        from ui.locker_screen.standby_screen import StandbyScreen
        clear_session()
        self.show_frame(StandbyScreen)

    def show_user(self, user_data: dict) -> None:
        from ui.locker_screen.scanning_screen import ScanningScreen
        self._frames[ScanningScreen].on_face_match(user_data)

    # ── Tema / Idioma ─────────────────────────────────────────────────────────

    def toggle_theme(self) -> None:
        from ui.admin_app import PALETTE, LIGHT_PALETTE, DARK_PALETTE, _ICON_CACHE
        if self._mode == "light":
            self._mode = "dark"
            PALETTE.update(DARK_PALETTE)
        else:
            self._mode = "light"
            PALETTE.update(LIGHT_PALETTE)
        _ICON_CACHE.clear()
        if self._admin_frames_built:
            self._rebuild_admin_frames()

    def toggle_lang(self) -> None:
        from ui.i18n import toggle as i18n_toggle
        i18n_toggle()
        self._rebuild_all()

    # ── Veil (cortina de transición para evitar flicker) ─────────────────────

    def _create_veil(self, text: str = "", icon: str = "") -> ctk.CTkFrame:
        """Frame opaco que cubre la ventana mientras se reconstruyen las pantallas."""
        from ui.admin_app import PALETTE
        bg  = PALETTE["BG"]
        txt = PALETTE["TEXT"]
        mut = PALETTE["MUTED"]

        veil = ctk.CTkFrame(self, fg_color=bg, corner_radius=0)
        veil.place(x=0, y=0, relwidth=1, relheight=1)
        veil.lift()

        if icon or text:
            inner = ctk.CTkFrame(veil, fg_color="transparent")
            inner.place(relx=0.5, rely=0.5, anchor="center")
            if icon:
                ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=52),
                             fg_color="transparent", text_color=txt).pack(pady=(0, 12))
            if text:
                ctk.CTkLabel(inner, text=text, font=ctk.CTkFont(size=18, weight="bold"),
                             fg_color="transparent", text_color=txt).pack()
            ctk.CTkLabel(inner, text="Por favor espera…", font=ctk.CTkFont(size=13),
                         fg_color="transparent", text_color=mut).pack(pady=(6, 0))
        return veil

    # ── Rebuild admin ─────────────────────────────────────────────────────────

    def _rebuild_admin_frames(self) -> None:
        going_dark = self._mode == "dark"
        veil = self._create_veil(
            text="Cambiando a modo oscuro…" if going_dark else "Cambiando a modo claro…",
            icon="🌙" if going_dark else "☀️",
        )
        self.after(30, lambda: self._do_rebuild_admin(veil))

    def _do_rebuild_admin(self, veil: ctk.CTkFrame) -> None:
        from ui.admin.login_screen      import LoginScreen
        from ui.admin.dashboard         import DashboardScreen
        from ui.admin.users_catalog     import UsersCatalogScreen
        from ui.admin.lockers_catalog   import LockersCatalogScreen
        from ui.admin.areas_catalog     import AreasCatalogScreen
        from ui.admin.access_history    import AccessHistoryScreen
        from ui.admin.locker_assignment import LockerAssignmentScreen
        from ui.admin.register_user     import RegisterUserScreen
        from auth.session import is_authenticated

        admin_classes = (
            LoginScreen, DashboardScreen, UsersCatalogScreen,
            LockersCatalogScreen, AreasCatalogScreen,
            AccessHistoryScreen, LockerAssignmentScreen, RegisterUserScreen,
        )
        try:
            ctk.set_appearance_mode("dark" if self._mode == "dark" else "light")
            for cls in admin_classes:
                if cls in self._frames:
                    self._frames[cls].destroy()
                    del self._frames[cls]
            self._admin_frames_built = False
            self.ensure_admin_frames()
            if is_authenticated():
                self.show_frame(DashboardScreen)
            else:
                self.show_frame(LoginScreen)
        finally:
            if veil.winfo_exists():
                veil.lift()
                veil.destroy()

    # ── Rebuild all (cambio de idioma) ────────────────────────────────────────

    def _rebuild_all(self) -> None:
        veil = self._create_veil()
        self.after(30, lambda: self._do_rebuild_all(veil))

    def _do_rebuild_all(self, veil: ctk.CTkFrame) -> None:
        from ui.locker_screen.standby_screen  import StandbyScreen
        from ui.locker_screen.scanning_screen import ScanningScreen
        from ui.locker_screen.user_display    import UserDisplayScreen
        from auth.session import is_authenticated
        try:
            for cls in (StandbyScreen, ScanningScreen, UserDisplayScreen):
                if cls in self._frames:
                    self._frames[cls].destroy()
                    del self._frames[cls]
            for FrameClass in (StandbyScreen, ScanningScreen, UserDisplayScreen):
                frame = FrameClass(parent=self, controller=self)
                self._frames[FrameClass] = frame
                frame.grid(row=0, column=0, sticky="nsew")
            if self._admin_frames_built:
                from ui.admin.login_screen      import LoginScreen
                from ui.admin.dashboard         import DashboardScreen
                from ui.admin.users_catalog     import UsersCatalogScreen
                from ui.admin.lockers_catalog   import LockersCatalogScreen
                from ui.admin.areas_catalog     import AreasCatalogScreen
                from ui.admin.access_history    import AccessHistoryScreen
                from ui.admin.locker_assignment import LockerAssignmentScreen
                from ui.admin.register_user     import RegisterUserScreen
                admin_cls = (
                    LoginScreen, DashboardScreen, UsersCatalogScreen,
                    LockersCatalogScreen, AreasCatalogScreen,
                    AccessHistoryScreen, LockerAssignmentScreen, RegisterUserScreen,
                )
                for cls in admin_cls:
                    if cls in self._frames:
                        self._frames[cls].destroy()
                        del self._frames[cls]
                self._admin_frames_built = False
                self.ensure_admin_frames()
                if is_authenticated():
                    self.show_frame(DashboardScreen)
                else:
                    self.show_frame(LoginScreen)
            else:
                self.show_frame(StandbyScreen)
        finally:
            if veil.winfo_exists():
                veil.lift()
                veil.destroy()

    # ── Salida del modo kiosco ────────────────────────────────────────────────

    def _kiosk_grab_focus(self) -> None:
        """
        Captura el foco de input para la ventana kiosco.
        Necesario bajo XWayland/Labwc: sin esto el teclado y touch pueden
        no responder cuando el sistema arranca desde autostart.
        Se reintenta cada segundo hasta conseguir foco (máx 10 intentos).
        """
        try:
            self.focus_force()
            self.lift()
            # Verificar que realmente tenemos foco
            if self.focus_get() is None:
                # Reintentar en 1 segundo
                if not hasattr(self, "_focus_attempts"):
                    self._focus_attempts = 0
                self._focus_attempts += 1
                if self._focus_attempts < 10:
                    self.after(1000, self._kiosk_grab_focus)
            else:
                self._focus_attempts = 0
        except Exception:
            pass

    def _reveal_window(self) -> None:
        """Hace visible la ventana ya configurada y fuerza fullscreen si aplica."""
        try:
            if self._kiosk_mode:
                self.attributes("-fullscreen", True)
        except Exception:
            pass
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _on_kiosk_exit_key(self, event=None) -> None:
        """Alt+F4 abre el diálogo de confirmación de salida."""
        self.confirm_kiosk_exit()

    def _exit_kiosk(self) -> None:
        """Cierra la app limpiamente para evitar ventanas fantasma."""
        try:
            from ui.locker_screen.scanning_screen import ScanningScreen
            frame = self._frames.get(ScanningScreen)
            if frame and hasattr(frame, "on_hide"):
                frame.on_hide()
        except Exception:
            pass

        try:
            self.attributes("-fullscreen", False)
        except Exception:
            pass

        self.destroy()

    def confirm_kiosk_exit(self) -> None:
        """Diálogo modal: confirma antes de salir del modo kiosco."""
        from ui.admin_app import PALETTE

        # Fondo semitransparente oscuro
        overlay = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()

        card = ctk.CTkFrame(
            overlay,
            fg_color=PALETTE["CARD"],
            corner_radius=20,
            border_width=1,
            border_color=PALETTE["BORDER"],
            width=360,
            height=230,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.86)

        ctk.CTkLabel(
            inner,
            text="⚠️  Salir del modo kiosco",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            inner,
            text="Regresarás al escritorio\nde la Raspberry Pi.",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            justify="center",
        ).pack(pady=(0, 20))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(
            btn_row,
            text="Cancelar",
            width=140, height=46,
            font=ctk.CTkFont(size=14),
            fg_color=PALETTE["BG"],
            hover_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            corner_radius=12,
            command=overlay.destroy,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="Salir",
            width=140, height=46,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=PALETTE["DANGER"],
            hover_color="#8B1A1A",
            text_color="#FFFFFF",
            corner_radius=12,
            command=self._exit_kiosk,   # cierra la app sin dejar ventana residual
        ).pack(side="left")
