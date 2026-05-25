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

# ── Scroll universal para CTkScrollableFrame ──────────────────────────────────
# CTk 5.x ya maneja <MouseWheel> en Windows/Mac pero NO Button-4/5 de Linux.
# Este patch añade: (1) rueda del ratón en Linux/RPi, (2) arrastre táctil.
# Usa check_if_master_is_canvas() (API interna de CTk) para que cada frame
# solo reaccione a eventos que ocurran DENTRO de él, igual que hace CTk.

def _ctk_sf_add_scroll(sf: ctk.CTkScrollableFrame) -> None:
    canvas = sf._parent_canvas

    def _linux_wheel(event):
        if sf.check_if_master_is_canvas(event.widget):
            if canvas.yview() != (0.0, 1.0):
                canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

    drag: dict = {"y": None}

    def _drag_start(event):
        drag["y"] = event.y_root if sf.check_if_master_is_canvas(event.widget) else None

    def _drag_move(event):
        if drag["y"] is None:
            return
        if not sf.check_if_master_is_canvas(event.widget):
            return
        dy = drag["y"] - event.y_root
        drag["y"] = event.y_root
        if abs(dy) > 3:
            canvas.yview_scroll(int(dy / 8) or (1 if dy > 0 else -1), "units")

    def _drag_end(event):
        drag["y"] = None

    sf.bind_all("<Button-4>",       _linux_wheel, add="+")
    sf.bind_all("<Button-5>",       _linux_wheel, add="+")
    sf.bind_all("<ButtonPress-1>",  _drag_start,  add="+")
    sf.bind_all("<B1-Motion>",      _drag_move,   add="+")
    sf.bind_all("<ButtonRelease-1>",_drag_end,    add="+")


_ctk_sf_orig_init = ctk.CTkScrollableFrame.__init__

def _ctk_sf_patched_init(self, *args, **kwargs):
    _ctk_sf_orig_init(self, *args, **kwargs)
    _ctk_sf_add_scroll(self)

ctk.CTkScrollableFrame.__init__ = _ctk_sf_patched_init

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

# ── Teclado en pantalla ───────────────────────────────────────────────────────

import tkinter as _tk   # noqa: E402

_KB_ROWS = [
    ("qwertyuiop", "QWERTYUIOP", "1234567890"),
    ("asdfghjkl",  "ASDFGHJKL",  "-_.@#&!?%+"),
    ("zxcvbnm",    "ZXCVBNM",    "()/;:',\"~"),
]
# variable global: se instancia en AdminApp.__init__
_keyboard: "ScreenKeyboard | None" = None


