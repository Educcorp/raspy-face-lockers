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
from PIL import Image, ImageDraw, ImageFont
from auth.session import (
    clear_session,
    get_current_role_label,
    is_authenticated,
)

# ── Tema base (mismo que la pantalla física del locker) ───────────────────────
_THEME = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "School.json"
)
ctk.set_default_color_theme(_THEME)

# ── Paletas ───────────────────────────────────────────────────────────────────
LIGHT_PALETTE = {
    "BG":          "#F4F1EC",
    "CARD":        "#E9E4DE",
    "ACCENT":      "#6E7F63",
    "ACCENT_HOVER":"#5F7155",
    "DANGER":      "#AE655C",
    "WARN":        "#B99662",
    "TEXT":        "#3F3E3B",
    "MUTED":       "#8B847C",
    "BORDER":      "#D2CBC3",
    "WHITE":       "#ffffff",
    "SUCCESS":     "#6E7F63",
}

DARK_PALETTE = {
    "BG":          "#111726",
    "CARD":        "#1A2233",
    "ACCENT":      "#5E8F8B",
    "ACCENT_HOVER":"#4F7D79",
    "DANGER":      "#A86761",
    "WARN":        "#B29463",
    "TEXT":        "#C4CCD3",
    "MUTED":       "#72808F",
    "BORDER":      "#253046",
    "WHITE":       "#ffffff",
    "SUCCESS":     "#5E8F8B",
}

# ── Paleta activa (mutable – todas las pantallas la referencian) ──────────────
PALETTE: dict = dict(LIGHT_PALETTE)
ctk.set_appearance_mode("light")

_ICON_CACHE: dict[tuple[str, int, str], ctk.CTkImage] = {}
_FA_FONT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts", "fa-solid-900.ttf"
)
_FA_GLYPHS = {
    "sun": "\uf185",
    "moon": "\uf186",
    "user": "\uf007",
    "lock": "\uf023",
    "logout": "\uf2f5",
    "eye": "\uf06e",
    "eye-off": "\uf070",
}
_FA_ICON_SCALE = {
    "sun": 0.90,
    "moon": 0.90,
    "user": 0.78,
    "lock": 0.86,
    "logout": 0.86,
    "eye": 0.84,
    "eye-off": 0.84,
}
_FA_ICON_Y_OFFSET = {
    "user": 1,
}


def _icon_canvas(size: int) -> Image.Image:
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def _draw_fontawesome_icon(name: str, size: int, color: str) -> Image.Image | None:
    """Renderiza íconos oficiales de Font Awesome si la fuente está disponible."""
    glyph = _FA_GLYPHS.get(name)
    if not glyph or not os.path.exists(_FA_FONT_PATH):
        return None

    scale = _FA_ICON_SCALE.get(name, 0.88)
    try:
        font = ImageFont.truetype(_FA_FONT_PATH, size=max(10, int(size * scale)))
    except Exception:
        return None

    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), glyph, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1] + _FA_ICON_Y_OFFSET.get(name, 0)
    draw.text((x, y), glyph, font=font, fill=color)
    return img


def _draw_sun(size: int, color: str) -> Image.Image:
    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    cx = cy = size / 2
    core = max(3, int(size * 0.2))
    ray_inner = int(size * 0.36)
    ray_outer = int(size * 0.47)
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1), (0.7, 0.7), (-0.7, 0.7), (-0.7, -0.7), (0.7, -0.7)):
        x0 = cx + dx * ray_inner
        y0 = cy + dy * ray_inner
        x1 = cx + dx * ray_outer
        y1 = cy + dy * ray_outer
        draw.line((x0, y0, x1, y1), fill=color, width=max(1, int(size * 0.1)))
    draw.ellipse((cx - core, cy - core, cx + core, cy + core), outline=color, width=max(2, int(size * 0.1)))
    return img


def _draw_moon(size: int, color: str) -> Image.Image:
    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    r = int(size * 0.34)
    cx = cy = size // 2
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    cut = int(r * 0.82)
    offset = int(size * 0.16)
    draw.ellipse((cx - cut + offset, cy - cut, cx + cut + offset, cy + cut), fill=(0, 0, 0, 0))
    return img


def _draw_user(size: int, color: str) -> Image.Image:
    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    head_r = int(size * 0.18)
    cx = size // 2
    head_y = int(size * 0.32)
    draw.ellipse((cx - head_r, head_y - head_r, cx + head_r, head_y + head_r), outline=color, width=max(2, int(size * 0.1)))
    shoulder_top = int(size * 0.58)
    shoulder_w = int(size * 0.3)
    draw.arc((cx - shoulder_w, shoulder_top - int(size * 0.14), cx + shoulder_w, shoulder_top + int(size * 0.24)), start=200, end=-20, fill=color, width=max(2, int(size * 0.1)))
    return img


