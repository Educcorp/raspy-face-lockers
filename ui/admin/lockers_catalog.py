"""
LockersCatalogScreen – Catálogo de lockers (480×800 px, touch-friendly).

Lista todos los lockers con su área, unidad y estado.
Al tocar uno → overlay de detalle con edición de estado.
Botón "+" → formulario para crear un nuevo locker.
"""

import customtkinter as ctk
import tkinter as tk
from database.connection import fetch_all, fetch_one, execute
from ui.admin_app import PALETTE, get_icon
from ui.i18n import t
from auth.session import can_edit_catalogs, is_superadmin

# Lockers 1-4 son predeterminados del sistema — área/unidad no editables, solo estado
_DEFAULT_LOCKER_IDS = frozenset({1, 2, 3, 4})


def _estado_badge(estado: str) -> tuple[str, str]:
    labels = {
        "es": {"activo": "Activo", "inactivo": "Inactivo", "mantenimiento": "Mantenimiento"},
        "en": {"activo": "Active", "inactivo": "Inactive", "mantenimiento": "Maintenance"},
    }
    from ui.i18n import get_lang
    lang = get_lang()
    label = labels.get(lang, labels["es"]).get(estado, "?")
    colors = {
        "activo": "#27ae60",
        "inactivo": PALETTE["MUTED"],
        "mantenimiento": "#d4a034",
    }
    return f"●  {label}", colors.get(estado, PALETTE["MUTED"])


