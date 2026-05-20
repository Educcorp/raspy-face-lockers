"""
LockerApp – ventana raíz CustomTkinter para la pantalla física (800×480 px).

Gestiona la navegación entre pantallas sin abrir ventanas nuevas:
simplemente hace tkraise() sobre el CTkFrame activo.

    standby_screen  →  scanning_screen  →  user_display
         ↑_________________________↑_______________|

Uso desde main.py (--mode locker):
    from ui.app import LockerApp
    LockerApp().mainloop()
"""

import os
import customtkinter as ctk

_THEME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "School.json")

ctk.set_appearance_mode("light")
ctk.set_default_color_theme(_THEME)


class LockerApp(ctk.CTk):
    """
    Ventana raíz del locker físico. Resolución fija 800×480 px.

    Kiosk mode (sin barra de título) se activa descomentando
    overrideredirect(True) — solo en la Raspberry Pi física.
    """

    WIDTH  = 480
    HEIGHT = 800

    def __init__(self) -> None:
        super().__init__()

        self._mode = "light"           # requerido por LoginScreen para el toggle de tema
        self._admin_frames_built = False

        # ── Ventana ───────────────────────────────────────────────────────────
        self.title("Smart Locker")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        # self.overrideredirect(True)   # ← activar en RPi (kiosk sin decoración)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Registrar todas las pantallas ────────────────────────────────────
        # Importaciones diferidas para evitar ciclos de importación
        from ui.locker_screen.standby_screen  import StandbyScreen
        from ui.locker_screen.scanning_screen import ScanningScreen
        from ui.locker_screen.user_display    import UserDisplayScreen

        self._frames: dict[type, ctk.CTkFrame] = {}
        for FrameClass in (StandbyScreen, ScanningScreen, UserDisplayScreen):
            frame = FrameClass(parent=self, controller=self)
            self._frames[FrameClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Pantalla inicial
        self.show_frame(StandbyScreen)

    # ── API de navegación ─────────────────────────────────────────────────────

    def show_frame(self, frame_class: type) -> None:
        """Trae al frente la pantalla indicada y llama on_show() si existe."""
        # Llamar on_hide() a la pantalla que se oculta
        for registered_class, frame in self._frames.items():
            if frame.winfo_ismapped():
                if hasattr(frame, "on_hide"):
                    frame.on_hide()
                break
        
        # Mostrar nueva pantalla y llamar on_show()
        frame = self._frames[frame_class]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    # ── Admin bridge ─────────────────────────────────────────────────────────

    def ensure_admin_frames(self) -> None:
        """Registra las pantallas del panel admin la primera vez que se necesitan."""
        if self._admin_frames_built:
            return
        from ui.admin.login_screen      import LoginScreen
        from ui.admin.dashboard         import DashboardScreen
        from ui.admin.users_catalog     import UsersCatalogScreen
        from ui.admin.lockers_catalog   import LockersCatalogScreen
        from ui.admin.areas_catalog     import AreasCatalogScreen
        from ui.admin.locker_assignment import LockerAssignmentScreen
        from ui.admin.register_user     import RegisterUserScreen
        for FrameClass in (
            LoginScreen, DashboardScreen, UsersCatalogScreen,
            LockersCatalogScreen, AreasCatalogScreen,
            LockerAssignmentScreen, RegisterUserScreen,
        ):
            frame = FrameClass(parent=self, controller=self)
            self._frames[FrameClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        self._admin_frames_built = True

    def toggle_theme(self) -> None:
        """Alterna tema claro/oscuro en el panel admin (las pantallas del locker no cambian)."""
        from ui.admin_app import PALETTE, LIGHT_PALETTE, DARK_PALETTE, _ICON_CACHE
        import customtkinter as ctk_mod
        if self._mode == "light":
            self._mode = "dark"
            ctk_mod.set_appearance_mode("dark")
            PALETTE.update(DARK_PALETTE)
        else:
            self._mode = "light"
            ctk_mod.set_appearance_mode("light")
            PALETTE.update(LIGHT_PALETTE)
        _ICON_CACHE.clear()
        if self._admin_frames_built:
            self._rebuild_admin_frames()

    def toggle_lang(self) -> None:
        """Alterna idioma ES/EN y reconstruye todas las pantallas."""
        from ui.i18n import toggle as i18n_toggle
        i18n_toggle()
        self._rebuild_all()

    def _rebuild_admin_frames(self) -> None:
        """Destruye y recrea solo los frames del panel admin."""
        from ui.admin.login_screen      import LoginScreen
        from ui.admin.dashboard         import DashboardScreen
        from ui.admin.users_catalog     import UsersCatalogScreen
        from ui.admin.lockers_catalog   import LockersCatalogScreen
        from ui.admin.areas_catalog     import AreasCatalogScreen
        from ui.admin.locker_assignment import LockerAssignmentScreen
        from ui.admin.register_user     import RegisterUserScreen
        from auth.session import is_authenticated

        admin_classes = (
            LoginScreen, DashboardScreen, UsersCatalogScreen,
            LockersCatalogScreen, AreasCatalogScreen,
            LockerAssignmentScreen, RegisterUserScreen,
        )
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

    def _rebuild_all(self) -> None:
        """Destruye y recrea todas las pantallas (locker + admin si están construidas)."""
        from ui.locker_screen.standby_screen  import StandbyScreen
        from ui.locker_screen.scanning_screen import ScanningScreen
        from ui.locker_screen.user_display    import UserDisplayScreen
        from auth.session import is_authenticated

        for cls in (StandbyScreen, ScanningScreen, UserDisplayScreen):
            if cls in self._frames:
                self._frames[cls].destroy()
                del self._frames[cls]

        for FrameClass in (StandbyScreen, ScanningScreen, UserDisplayScreen):
            frame = FrameClass(parent=self, controller=self)
            self._frames[FrameClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        if self._admin_frames_built:
            self._rebuild_admin_frames()
        else:
            self.show_frame(StandbyScreen)

    def on_login_success(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.show_frame(DashboardScreen)

    def logout(self) -> None:
        from auth.session import clear_session
        from ui.locker_screen.standby_screen import StandbyScreen
        clear_session()
        self.show_frame(StandbyScreen)

    def show_user(self, user_data: dict) -> None:
        """
        Muestra overlay de éxito en ScanningScreen con los datos del usuario.

        user_data = {
            "nombre":        str,
            "locker_numero": int,
            "fecha":         str,   # formato legible, ej. "07/03/2026 14:32"
        }
        """
        from ui.locker_screen.scanning_screen import ScanningScreen
        screen: ScanningScreen = self._frames[ScanningScreen]
        screen.on_face_match(user_data)
