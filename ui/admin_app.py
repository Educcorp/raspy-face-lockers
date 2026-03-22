"""
AdminApp – ventana raíz del panel de super-administración.

Resolución fija: 480×800 px  (igual que la pantalla física del locker).
Toda la navegación es interna (tkraise), sin abrir ventanas nuevas.
Todo está diseñado para ser touchable (botones ≥ 52 px de alto).

Paleta de colores (modo claro – locker-style):
    BG        #F5F0EB   Fondo crema claro escolar
    CARD      #EDE8E2   Cards
    ACCENT    #5B8C5A   Verde pizarrón (igual que locker)
    TEXT      #3D3D3D   Texto oscuro legible
    MUTED     #8C8279   Texto secundario cálido
    BORDER    #CCC5BC   Bordes suaves

Paleta de colores (modo oscuro):
    BG        #0c112f   Fondo principal
    CARD      #151d3b   Cards / elementos elevados
    ACCENT    #33a8a3   Verde-azulado principal
    TEXT      #c7cfd5   Texto principal
    MUTED     #6b7a8a   Texto secundario
    BORDER    #1e2d4a   Bordes sutiles
"""

import os
import customtkinter as ctk
from auth.session import (
    clear_session,
    get_current_role_label,
    has_env_role_override,
    initialize_session_from_env,
    is_authenticated,
)

# ── Tema base (mismo que la pantalla física del locker) ───────────────────────
_THEME = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "School.json"
)
ctk.set_default_color_theme(_THEME)

# ── Paletas ───────────────────────────────────────────────────────────────────
LIGHT_PALETTE = {
    "BG":          "#F5F0EB",
    "CARD":        "#EDE8E2",
    "ACCENT":      "#5B8C5A",
    "ACCENT_HOVER":"#4A7A49",
    "DANGER":      "#c0392b",
    "WARN":        "#d4a034",
    "TEXT":        "#3D3D3D",
    "MUTED":       "#8C8279",
    "BORDER":      "#CCC5BC",
    "WHITE":       "#ffffff",
    "SUCCESS":     "#5B8C5A",
}

DARK_PALETTE = {
    "BG":          "#0c112f",
    "CARD":        "#151d3b",
    "ACCENT":      "#33a8a3",
    "ACCENT_HOVER":"#268f8a",
    "DANGER":      "#c0392b",
    "WARN":        "#d4a034",
    "TEXT":        "#c7cfd5",
    "MUTED":       "#6b7a8a",
    "BORDER":      "#1e2d4a",
    "WHITE":       "#ffffff",
    "SUCCESS":     "#27ae60",
}

# ── Paleta activa (mutable – todas las pantallas la referencian) ──────────────
PALETTE: dict = dict(LIGHT_PALETTE)
ctk.set_appearance_mode("light")


class AdminApp(ctk.CTk):
    """
    Ventana raíz del panel de administración.
    Fija en 480×800 px. Gestiona navegación entre pantallas sin sub-ventanas.
    Soporta alternancia de tema claro/oscuro vía toggle_theme().
    """

    WIDTH  = 480
    HEIGHT = 800

    def __init__(self) -> None:
        super().__init__()
        self._mode = "light"
        self._bypass_login = has_env_role_override()

        if self._bypass_login:
            initialize_session_from_env()
        else:
            clear_session()

        self.title(f"Smart Locker – {get_current_role_label()}")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["BG"])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._frames: dict[type, ctk.CTkFrame] = {}
        self._build_frames()

        from ui.admin.dashboard import DashboardScreen
        from ui.admin.login_screen import LoginScreen
        self.show_frame(DashboardScreen if self._bypass_login else LoginScreen)

    # ── Construcción / reconstrucción de pantallas ────────────────────────────

    def _build_frames(self) -> None:
        """Instancia todas las pantallas y las apila en la cuadrícula."""
        from ui.admin.dashboard       import DashboardScreen
        from ui.admin.login_screen    import LoginScreen
        from ui.admin.users_catalog   import UsersCatalogScreen
        from ui.admin.lockers_catalog import LockersCatalogScreen
        from ui.admin.areas_catalog   import AreasCatalogScreen
        from ui.admin.locker_assignment import LockerAssignmentScreen
        from ui.admin.register_user   import RegisterUserScreen

        for FrameClass in (
            LoginScreen,
            DashboardScreen,
            UsersCatalogScreen,
            LockersCatalogScreen,
            AreasCatalogScreen,
            LockerAssignmentScreen,
            RegisterUserScreen,
        ):
            frame = FrameClass(parent=self, controller=self)
            self._frames[FrameClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")

    # ── Tema ──────────────────────────────────────────────────────────────────

    def toggle_theme(self) -> None:
        """Alterna entre modo claro (locker-style) y modo oscuro."""
        if self._mode == "light":
            self._mode = "dark"
            ctk.set_appearance_mode("dark")
            PALETTE.update(DARK_PALETTE)
        else:
            self._mode = "light"
            ctk.set_appearance_mode("light")
            PALETTE.update(LIGHT_PALETTE)
        self._rebuild_frames()

    def _rebuild_frames(self) -> None:
        """Destruye todos los frames y los recrea con la paleta actualizada."""
        for frame in list(self._frames.values()):
            frame.destroy()
        self._frames.clear()
        self.configure(fg_color=PALETTE["BG"])
        self.title(f"Smart Locker – {get_current_role_label()}")
        self._build_frames()
        from ui.admin.dashboard import DashboardScreen
        self.show_frame(DashboardScreen)

    def on_login_success(self) -> None:
        """Se invoca cuando LoginScreen autentica al usuario en BD."""
        self._rebuild_frames()

    # ── Navegación ────────────────────────────────────────────────────────────

    def show_frame(self, frame_class: type, **kwargs) -> None:
        """Trae al frente la pantalla indicada. Llama on_hide / on_show."""
        from ui.admin.login_screen import LoginScreen

        if frame_class is not LoginScreen and not is_authenticated():
            frame_class = LoginScreen

        for frame in self._frames.values():
            if frame.winfo_ismapped():
                if hasattr(frame, "on_hide"):
                    frame.on_hide()
                break

        frame = self._frames[frame_class]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show(**kwargs)