class ScreenKeyboard(ctk.CTkFrame):
    """Teclado QWERTY táctil para el panel de admin.
    Se muestra en la parte inferior de la ventana cuando un CTkEntry recibe foco.
    Se cierra con ✕ o tocando fuera del área del teclado.
    """

    H = 220   # altura total del teclado

    def __init__(self, root: ctk.CTk) -> None:
        super().__init__(root, fg_color=PALETTE["CARD"], corner_radius=0,
                         height=self.H, border_width=1,
                         border_color=PALETTE["BORDER"])
        self._root    = root
        self._target: "ctk.CTkEntry | None" = None
        self._caps    = False
        self._sym     = False
        self._visible = False
        self._build()

    # ── layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # barra superior
        bar = ctk.CTkFrame(self, fg_color=PALETTE["BORDER"], height=32, corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="Teclado", font=ctk.CTkFont(size=11),
                     text_color=PALETTE["MUTED"], fg_color="transparent").pack(side="left", padx=8)
        ctk.CTkButton(bar, text="✕", width=40, height=26, font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=PALETTE["DANGER"], hover_color="#8B1A1A",
                      text_color="#FFFFFF", corner_radius=6,
                      command=self.hide).pack(side="right", padx=6, pady=3)

        self._kf = ctk.CTkFrame(self, fg_color="transparent")
        self._kf.pack(fill="both", expand=True, padx=2, pady=2)
        self._render()

    def _btn(self, parent, text, cmd, w=42, accent=False):
        fg = PALETTE["ACCENT"] if accent else PALETTE["BG"]
        tc = PALETTE["WHITE"] if accent else PALETTE["TEXT"]
        b = ctk.CTkButton(parent, text=text, width=w, height=38,
                          font=ctk.CTkFont(size=14, weight="bold" if len(text) == 1 else "normal"),
                          fg_color=fg, hover_color=PALETTE["BORDER"],
                          text_color=tc, corner_radius=5,
                          command=cmd)
        b.pack(side="left", padx=1)
        return b

    def _render(self) -> None:
        for w in self._kf.winfo_children():
            w.destroy()

        col = 2 if self._sym else (1 if self._caps else 0)
        rows = [r[col] for r in _KB_ROWS]

        for r_i, chars in enumerate(rows):
            row = ctk.CTkFrame(self._kf, fg_color="transparent")
            row.pack(fill="x", pady=1)

            if r_i == 2 and not self._sym:
                self._btn(row, "⇧", self._toggle_caps, w=46, accent=self._caps)

            for ch in chars:
                self._btn(row, ch, lambda c=ch: self._type(c))

            if r_i == 1:
                self._btn(row, "⌫", self._backspace, w=48)

        # fila inferior
        bot = ctk.CTkFrame(self._kf, fg_color="transparent")
        bot.pack(fill="x", pady=1)
        self._btn(bot, "?123" if not self._sym else "ABC", self._toggle_sym,
                  w=54, accent=self._sym)
        ctk.CTkButton(bot, text="espacio", height=38, font=ctk.CTkFont(size=12),
                      fg_color=PALETTE["BG"], hover_color=PALETTE["BORDER"],
                      text_color=PALETTE["MUTED"], corner_radius=5,
                      command=lambda: self._type(" ")
                      ).pack(side="left", padx=1, fill="x", expand=True)
        self._btn(bot, "@",  lambda: self._type("@"), w=38)
        self._btn(bot, ".",  lambda: self._type("."), w=38)
        self._btn(bot, "⌫", self._backspace,          w=44)

    # ── acciones ─────────────────────────────────────────────────────────────

    def _type(self, ch: str) -> None:
        if self._target is None:
            return
        try:
            e = self._target._entry
            e.insert(_tk.INSERT, ch)
            e.event_generate("<<Modified>>")
        except Exception:
            pass
        if self._caps and not self._sym:
            self._caps = False
            self._render()

    def _backspace(self) -> None:
        if self._target is None:
            return
        try:
            e = self._target._entry
            i = e.index(_tk.INSERT)
            if i > 0:
                e.delete(i - 1, i)
            e.event_generate("<<Modified>>")
        except Exception:
            pass

    def _toggle_caps(self) -> None:
        self._caps = not self._caps
        self._render()

    def _toggle_sym(self) -> None:
        self._sym = not self._sym
        self._render()

    # ── visibilidad ───────────────────────────────────────────────────────────

    def show(self, entry: ctk.CTkEntry) -> None:
        self._target = entry
        if not self._visible:
            self.place(x=0, y=800 - self.H, relwidth=1)
            self.lift()
            self._visible = True

    def hide(self) -> None:
        self._target = None
        if self._visible:
            self.place_forget()
            self._visible = False

    def is_inside(self, rx: int, ry: int) -> bool:
        try:
            return (self.winfo_rootx() <= rx <= self.winfo_rootx() + self.winfo_width() and
                    self.winfo_rooty() <= ry <= self.winfo_rooty() + self.winfo_height())
        except Exception:
            return False


# Patch de CTkEntry: muestra el teclado al ganar el foco
_orig_entry_init = ctk.CTkEntry.__init__

def _entry_patched_init(self, *args, **kwargs):
    _orig_entry_init(self, *args, **kwargs)
    try:
        self._entry.bind(
            "<FocusIn>",
            lambda e, en=self: _keyboard and _keyboard.show(en),
            add="+",
        )
    except Exception:
        pass