class LockersCatalogScreen(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._search_var = tk.StringVar()
        self._rows: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        # Header
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64,
                           corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkButton(
            hdr, text="←", width=46, height=46,
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color="transparent", hover_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            command=self._go_back,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            hdr, text=t("lockers.title"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=4)

        if can_edit_catalogs():
            ctk.CTkButton(
                hdr, text="+", width=46, height=46,
                font=ctk.CTkFont(size=22),
                fg_color=PALETTE["ACCENT"],
                hover_color=PALETTE["ACCENT_HOVER"],
                text_color=PALETTE["WHITE"],
                command=self._open_create,
            ).pack(side="right", padx=8)

        # Búsqueda
        sf = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=12, height=48)
        sf.pack(fill="x", padx=14, pady=(12, 6))
        sf.pack_propagate(False)
        _ic = get_icon("search", size=17, color=PALETTE["MUTED"])
        ctk.CTkLabel(sf, image=_ic, text="",
                     fg_color="transparent").pack(side="left", padx=10)
        entry = ctk.CTkEntry(
            sf, textvariable=self._search_var,
            placeholder_text=t("lockers.search_placeholder"),
            fg_color="transparent", border_width=0,
            text_color=PALETTE["TEXT"], font=ctk.CTkFont(size=15),
        )
        entry.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self._search_var.trace_add("write", lambda *_: self._filter())

        # Lista
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=PALETTE["BG"],
            scrollbar_button_color=PALETTE["BORDER"],
            scrollbar_button_hover_color=PALETTE["ACCENT"],
        )
        self._list_frame.pack(fill="both", expand=True, padx=10, pady=4)

    def _render_rows(self, rows: list[dict]) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()
        if not rows:
            ctk.CTkLabel(self._list_frame, text=t("common.no_results"),
                         font=ctk.CTkFont(size=16),
                         text_color=PALETTE["MUTED"],
                         fg_color="transparent").pack(pady=40)
            return
        for r in rows:
            self._make_row(r)

    def _make_row(self, r: dict) -> None:
        badge_text, badge_color = _estado_badge(r.get("estado", ""))
        
        # Determinar si está inactivo
        estado = r.get("estado", "")
        is_inactive = estado in ["inactivo", "mantenimiento"]
        
        # Color de fondo para estado inactivo
        row_bg = "#e8e8e8" if is_inactive else PALETTE["CARD"]
        text_color = "#888888" if is_inactive else PALETTE["TEXT"]
        number_color = "#888888" if is_inactive else PALETTE["ACCENT"]
        subtitle_color = "#999999" if is_inactive else PALETTE["MUTED"]

        row_frame = ctk.CTkFrame(self._list_frame, fg_color=row_bg,
                                 corner_radius=12, border_width=1,
                                 border_color=PALETTE["BORDER"], cursor="hand2")
        row_frame.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(row_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        inner.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(inner, text=f"#  {r['idLocker']}",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=number_color, fg_color="transparent",
                     ).grid(row=0, column=0, rowspan=2, padx=(0, 14))

        # Área + indicador inactivo
        area_text = f"{t('lockers.area_prefix')} {r.get('area', '—')}"
        if is_inactive:
            area_text += f" {t('common.inactive_badge')}"
        ctk.CTkLabel(inner, text=area_text,
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=text_color, fg_color="transparent",
                     anchor="w").grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(inner, text=f"{r.get('unidad', '—')}",
                     font=ctk.CTkFont(size=12),
                     text_color=subtitle_color, fg_color="transparent",
                     anchor="w").grid(row=1, column=1, sticky="ew")

        ctk.CTkLabel(inner, text=badge_text,
                     font=ctk.CTkFont(size=12),
                     text_color=badge_color, fg_color="transparent",
                     ).grid(row=0, column=2, rowspan=2, padx=(10, 0))

        lid = r["idLocker"]
        for w in [row_frame, inner] + inner.winfo_children():
            w.bind("<Button-1>", lambda e, i=lid: self._open_detail(i))

    def _filter(self) -> None:
        q = self._search_var.get().lower()
        if not q:
            self._render_rows(self._rows)
            return
        self._render_rows([r for r in self._rows
                           if q in str(r["idLocker"])
                           or q in (r.get("area", "") or "").lower()
                           or q in (r.get("unidad", "") or "").lower()])

    def _load(self) -> None:
        self._rows = fetch_all("""
            SELECT l.idLocker, l.estado,
                   a.nombreArea AS area,
                   ua.nombreUnidadAcademica AS unidad,
                   l.idArea, l.idUnidadAcademica
            FROM lockers l
            LEFT JOIN area_lockers   a  ON a.idArea = l.idArea
            LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = l.idUnidadAcademica
            ORDER BY l.idLocker
        """)
        self._filter()

    def _go_back(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    def _open_create(self) -> None:
        if not can_edit_catalogs():
            return
        LockerCreateOverlay(self, on_close=self._load)

    def _open_detail(self, locker_id: int) -> None:
        LockerDetailOverlay(self, locker_id, on_close=self._load)

    def on_show(self, **_kwargs) -> None:
        self._load()


# ── Diálogos overlay ──────────────────────────────────────────────────────────

class _AlertDialog(ctk.CTkFrame):
    """Diálogo informativo de un solo botón (compatible Linux/RPi)."""

    def __init__(self, parent, message: str):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()

        card = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=20,
                            width=400, height=220)
        card.pack(expand=True)
        card.pack_propagate(False)

        ctk.CTkLabel(
            card, text=message,
            font=ctk.CTkFont(size=15),
            text_color=PALETTE["TEXT"], fg_color="transparent",
            wraplength=360, justify="center",
        ).pack(expand=True, padx=20, pady=(30, 10))

        ctk.CTkButton(
            card, text=t("common.accept"), height=52,
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"],
            command=self.destroy,
        ).pack(fill="x", padx=20, pady=(0, 20))


class _ConfirmDialog(ctk.CTkFrame):
    """Diálogo de confirmación como overlay en-ventana (compatible Linux/RPi)."""

    def __init__(self, parent, message: str, on_confirm):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()

        card = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=20,
                            width=400, height=250)
        card.pack(expand=True)
        card.pack_propagate(False)

        ctk.CTkLabel(
            card, text=message,
            font=ctk.CTkFont(size=15),
            text_color=PALETTE["TEXT"], fg_color="transparent",
            wraplength=360, justify="center",
        ).pack(expand=True, padx=20, pady=(30, 10))

        btn_row = ctk.CTkFrame(card, fg_color="transparent", height=60)
        btn_row.pack(fill="x", padx=20, pady=(0, 20))
        btn_row.pack_propagate(False)

        ctk.CTkButton(
            btn_row, text=t("common.cancel"), height=52,
            fg_color=PALETTE["BORDER"], hover_color=PALETTE["MUTED"],
            text_color=PALETTE["TEXT"],
            command=self.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text=t("common.confirm"), height=52,
            fg_color=PALETTE["DANGER"], hover_color="#922b21",
            text_color=PALETTE["WHITE"],
            command=lambda: (on_confirm(), self.destroy()),
        ).pack(side="right", expand=True, fill="x", padx=(6, 0))


