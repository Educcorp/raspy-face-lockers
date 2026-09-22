"""
ui/theme.py – Tema visual compartido de la app del Pi.

Fuente única de colores, tipografía e iconos, traducidos de la paleta y las
fuentes del panel web (webapp/static/css/style.css) para que ambas
interfaces se vean como el mismo producto. Toda pantalla de ui/admin y
ui/locker_screen debe leer sus colores/fuentes de aquí en vez de definir
hex codes propios.

Paleta (misma semántica que las custom properties --bg/--card/--accent/...
de style.css, con una variante oscura equivalente para el toggle de tema
que ya tenía la app):
    BG            Fondo de la ventana
    CARD          Superficie de tarjetas/paneles
    SURFACE_ALT   Hover / fondos muteados (filas, tracks)
    BORDER        Bordes finos
    TEXT          Texto principal
    MUTED         Texto secundario
    ACCENT        Color de marca (botones primarios, elementos activos)
    ACCENT_HOVER  Hover del color de marca
    ACCENT_SOFT   Fondo suave de marca (avatares, iconos de stat cards)
    SAGE          Acento secundario orgánico (usado en login)
    SAGE_SOFT     Fondo suave del acento secundario
    SUCCESS / SUCCESS_SOFT, DANGER / DANGER_SOFT, WARN / WARN_SOFT
                  Estados (activo/ok, error/eliminar, advertencia/pendiente)
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

_HERE = Path(__file__).resolve().parent
_ASSETS_DIR = _HERE.parent / "assets"
FONTS_DIR = _ASSETS_DIR / "fonts"

# ── Paletas (traducidas de las custom properties de webapp/static/css/style.css) ──
LIGHT_PALETTE = {
    "BG":                 "#faf5ef",
    "CARD":               "#fffdfb",
    "SURFACE_ALT":        "#f3e9dd",
    "BORDER":             "#e9dcca",
    "TEXT":               "#2c241d",
    "MUTED":              "#8c7c6b",
    "ACCENT":             "#c1603c",
    "ACCENT_HOVER":       "#a44d2f",
    "ACCENT_SOFT":        "#f6e1d3",
    "ACCENT_SOFT_STRONG": "#eeccb3",
    "SAGE":               "#5c7a5e",
    "SAGE_SOFT":          "#e5ede2",
    "SUCCESS":            "#4f7a5c",
    "SUCCESS_SOFT":       "#e6ede4",
    "DANGER":             "#b8493f",
    "DANGER_SOFT":        "#f8e5e1",
    "WARN":               "#c1862c",
    "WARN_SOFT":          "#f6ecd7",
    "WHITE":              "#ffffff",
}

# Misma identidad de marca (terracota/sage) sobre superficies oscuras, para
# que alternar el tema no rompa la relación visual con el panel web.
DARK_PALETTE = {
    "BG":                 "#1c1712",
    "CARD":               "#241d17",
    "SURFACE_ALT":        "#2e251d",
    "BORDER":             "#3a2f25",
    "TEXT":               "#f1e9df",
    "MUTED":              "#a3937f",
    "ACCENT":             "#e08a5f",
    "ACCENT_HOVER":       "#c1603c",
    "ACCENT_SOFT":        "#3a2a20",
    "ACCENT_SOFT_STRONG": "#4a3527",
    "SAGE":               "#8fae90",
    "SAGE_SOFT":          "#2a332a",
    "SUCCESS":            "#7fa889",
    "SUCCESS_SOFT":       "#25332a",
    "DANGER":             "#d97b6f",
    "DANGER_SOFT":        "#3a2422",
    "WARN":               "#d9a95f",
    "WARN_SOFT":          "#382d1c",
    "WHITE":              "#ffffff",
}

# ── Paleta activa (mutable – todas las pantallas la importan y la leen en vivo) ──
PALETTE: dict = dict(LIGHT_PALETTE)


def apply_light() -> None:
    PALETTE.clear()
    PALETTE.update(LIGHT_PALETTE)


def apply_dark() -> None:
    PALETTE.clear()
    PALETTE.update(DARK_PALETTE)


# ── Radios / espaciados (igual que --radius/--radius-sm/--radius-lg en CSS) ──
RADIUS_CARD = 20
RADIUS_CARD_LG = 28
RADIUS_SM = 12
RADIUS_PILL = 999

PAD_CARD = 20
PAD_FIELD = 12
GAP = 12

# ── Colores de estado (equivalentes a .badge.activo/.inactivo/... en CSS) ──
STATUS_TOKENS = {
    "activo":        ("SUCCESS", "SUCCESS_SOFT"),
    "registrado":    ("SUCCESS", "SUCCESS_SOFT"),
    "permitido":     ("SUCCESS", "SUCCESS_SOFT"),
    "inactivo":      ("MUTED", "SURFACE_ALT"),
    "suspendido":    ("DANGER", "DANGER_SOFT"),
    "vencido":       ("DANGER", "DANGER_SOFT"),
    "denegado":      ("DANGER", "DANGER_SOFT"),
    "mantenimiento": ("WARN", "WARN_SOFT"),
    "pendiente":     ("WARN", "WARN_SOFT"),
}


def status_colors(status: str) -> tuple[str, str]:
    """(color_texto, color_fondo) resueltos contra la PALETTE activa, para un
    estado dado (activo/inactivo/suspendido/vencido/mantenimiento/pendiente/...).
    Estado desconocido cae a la variante muted/neutral."""
    key = (status or "").strip().lower()
    fg_key, bg_key = STATUS_TOKENS.get(key, ("MUTED", "SURFACE_ALT"))
    return PALETTE[fg_key], PALETTE[bg_key]


# ── Tipografía (Inter + Fraunces, igual que el panel web) ─────────────────────
# Ambas se bundlean como fuentes variables únicas en assets/fonts/ (no había
# archivos .ttf locales antes; el web las carga desde Google Fonts CDN, algo
# que no aplica a una app de escritorio). Se instalan a nivel de usuario en
# tiempo de ejecución para que Tk pueda resolverlas por nombre de familia.
_FONT_BODY_NAME = "Inter"
_FONT_DISPLAY_NAME = "Fraunces"
_FALLBACK_BODY = "Helvetica"
_FALLBACK_DISPLAY = "Georgia"

_font_body_family = _FALLBACK_BODY
_font_display_family = _FALLBACK_DISPLAY
_fonts_ready = False


def _install_bundled_fonts() -> None:
    """Copia los .ttf de assets/fonts/ a ~/.local/share/fonts y refresca la
    caché de fontconfig. No falla el arranque si no hay permisos o `fc-cache`
    no está disponible: en ese caso se usa la fuente del sistema."""
    try:
        target_dir = Path.home() / ".local" / "share" / "fonts" / "smart-locker"
        target_dir.mkdir(parents=True, exist_ok=True)
        copied = False
        for ttf in FONTS_DIR.glob("*.ttf"):
            if ttf.name == "fa-solid-900.ttf":
                continue  # fuente de iconos, no de texto
            dest = target_dir / ttf.name
            if not dest.exists() or dest.stat().st_size != ttf.stat().st_size:
                shutil.copy2(ttf, dest)
                copied = True
        if copied:
            subprocess.run(
                ["fc-cache", "-f", str(target_dir)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
    except Exception:
        pass


def _family_available(family: str) -> bool:
    try:
        import tkinter.font as tkfont
        return family in set(tkfont.families())
    except Exception:
        return False


def init_fonts() -> None:
    """Registra Inter/Fraunces. Debe llamarse una vez con una ventana Tk raíz
    ya creada (tkinter.font.families() requiere un root activo)."""
    global _font_body_family, _font_display_family, _fonts_ready
    if _fonts_ready:
        return
    _fonts_ready = True

    _install_bundled_fonts()
    _font_body_family = _FONT_BODY_NAME if _family_available(_FONT_BODY_NAME) else _FALLBACK_BODY
    _font_display_family = _FONT_DISPLAY_NAME if _family_available(_FONT_DISPLAY_NAME) else _FALLBACK_DISPLAY


def font_body(size: int = 14, weight: str = "normal") -> ctk.CTkFont:
    """Fuente de UI/cuerpo (equivalente a "Inter" en el web)."""
    return ctk.CTkFont(family=_font_body_family, size=size, weight=weight)


def font_display(size: int = 22, weight: str = "bold") -> ctk.CTkFont:
    """Fuente de encabezados/números grandes (equivalente a "Fraunces")."""
    return ctk.CTkFont(family=_font_display_family, size=size, weight=weight)


# ── Iconos (SVG-like, renderizados a bitmap y cacheados) ──────────────────────
# El web usa iconos SVG inline estilo Feather; en Tk se renderizan glifos de
# Font Awesome (ya bundleada en assets/fonts/fa-solid-900.ttf) con un
# fallback dibujado a mano en PIL si la fuente no está disponible.
_ICON_CACHE: dict[tuple[str, int, str], "ctk.CTkImage"] = {}
_FA_FONT_PATH = FONTS_DIR / "fa-solid-900.ttf"

_FA_GLYPHS = {
    "sun":          "",
    "moon":         "",
    "user":         "",
    "lock":         "",
    "logout":       "",
    "eye":          "",
    "eye-off":      "",
    "search":       "",
    "times":        "",
    "home":         "",
    "box":          "",
    "link":         "",
    "clock":        "",
    "layers":       "",
    "chevron-down": "",
    "chevron-right":"",
    "bars":         "",
    "pencil":       "",
    "trash":        "",
    "plus":         "",
    "check-circle": "",
    "warning":      "",
}
_FA_ICON_SCALE = {
    "sun": 0.90, "moon": 0.90, "user": 0.78, "lock": 0.86, "logout": 0.86,
    "eye": 0.84, "eye-off": 0.84, "search": 0.86, "times": 0.80,
    "home": 0.84, "box": 0.82, "link": 0.82, "clock": 0.84, "layers": 0.82,
    "chevron-down": 0.78, "chevron-right": 0.78, "bars": 0.86,
    "pencil": 0.80, "trash": 0.82, "plus": 0.86,
    "check-circle": 0.86, "warning": 0.86,
}
_FA_ICON_Y_OFFSET = {"user": 1}


def _icon_canvas(size: int) -> Image.Image:
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def _draw_fontawesome_icon(name: str, size: int, color: str) -> Image.Image | None:
    glyph = _FA_GLYPHS.get(name)
    if not glyph or not _FA_FONT_PATH.exists():
        return None
    scale = _FA_ICON_SCALE.get(name, 0.88)
    try:
        font = ImageFont.truetype(str(_FA_FONT_PATH), size=max(10, int(size * scale)))
    except Exception:
        return None

    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), glyph, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1] + _FA_ICON_Y_OFFSET.get(name, 0)
    draw.text((x, y), glyph, font=font, fill=color)
    return img


def _draw_bars(size: int, color: str) -> Image.Image:
    """Fallback: 3 líneas horizontales (menú hamburguesa)."""
    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    lw = max(2, int(size * 0.11))
    x0, x1 = int(size * 0.18), int(size * 0.82)
    for frac in (0.28, 0.5, 0.72):
        y = int(size * frac)
        draw.line((x0, y, x1, y), fill=color, width=lw)
    return img


def _draw_chevron_down(size: int, color: str) -> Image.Image:
    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    lw = max(2, int(size * 0.12))
    x0, xm, x1 = int(size * 0.22), size // 2, int(size * 0.78)
    y0, y1 = int(size * 0.38), int(size * 0.62)
    draw.line((x0, y0, xm, y1), fill=color, width=lw)
    draw.line((xm, y1, x1, y0), fill=color, width=lw)
    return img


def _draw_times(size: int, color: str) -> Image.Image:
    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    lw = max(2, int(size * 0.13))
    m = int(size * 0.22)
    draw.line([(m, m), (size - m, size - m)], fill=color, width=lw)
    draw.line([(size - m, m), (m, size - m)], fill=color, width=lw)
    return img


def _draw_search(size: int, color: str) -> Image.Image:
    img = _icon_canvas(size)
    draw = ImageDraw.Draw(img)
    r = int(size * 0.28)
    cx = cy = int(size * 0.40)
    lw = max(2, int(size * 0.12))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=lw)
    x0, y0 = int(cx + r * 0.70), int(cy + r * 0.70)
    x1, y1 = int(size * 0.86), int(size * 0.86)
    draw.line((x0, y0, x1, y1), fill=color, width=lw)
    return img


_FALLBACK_BUILDERS = {
    "bars": _draw_bars,
    "chevron-down": _draw_chevron_down,
    "times": _draw_times,
    "search": _draw_search,
}


def get_icon(name: str, size: int = 20, color: str | None = None) -> "ctk.CTkImage":
    """Ícono rasterizado y cacheado. Usa Font Awesome si está disponible, si no
    cae a un dibujo simple en PIL (solo para los íconos con fallback definido)."""
    icon_color = color or PALETTE["TEXT"]
    cache_key = (name, size, icon_color)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    img = _draw_fontawesome_icon(name, size, icon_color)
    if img is None:
        builder = _FALLBACK_BUILDERS.get(name, _draw_bars)
        img = builder(size, icon_color)

    icon = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _ICON_CACHE[cache_key] = icon
    return icon


def clear_icon_cache() -> None:
    _ICON_CACHE.clear()