ctk.CTkEntry.__init__ = _entry_patched_init


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
    "search": "\uf002",   # lupa / magnifying glass
    "times":  "\uf00d",   # \u2715  salir / kiosk exit
}
_FA_ICON_SCALE = {
    "sun": 0.90,
    "moon": 0.90,
    "user": 0.78,
    "lock": 0.86,
    "logout": 0.86,
    "eye": 0.84,
    "eye-off": 0.84,
    "search": 0.86,
    "times":  0.80,
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


def _draw_times(size: int, color: str) -> Image.Image:
    """Fallback: dibuja una X (cerrar/salir)."""
    img  = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    lw   = max(2, int(size * 0.13))
    m    = int(size * 0.22)
    draw.line([(m, m), (size - m, size - m)], fill=color, width=lw)
    draw.line([(size - m, m), (m, size - m)], fill=color, width=lw)
    return img


def _draw_search(size: int, color: str) -> Image.Image:
    """Fallback: dibuja una lupa (círculo + mango)."""
    img  = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    r    = int(size * 0.28)
    cx   = int(size * 0.40)
    cy   = int(size * 0.40)
    lw   = max(2, int(size * 0.12))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=lw)
    # mango diagonal
    x0 = int(cx + r * 0.70)
    y0 = int(cy + r * 0.70)
    x1 = int(size * 0.86)
    y1 = int(size * 0.86)
    draw.line((x0, y0, x1, y1), fill=color, width=lw)
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
            "sun":    _draw_sun,
            "moon":   _draw_moon,
            "user":   _draw_user,
            "lock":   _draw_lock,
            "search": _draw_search,
            "times":  _draw_times,
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

        # Crear el teclado en pantalla y registrarlo globalmente
        global _keyboard
        _keyboard = ScreenKeyboard(self)

        # Cerrar teclado al tocar fuera de él
        self.bind_all("<ButtonPress-1>", self._close_keyboard_if_outside, add="+")

        from ui.admin.login_screen import LoginScreen
        self.show_frame(LoginScreen)

    def _close_keyboard_if_outside(self, event) -> None:
        if _keyboard is None or not _keyboard._visible:
            return
        # Si el click fue dentro del teclado, ignorar
        if _keyboard.is_inside(event.x_root, event.y_root):
            return
        # Si el click fue en un CTkEntry, el FocusIn lo mostrará de nuevo
        w = event.widget
        while w is not None:
            if isinstance(w, ctk.CTkEntry):
                return
            w = getattr(w, "master", None)
        _keyboard.hide()

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
            going_dark = True
            self._mode = "dark"
            PALETTE.update(DARK_PALETTE)
        else:
            going_dark = False
            self._mode = "light"
            PALETTE.update(LIGHT_PALETTE)
        _ICON_CACHE.clear()
        label = "Cambiando a modo oscuro…" if going_dark else "Cambiando a modo claro…"
        icon  = "🌙" if going_dark else "☀️"
        self._rebuild_frames(transition_text=label, transition_icon=icon)

    def toggle_lang(self) -> None:
        """Alterna entre español e inglés y reconstruye las pantallas."""
        from ui.i18n import toggle as i18n_toggle
        i18n_toggle()
        self._rebuild_frames()

    def _rebuild_frames(
        self,
        transition_text: str = "",
        transition_icon: str = "",
    ) -> None:
        """Reconstruye todos los frames mostrando una pantalla de transición.

        1. Se muestra una pantalla opaca encima de todo el contenido actual
           (con mensaje opcional) y se dibuja síncronamente.
        2. La reconstrucción ocurre detrás sin llamar a update() — ningún
           frame intermedio se pinta en pantalla.
        3. Al destruir la pantalla de transición, el event loop dibuja
           directamente el estado final ya listo.
        """
        bg  = PALETTE["BG"]
        txt = PALETTE["TEXT"]
        mut = PALETTE["MUTED"]

        # ── Pantalla de transición ────────────────────────────────────────────
        veil = ctk.CTkFrame(self, fg_color=bg, corner_radius=0)
        veil.place(x=0, y=0, relwidth=1, relheight=1)
        veil.lift()

        if transition_icon or transition_text:
            inner = ctk.CTkFrame(veil, fg_color="transparent")
            inner.place(relx=0.5, rely=0.5, anchor="center")

            if transition_icon:
                ctk.CTkLabel(
                    inner,
                    text=transition_icon,
                    font=ctk.CTkFont(size=52),
                    fg_color="transparent",
                    text_color=txt,
                ).pack(pady=(0, 12))

            if transition_text:
                ctk.CTkLabel(
                    inner,
                    text=transition_text,
                    font=ctk.CTkFont(size=18, weight="bold"),
                    fg_color="transparent",
                    text_color=txt,
                ).pack()

            ctk.CTkLabel(
                inner,
                text="Por favor espera…",
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                text_color=mut,
            ).pack(pady=(6, 0))

        # ── Diferir el rebuild al siguiente tick del event loop ──────────────────
        # update_idletasks() no garantiza flush físico al display en X11/RPi.
        # Los frames nuevos nacen con z-order mayor al veil (creados después).
        # Con after(30) el event loop dibuja el veil en pantalla primero;
        # el rebuild ocurre en _do_rebuild() con el veil ya físicamente visible.
        self.after(30, lambda: self._do_rebuild(veil))

    def _do_rebuild(self, veil: "ctk.CTkFrame") -> None:
        """Rebuilds all frames. Runs after the transition screen is already visible."""
        try:
            if _keyboard:
                _keyboard.hide()

            ctk.set_appearance_mode("dark" if self._mode == "dark" else "light")

            for frame in list(self._frames.values()):
                frame.destroy()
            self._frames.clear()

            self.configure(fg_color=PALETTE["BG"])
            self.title(self._window_title())
            self._build_frames()

            from ui.admin.dashboard import DashboardScreen
            self.show_frame(DashboardScreen)

        finally:
            # Re-levantar el veil: los frames nuevos nacen con z-order mayor.
            # lift() lo pone encima de todos antes de destruirlo.
            if veil.winfo_exists():
                veil.lift()
                veil.destroy()

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