# ── Detalle Locker ────────────────────────────────────────────────────────────

class LockerDetailOverlay(ctk.CTkFrame):
    """Overlay de pantalla completa – compatible con Linux/RPi."""

    def __init__(self, parent, locker_id: int, on_close=None):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self.locker_id = locker_id
        self._on_close = on_close
        self._can_edit = can_edit_catalogs()
        self._is_default = int(locker_id) in _DEFAULT_LOCKER_IDS
        self._unidades: list[dict] = []
        self._areas: list[dict] = []
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64,
                           corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkButton(hdr, text="←", width=46, height=46,
                      font=ctk.CTkFont(size=22, weight="bold"),
                      fg_color="transparent", hover_color=PALETTE["BORDER"],
                      text_color=PALETTE["TEXT"], command=self._close,
                      ).pack(side="left", padx=8)
        ctk.CTkLabel(hdr, text=t("lockers.detail_title"),
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=PALETTE["TEXT"],
                     fg_color="transparent").pack(side="left", padx=4)

        scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
        scroll.pack(fill="both", expand=True, padx=14, pady=10)

        # ID Locker (solo lectura)
        ctk.CTkLabel(scroll, text="ID Locker", font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self.lbl_id = ctk.CTkLabel(scroll, text="—",
                                   font=ctk.CTkFont(size=15, weight="bold"),
                                   text_color=PALETTE["TEXT"],
                                   fg_color=PALETTE["CARD"], corner_radius=8, height=42)
        self.lbl_id.pack(fill="x", padx=4)

        # Unidad académica (editable)
        ctk.CTkLabel(scroll, text=t("lockers.field_unit"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._unidad_var = tk.StringVar()
        self._unidad_var.trace_add("write", lambda *_: self._on_unit_change())
        self._unidad_menu = ctk.CTkOptionMenu(
            scroll, variable=self._unidad_var, values=["—"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._unidad_menu.pack(fill="x", padx=4)

        # Área (editable, filtrada por unidad)
        ctk.CTkLabel(scroll, text=t("lockers.field_area"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._area_var = tk.StringVar()
        self._area_menu = ctk.CTkOptionMenu(
            scroll, variable=self._area_var, values=["—"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._area_menu.pack(fill="x", padx=4)

        # Estado
        ctk.CTkLabel(scroll, text=t("common.status"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._estado_var = tk.StringVar()
        self._estado_menu = ctk.CTkOptionMenu(
            scroll, variable=self._estado_var,
            values=["activo", "inactivo", "mantenimiento"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._estado_menu.pack(fill="x", padx=4)

        # Asignación actual
        ctk.CTkLabel(scroll, text=t("lockers.current_assignment"),
                     font=ctk.CTkFont(size=12), text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(12, 2))
        self.lbl_asign = ctk.CTkLabel(scroll, text="—",
                                      font=ctk.CTkFont(size=14),
                                      text_color=PALETTE["TEXT"],
                                      fg_color=PALETTE["CARD"],
                                      corner_radius=8, height=42)
        self.lbl_asign.pack(fill="x", padx=4)

        if not self._can_edit or self._is_default:
            self._unidad_menu.configure(state="disabled")
            self._area_menu.configure(state="disabled")
        if not self._can_edit:
            self._estado_menu.configure(state="disabled")

        # Botones
        self.btn_toggle = None
        if self._can_edit:
            if self._is_default:
                ctk.CTkLabel(
                    scroll, text=t("lockers.system_protected"),
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color="#D4A34A", fg_color=PALETTE["CARD"],
                    corner_radius=8, height=40,
                ).pack(fill="x", padx=4, pady=(16, 4))
                ctk.CTkButton(
                    scroll, text=t("common.save_changes"),
                    font=ctk.CTkFont(size=15, weight="bold"),
                    fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
                    text_color=PALETTE["WHITE"], height=50, corner_radius=12,
                    command=self._save_estado_only,
                ).pack(fill="x", padx=4, pady=(0, 8))
            else:
                ctk.CTkButton(
                    scroll, text=t("common.save_changes"),
                    font=ctk.CTkFont(size=15, weight="bold"),
                    fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
                    text_color=PALETTE["WHITE"], height=50, corner_radius=12,
                    command=self._save,
                ).pack(fill="x", padx=4, pady=(16, 8))

                self.btn_toggle = ctk.CTkButton(
                    scroll, text=t("common.disable"),
                    font=ctk.CTkFont(size=15, weight="bold"),
                    fg_color=PALETTE["DANGER"], hover_color="#922b21",
                    text_color=PALETTE["WHITE"], height=50, corner_radius=12,
                    command=self._toggle_status,
                )
                self.btn_toggle.pack(fill="x", padx=4, pady=(0, 8))

                if is_superadmin():
                    ctk.CTkButton(
                        scroll, text=t("lockers.delete_btn"),
                        font=ctk.CTkFont(size=15, weight="bold"),
                        fg_color="#8B1A1A", hover_color="#6B0000",
                        text_color=PALETTE["WHITE"], height=50, corner_radius=12,
                        command=self._confirm_delete_locker,
                    ).pack(fill="x", padx=4, pady=(0, 8))

    def _on_unit_change(self) -> None:
        """Recarga las áreas disponibles para la unidad seleccionada."""
        unit_name = self._unidad_var.get()
        unit = next((u for u in self._unidades if u["nombreUnidadAcademica"] == unit_name), None)
        if unit:
            self._areas = fetch_all(
                "SELECT idArea, nombreArea FROM area_lockers "
                "WHERE idUnidadAcademica=? AND estado='activo' ORDER BY nombreArea",
                (unit["idUnidadAcademica"],),
            )
        else:
            self._areas = []
        area_names = [a["nombreArea"] for a in self._areas]
        self._area_menu.configure(values=area_names if area_names else ["—"])
        if self._area_var.get() not in area_names:
            self._area_var.set(area_names[0] if area_names else "—")

    def _load(self) -> None:
        row = fetch_one("""
            SELECT l.idLocker, l.estado, l.idArea, l.idUnidadAcademica,
                   a.nombreArea AS area,
                   ua.nombreUnidadAcademica AS unidad
            FROM lockers l
            LEFT JOIN area_lockers   a  ON a.idArea = l.idArea
            LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = l.idUnidadAcademica
            WHERE l.idLocker=?
        """, (self.locker_id,))
        if not row:
            self._close()
            return

        self.lbl_id.configure(text=str(row["idLocker"]))

        # Cargar unidades y configurar dropdown
        self._unidades = fetch_all(
            "SELECT idUnidadAcademica, nombreUnidadAcademica FROM unidad_academica "
            "WHERE estado='activo' ORDER BY nombreUnidadAcademica"
        )
        unit_names = [u["nombreUnidadAcademica"] for u in self._unidades]
        self._unidad_menu.configure(values=unit_names if unit_names else ["—"])

        # Establecer unidad → dispara _on_unit_change que carga áreas para esa unidad
        current_unidad = row.get("unidad") or ""
        if current_unidad and current_unidad in unit_names:
            self._unidad_var.set(current_unidad)
        elif unit_names:
            self._unidad_var.set(unit_names[0])
        else:
            self._unidad_var.set("—")
        # _on_unit_change ya se ejecutó: self._areas cargadas

        # Establecer área actual
        current_area = row.get("area") or ""
        area_names = [a["nombreArea"] for a in self._areas]
        if current_area and current_area in area_names:
            self._area_var.set(current_area)
        elif area_names:
            self._area_var.set(area_names[0])

        self._estado_var.set(row.get("estado", "activo"))
        if self._can_edit and self.btn_toggle:
            self._refresh_toggle_button()

        asign = fetch_one("""
            SELECT u.nombre || ' ' || u.apPaterno AS usuario,
                   al.estado AS asignEstado
            FROM asignacion_locker al
            JOIN usuarios u ON u.idUsuario = al.idUsuario
            WHERE al.idLocker=? AND al.estado='activo'
        """, (self.locker_id,))
        if asign:
            self.lbl_asign.configure(text=f"✓ {asign['usuario']}  ({asign['asignEstado']})")
        else:
            self.lbl_asign.configure(text=t("lockers.no_assignment"))

    def _save(self) -> None:
        if not self._can_edit:
            return
        unit_name = self._unidad_var.get()
        area_name = self._area_var.get()
        new_state = (self._estado_var.get() or "activo").strip()

        unit = next((u for u in self._unidades if u["nombreUnidadAcademica"] == unit_name), None)
        area = next((a for a in self._areas if a["nombreArea"] == area_name), None)

        if new_state != "activo" and self._has_active_assignment():
            _AlertDialog(
                self,
                "No puedes deshabilitar un locker con asignación activa.\nLibéralo primero.",
            )
            return
        execute(
            "UPDATE lockers SET idUnidadAcademica=?, idArea=?, estado=?, "
            "fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), "
            "modificadoPor=1 WHERE idLocker=?",
            (
                unit["idUnidadAcademica"] if unit else None,
                area["idArea"] if area else None,
                new_state,
                self.locker_id,
            ),
        )
        self._close()

    def _has_active_assignment(self) -> bool:
        row = fetch_one(
            "SELECT COUNT(*) AS n FROM asignacion_locker WHERE idLocker=? AND estado='activo'",
            (self.locker_id,),
        )
        return bool(row and (row.get("n") or 0) > 0)

    def _refresh_toggle_button(self) -> None:
        if not self.btn_toggle:
            return
        current_state = (self._estado_var.get() or "activo").strip().lower()
        is_inactive = current_state == "inactivo"
        self.btn_toggle.configure(
            text=t("common.enable") if is_inactive else t("common.disable"),
            fg_color=PALETTE["SUCCESS"] if is_inactive else PALETTE["DANGER"],
            hover_color="#1e8449" if is_inactive else "#922b21",
        )

    def _toggle_status(self) -> None:
        if not self._can_edit:
            return
        current_state = (self._estado_var.get() or "activo").strip().lower()
        new_state = "activo" if current_state == "inactivo" else "inactivo"
        self._estado_var.set(new_state)
        self._save()

    def _save_estado_only(self) -> None:
        if not self._can_edit:
            return
        new_state = (self._estado_var.get() or "activo").strip()
        if new_state != "activo" and self._has_active_assignment():
            _AlertDialog(
                self,
                "No puedes deshabilitar un locker con asignación activa.\nLibéralo primero.",
            )
            return
        execute(
            "UPDATE lockers SET estado=?, "
            "fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), "
            "modificadoPor=1 WHERE idLocker=?",
            (new_state, self.locker_id),
        )
        self._close()

    def _confirm_delete_locker(self) -> None:
        if not is_superadmin():
            return
        if self._is_default:
            _AlertDialog(self, "Los lockers predeterminados no pueden eliminarse.")
            return
        if self._has_active_assignment():
            _AlertDialog(
                self,
                "Este locker tiene una asignación activa.\nLibéralo primero en el módulo de Asignaciones.",
            )
            return
        _ConfirmDialog(
            self,
            f"¿Eliminar permanentemente el Locker #{self.locker_id}?\n\n"
            "Se borrarán también sus asignaciones históricas.\n"
            "Esta acción NO se puede deshacer.",
            on_confirm=self._do_delete_locker,
        )

    def _do_delete_locker(self) -> None:
        from database.connection import db_session
        with db_session() as conn:
            conn.execute(
                "UPDATE asignacion_locker SET estado='vencido' WHERE idLocker=?",
                (self.locker_id,),
            )
            conn.execute("DELETE FROM lockers WHERE idLocker=?", (self.locker_id,))
        self._close()

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        self.destroy()


# ── Formulario nuevo locker ───────────────────────────────────────────────────

class LockerCreateOverlay(ctk.CTkFrame):
    """Overlay de pantalla completa para crear un nuevo locker."""

    def __init__(self, parent, on_close=None):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self._on_close = on_close
        self._unidades: list[dict] = []
        self._areas: list[dict] = []
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self._build_ui()
        self._load_catalogs()

    def _build_ui(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkButton(hdr, text="←", width=46, height=46,
                      font=ctk.CTkFont(size=22, weight="bold"),
                      fg_color="transparent", hover_color=PALETTE["BORDER"],
                      text_color=PALETTE["TEXT"], command=self._close,
                      ).pack(side="left", padx=8)
        ctk.CTkLabel(hdr, text="Nuevo Locker",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=PALETTE["TEXT"],
                     fg_color="transparent").pack(side="left", padx=4)

        scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
        scroll.pack(fill="both", expand=True, padx=14, pady=10)

        # Unidad académica
        ctk.CTkLabel(scroll, text=t("lockers.field_unit"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._unidad_var = tk.StringVar()
        self._unidad_var.trace_add("write", lambda *_: self._on_unit_change())
        self._unidad_menu = ctk.CTkOptionMenu(
            scroll, variable=self._unidad_var, values=["—"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._unidad_menu.pack(fill="x", padx=4)

        # Área
        ctk.CTkLabel(scroll, text=t("lockers.field_area"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._area_var = tk.StringVar()
        self._area_menu = ctk.CTkOptionMenu(
            scroll, variable=self._area_var, values=["—"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._area_menu.pack(fill="x", padx=4)

        # Estado
        ctk.CTkLabel(scroll, text=t("common.status"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._estado_var = tk.StringVar(value="activo")
        ctk.CTkOptionMenu(
            scroll, variable=self._estado_var,
            values=["activo", "inactivo", "mantenimiento"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        ).pack(fill="x", padx=4)

        self._lbl_err = ctk.CTkLabel(scroll, text="",
                                     font=ctk.CTkFont(size=13),
                                     text_color=PALETTE["DANGER"],
                                     fg_color="transparent")
        self._lbl_err.pack(pady=(8, 0))

        ctk.CTkButton(
            scroll, text="Crear Locker",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"], height=52, corner_radius=12,
            command=self._save,
        ).pack(fill="x", padx=4, pady=(16, 8))

    def _load_catalogs(self) -> None:
        self._unidades = fetch_all(
            "SELECT idUnidadAcademica, nombreUnidadAcademica FROM unidad_academica "
            "WHERE estado='activo' ORDER BY nombreUnidadAcademica"
        )
        unit_names = [u["nombreUnidadAcademica"] for u in self._unidades]
        self._unidad_menu.configure(values=unit_names if unit_names else ["—"])
        if unit_names:
            self._unidad_var.set(unit_names[0])
        else:
            self._unidad_var.set("—")

    def _on_unit_change(self) -> None:
        unit_name = self._unidad_var.get()
        unit = next((u for u in self._unidades if u["nombreUnidadAcademica"] == unit_name), None)
        if unit:
            self._areas = fetch_all(
                "SELECT idArea, nombreArea FROM area_lockers "
                "WHERE idUnidadAcademica=? AND estado='activo' ORDER BY nombreArea",
                (unit["idUnidadAcademica"],),
            )
        else:
            self._areas = []
        area_names = [a["nombreArea"] for a in self._areas]
        self._area_menu.configure(values=area_names if area_names else ["—"])
        self._area_var.set(area_names[0] if area_names else "—")

    def _save(self) -> None:
        unit_name = self._unidad_var.get()
        area_name = self._area_var.get()
        estado = self._estado_var.get() or "activo"

        unit = next((u for u in self._unidades if u["nombreUnidadAcademica"] == unit_name), None)
        area = next((a for a in self._areas if a["nombreArea"] == area_name), None)

        if not unit or not area:
            self._lbl_err.configure(text="Selecciona una unidad académica y un área válidas.")
            return

        try:
            execute(
                "INSERT INTO lockers (idUnidadAcademica, idArea, estado, creadoPor) "
                "VALUES (?, ?, ?, 1)",
                (unit["idUnidadAcademica"], area["idArea"], estado),
            )
        except Exception as exc:
            self._lbl_err.configure(text=f"Error al crear: {str(exc)[:80]}")
            return
        self._close()

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        self.destroy()
