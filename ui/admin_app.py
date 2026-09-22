"""
AdminApp – ventana raíz del panel de super-administración.

Resolución fija: 480×800 px  (igual que la pantalla física del locker).
Toda la navegación es interna (tkraise), sin abrir ventanas nuevas.
Todo está diseñado para ser touchable (botones ≥ 52 px de alto).

La paleta de colores, la tipografía y los íconos viven en ui/theme.py
(traducidos de webapp/static/css/style.css, para que esta app se vea como el
panel web). PALETTE/LIGHT_PALETTE/DARK_PALETTE/get_icon se re-exportan aquí
por compatibilidad, porque las pantallas existentes en ui/admin/*.py y
ui/app.py hacen `from ui.admin_app import PALETTE, get_icon`.
"""

import os
import customtkinter as ctk
from auth.session import (
    clear_session,
    get_current_role_label,
    is_authenticated,
)
from ui import theme
from ui.theme import (  # noqa: F401  (re-exportados para las pantallas existentes)
    PALETTE,
    LIGHT_PALETTE,
    DARK_PALETTE,
    get_icon,
)
from ui.theme import _ICON_CACHE  # noqa: F401  (idem, usado por ui/app.py)

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
        theme.init_fonts()
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
        from ui.admin.areas_catalog   import AreasCatalogScreen
        from ui.admin.access_history  import AccessHistoryScreen
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
            theme.apply_dark()
        else:
            going_dark = False
            self._mode = "light"
            theme.apply_light()
        theme.clear_icon_cache()
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
