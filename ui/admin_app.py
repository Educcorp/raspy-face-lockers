"""
AdminApp – ventana raíz del panel de super-administración.

Resolución fija: 480×800 px  (igual que la pantalla física del locker).
Toda la navegación es interna (tkraise), sin abrir ventanas nuevas.
Todo está diseñado para ser touchable (botones ≥ 52 px de alto).

Paleta de colores (dark mode):
    BG        #0c112f   Fondo principal
    CARD      #151d3b   Cards / elementos elevados
    ACCENT    #33a8a3   Verde-azulado principal
    DANGER    #c0392b   Rojo para borrar / alertas
    TEXT      #c7cfd5   Texto principal
    MUTED     #6b7a8a   Texto secundario
    BORDER    #1e2d4a   Bordes sutiles
"""

import os
import customtkinter as ctk

# ── Tema ──────────────────────────────────────────────────────────────────────
_THEME = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "Greengage.json"
)
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme(_THEME)

# ── Paleta global accesible por todas las pantallas ───────────────────────────
PALETTE = {
    "BG":     "#0c112f",
    "CARD":   "#151d3b",
    "ACCENT": "#33a8a3",
    "DANGER": "#c0392b",
    "WARN":   "#d4a034",
    "TEXT":   "#c7cfd5",
    "MUTED":  "#6b7a8a",
    "BORDER": "#1e2d4a",
    "WHITE":  "#ffffff",
    "SUCCESS":"#27ae60",
}


class AdminApp(ctk.CTk):
    """
    Ventana raíz del panel de administración.
    Fija en 480×800 px. Gestiona navegación entre pantallas sin sub-ventanas.
    """

    WIDTH  = 480
    HEIGHT = 800

    def __init__(self) -> None:
        super().__init__()

        self.title("Smart Locker – Super Admin")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["BG"])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Importaciones diferidas para evitar ciclos
        from ui.admin.dashboard         import DashboardScreen
        from ui.admin.users_catalog     import UsersCatalogScreen
        from ui.admin.lockers_catalog   import LockersCatalogScreen
        from ui.admin.areas_catalog     import AreasCatalogScreen
        from ui.admin.register_user     import RegisterUserScreen

        self._frames: dict[type, ctk.CTkFrame] = {}
        for FrameClass in (
            DashboardScreen,
            UsersCatalogScreen,
            LockersCatalogScreen,
            AreasCatalogScreen,
            RegisterUserScreen,
        ):
            frame = FrameClass(parent=self, controller=self)
            self._frames[FrameClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Pantalla inicial
        self.show_frame(DashboardScreen)

    # ── Navegación ────────────────────────────────────────────────────────────

    def show_frame(self, frame_class: type, **kwargs) -> None:
        """Trae al frente la pantalla indicada. Llama on_hide / on_show."""
        for frame in self._frames.values():
            if frame.winfo_ismapped():
                if hasattr(frame, "on_hide"):
                    frame.on_hide()
                break

        frame = self._frames[frame_class]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show(**kwargs)
