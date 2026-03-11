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
