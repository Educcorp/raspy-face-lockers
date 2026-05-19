"""
ui/components/language_button.py – Botón reutilizable para alternar ES/EN.

Uso:
    from ui.components.language_button import LanguageToggleButton

    btn = LanguageToggleButton(parent)
    btn.pack(side="right", padx=8)
"""

from __future__ import annotations

import customtkinter as ctk
from core.i18n import get_language, set_language, register_observer, unregister_observer


class LanguageToggleButton(ctk.CTkButton):
    """
    Botón que muestra el idioma actual y lo alterna al hacer clic.

    Muestra  🇲🇽 Español  cuando el idioma es 'es'.
    Muestra  🇺🇸 English  cuando el idioma es 'en'.

    Se auto-actualiza cuando otro componente cambia el idioma.
    """

    _LABELS = {
        "es": "🇲🇽 Español",
        "en": "🇺🇸 English",
    }

    def __init__(self, parent, **kwargs):
        # Defaults visuales — pueden ser sobreescritos vía kwargs
        defaults = dict(
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color="#CCCCCC",
            text_color="#FFFFFF",
            border_width=1,
            border_color="#AAAAAA",
            width=110,
            height=34,
            corner_radius=10,
        )
        defaults.update(kwargs)
        super().__init__(
            parent,
            text=self._LABELS.get(get_language(), "🇲🇽 Español"),
            command=self._toggle,
            **defaults,
        )
        register_observer(self._on_lang_change)

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        current = get_language()
        set_language("en" if current == "es" else "es")

    def _on_lang_change(self) -> None:
        try:
            if self.winfo_exists():
                self.configure(text=self._LABELS.get(get_language(), "🇲🇽 Español"))
        except Exception:
            pass

    def destroy(self) -> None:
        unregister_observer(self._on_lang_change)
        super().destroy()