def _draw_lock(size: int, color: str) -> Image.Image:
    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    # Cuerpo sólido del candado (más legible en tamaño pequeño).
    body_w = int(size * 0.50)
    body_h = int(size * 0.36)
    x0 = (size - body_w) // 2
    y0 = int(size * 0.50)
    radius = max(2, int(size * 0.10))
    draw.rounded_rectangle((x0, y0, x0 + body_w, y0 + body_h), radius=radius, fill=color)

    # Arco superior del candado.
    stroke = max(2, int(size * 0.11))
    shackle_w = int(size * 0.34)
    shackle_h = int(size * 0.30)
    sx0 = (size - shackle_w) // 2
    sy0 = int(size * 0.22)
    draw.arc((sx0, sy0, sx0 + shackle_w, sy0 + shackle_h), start=20, end=160, fill=color, width=stroke)

    # Hueco de llave simple para identificarlo como candado.
    key_r = max(1, int(size * 0.05))
    kc = size // 2
    ky = y0 + int(body_h * 0.42)
    draw.ellipse((kc - key_r, ky - key_r, kc + key_r, ky + key_r), fill=(0, 0, 0, 0))
    draw.rectangle((kc - 1, ky, kc + 1, ky + max(2, int(size * 0.11))), fill=(0, 0, 0, 0))
    return img


def get_icon(name: str, size: int = 20, color: str | None = None) -> ctk.CTkImage:
    """Retorna un ícono rasterizado y cacheado para evitar archivos estáticos."""
    icon_color = color or PALETTE["TEXT"]
    cache_key = (name, size, icon_color)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    img = _draw_fontawesome_icon(name, size, icon_color)
    if img is None:
        builders = {
            "sun": _draw_sun,
            "moon": _draw_moon,
            "user": _draw_user,
            "lock": _draw_lock,
        }
        builder = builders.get(name, _draw_sun)
        img = builder(size, icon_color)

    icon = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _ICON_CACHE[cache_key] = icon
    return icon


class AdminApp(ctk.CTk):
    """
    Ventana raíz del panel de administración.
    Fija en 480×800 px. Gestiona navegación entre pantallas sin sub-ventanas.
    Soporta alternancia de tema claro/oscuro vía toggle_theme().
    """

    WIDTH  = 480
    HEIGHT = 800

    def _window_title(self) -> str:
        if is_authenticated():
            return f"Smart Locker – {get_current_role_label()}"
        return "Smart Locker – Iniciar sesión"

    def __init__(self) -> None:
        super().__init__()
        self._mode = "light"
        clear_session()

        self.title(self._window_title())
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["BG"])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._frames: dict[type, ctk.CTkFrame] = {}
        self._build_frames()

        from ui.admin.login_screen import LoginScreen
        self.show_frame(LoginScreen)

    # ── Construcción / reconstrucción de pantallas ────────────────────────────

    def _build_frames(self) -> None:
        """Instancia todas las pantallas y las apila en la cuadrícula."""
        from ui.admin.dashboard       import DashboardScreen
        from ui.admin.login_screen    import LoginScreen
        from ui.admin.users_catalog   import UsersCatalogScreen
        from ui.admin.lockers_catalog import LockersCatalogScreen
        from ui.admin.areas_catalog   import AreasCatalogScreen, AccessHistoryScreen
        from ui.admin.locker_assignment import LockerAssignmentScreen
        from ui.admin.register_user   import RegisterUserScreen

        for FrameClass in (
            LoginScreen,
            DashboardScreen,
            UsersCatalogScreen,
            LockersCatalogScreen,
            AreasCatalogScreen,
            AccessHistoryScreen,
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
        _ICON_CACHE.clear()
        self._rebuild_frames()

    def toggle_lang(self) -> None:
        """Alterna entre español e inglés y reconstruye las pantallas."""
        from ui.i18n import toggle as i18n_toggle
        i18n_toggle()
        self._rebuild_frames()

    def _rebuild_frames(self) -> None:
        """Destruye todos los frames y los recrea con la paleta actualizada."""
        for frame in list(self._frames.values()):
            frame.destroy()
        self._frames.clear()
        self.configure(fg_color=PALETTE["BG"])
        self.title(self._window_title())
        self._build_frames()
        from ui.admin.dashboard import DashboardScreen
        self.show_frame(DashboardScreen)

    def on_login_success(self) -> None:
        """Se invoca cuando LoginScreen autentica al usuario en BD."""
        self._rebuild_frames()

    def logout(self) -> None:
        """Cierra la sesión actual y regresa al login."""
        from ui.admin.login_screen import LoginScreen

        clear_session()
        self.title(self._window_title())
        self.show_frame(LoginScreen)

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
