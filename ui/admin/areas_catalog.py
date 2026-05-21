"""
AreasCatalogScreen – Catálogos de Áreas y Unidades Académicas.

Una única pantalla con 2 pestañas táctiles:
  1. Áreas / Zonas      (area_lockers)
  2. Unidades Acad.     (unidad_academica)

Cada pestaña ofrece lista + CRUD completo.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from database.connection import fetch_all, fetch_one, execute
from ui.admin_app import PALETTE
from ui.i18n import t
from auth.session import can_edit_catalogs, is_superadmin
from utils.validators import (
    validate_area_nombre, validate_unidad_nombre, limit_var,
    MAX_AREA_NOMBRE, MAX_UNIDAD_NOMBRE,
)


# ── Widget genérico de fila de catálogo ──────────────────────────────────────

def _catalog_row(parent, primary_text: str, sub_text: str,
                 on_click, estado: str = "activo") -> ctk.CTkFrame:
    # Determinar si está inactivo
    is_inactive = estado != "activo"
    
    # Colores para estado inactivo
    dot_color = "#27ae60" if estado == "activo" else PALETTE["MUTED"]
    row_bg = "#e8e8e8" if is_inactive else PALETTE["CARD"]
    text_color = "#888888" if is_inactive else PALETTE["TEXT"]
    subtitle_color = "#999999" if is_inactive else PALETTE["MUTED"]
    arrow_color = "#888888" if is_inactive else PALETTE["ACCENT"]
    
    row_frame = ctk.CTkFrame(parent, fg_color=row_bg, corner_radius=12,
                             border_width=1, border_color=PALETTE["BORDER"],
                             cursor="hand2")
    row_frame.pack(fill="x", padx=4, pady=4)

    inner = ctk.CTkFrame(row_frame, fg_color="transparent")
    inner.pack(fill="x", padx=14, pady=10)
    inner.grid_columnconfigure(1, weight=1)

    # Indicador de estado
    estado_text = "⊘" if is_inactive else "●"
    ctk.CTkLabel(inner, text=estado_text, font=ctk.CTkFont(size=14),
                 text_color=dot_color,
                 fg_color="transparent").grid(row=0, column=0, rowspan=2,
                                              padx=(0, 10))
    
    # Nombre + indicador inactivo
    display_text = primary_text + (" [INACTIVO]" if is_inactive else "")
    ctk.CTkLabel(inner, text=display_text,
                 font=ctk.CTkFont(size=15, weight="bold"),
                 text_color=text_color, fg_color="transparent",
                 anchor="w").grid(row=0, column=1, sticky="ew")
    ctk.CTkLabel(inner, text=sub_text, font=ctk.CTkFont(size=12),
                 text_color=subtitle_color, fg_color="transparent",
                 anchor="w").grid(row=1, column=1, sticky="ew")
    ctk.CTkLabel(inner, text="›", font=ctk.CTkFont(size=22),
                 text_color=arrow_color,
                 fg_color="transparent").grid(row=0, column=2, rowspan=2,
                                              padx=(10, 0))

    for w in [row_frame, inner] + inner.winfo_children():
        w.bind("<Button-1>", lambda e: on_click())
    return row_frame


# ── Pantalla principal ────────────────────────────────────────────────────────

class AreasCatalogScreen(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._active_tab = "areas"
        self._can_edit = can_edit_catalogs()
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
            text_color=PALETTE["TEXT"], command=self._go_back,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            hdr, text=t("areas.title"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=4)

        self.btn_add = ctk.CTkButton(
            hdr, text="+", width=46, height=46,
            font=ctk.CTkFont(size=22),
            fg_color=PALETTE["ACCENT"] if self._can_edit else PALETTE["BORDER"],
            hover_color=PALETTE["ACCENT_HOVER"] if self._can_edit else PALETTE["BORDER"],
            text_color=PALETTE["WHITE"],
            command=self._add_item if self._can_edit else None,
        )
        self.btn_add.pack(side="right", padx=8)

        # Tabs
        tab_bar = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=48,
                               corner_radius=0)
        tab_bar.pack(fill="x")

        self._tabs = {}
        tab_defs = [
            ("areas",    t("areas.tab.areas")),
            ("unidades", t("areas.tab.units")),
        ]
        tab_bar.grid_columnconfigure((0, 1), weight=1)
        for col, (key, label) in enumerate(tab_defs):
            btn = ctk.CTkButton(
                tab_bar, text=label,
                font=ctk.CTkFont(size=14, weight="bold"),
                height=42, corner_radius=0,
                fg_color=PALETTE["ACCENT"] if key == "areas" else PALETTE["CARD"],
                hover_color=PALETTE["ACCENT_HOVER"],
                text_color=PALETTE["WHITE"] if key == "areas" else PALETTE["MUTED"],
                command=lambda k=key: self._switch_tab(k),
            )
            btn.grid(row=0, column=col, sticky="nsew", padx=1)
            self._tabs[key] = btn

        # Lista scrollable
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=PALETTE["BG"],
            scrollbar_button_color=PALETTE["BORDER"],
            scrollbar_button_hover_color=PALETTE["ACCENT"],
        )
        self._list_frame.pack(fill="both", expand=True, padx=10, pady=8)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _switch_tab(self, key: str) -> None:
        self._active_tab = key
        for k, btn in self._tabs.items():
            if k == key:
                btn.configure(fg_color=PALETTE["ACCENT"],
                              text_color=PALETTE["WHITE"])
            else:
                btn.configure(fg_color=PALETTE["CARD"],
                              text_color=PALETTE["MUTED"])
        self._load()

    def _load(self) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()

        if self._active_tab == "areas":
            self._load_areas()
        else:
            self._load_unidades()

    # ── Áreas ─────────────────────────────────────────────────────────────────

    def _load_areas(self) -> None:
        rows = fetch_all(
            "SELECT a.*, u.nombre||' '||u.apPaterno AS encargado, "
            "ua.nombreUnidadAcademica AS nombreUnidad "
            "FROM area_lockers a "
            "LEFT JOIN usuarios u ON u.idUsuario = a.idUsuario "
            "LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = a.idUnidadAcademica "
            "ORDER BY a.nombreArea"
        )
        if not rows:
            ctk.CTkLabel(self._list_frame, text=t("areas.no_areas"),
                         font=ctk.CTkFont(size=16),
                         text_color=PALETTE["MUTED"],
                         fg_color="transparent").pack(pady=40)
            return
        for r in rows:
            unidad_label = r.get("nombreUnidad") or "—"
            _catalog_row(
                self._list_frame,
                primary_text=r["nombreArea"],
                sub_text=f"{t('areas.field_unidad')}: {unidad_label}  ·  ID {r['idArea']}",
                on_click=lambda row=r: AreaFormOverlay(self, row, on_close=self._load),
                estado=r.get("estado", "activo"),
            )

    # ── Unidades académicas ───────────────────────────────────────────────────

    def _load_unidades(self) -> None:
        rows = fetch_all(
            "SELECT * FROM unidad_academica ORDER BY nombreUnidadAcademica"
        )
        if not rows:
            ctk.CTkLabel(self._list_frame, text=t("areas.no_units"),
                         font=ctk.CTkFont(size=16),
                         text_color=PALETTE["MUTED"],
                         fg_color="transparent").pack(pady=40)
            return
        for r in rows:
            _catalog_row(
                self._list_frame,
                r["nombreUnidadAcademica"],
                f"{r['estado']}  ·  ID {r['idUnidadAcademica']}",
                on_click=lambda row=r: UnidadFormOverlay(self, row, on_close=self._load),
                estado=r.get("estado", "activo"),
            )

    # ── Añadir ────────────────────────────────────────────────────────────────

    def _add_item(self) -> None:
        if not self._can_edit:
            return
        if self._active_tab == "areas":
            AreaFormOverlay(self, None, on_close=self._load)
        else:
            UnidadFormOverlay(self, None, on_close=self._load)

    # ── Navegación ────────────────────────────────────────────────────────────

    def _go_back(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    def on_show(self, **_kwargs) -> None:
        self._load()


# ══ Overlays de formulario ════════════════════════════════════════════════════

class _BaseFormOverlay(ctk.CTkFrame):
    """
    Overlay de pantalla completa dentro de la ventana principal.
    Reemplaza CTkToplevel para compatibilidad con Linux/Raspberry Pi.
    """

    def __init__(self, parent, title: str, height: int = 460, on_close=None):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self._on_close = on_close
        self._can_edit = can_edit_catalogs()
        # Cubrir toda la ventana principal
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()

        # Header
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64,
                           corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkButton(hdr, text="←", width=46, height=46,
                      fg_color="transparent", hover_color=PALETTE["BORDER"],
                      font=ctk.CTkFont(size=22, weight="bold"),
                      text_color=PALETTE["TEXT"],
                      command=self._close).pack(side="left", padx=8)
        ctk.CTkLabel(hdr, text=title, font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=PALETTE["TEXT"],
                     fg_color="transparent").pack(side="left", padx=4)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
        self.scroll.pack(fill="both", expand=True, padx=14, pady=10)

        # Label de error reutilizable — se muestra antes de los botones de acción
        self._err_lbl = ctk.CTkLabel(
            self.scroll, text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["DANGER"],
            fg_color="transparent",
            wraplength=430, justify="center",
        )
        self._err_lbl.pack(pady=(4, 0))

    def _show_err(self, msg: str) -> None:
        self._err_lbl.configure(text=msg, text_color=PALETTE["DANGER"])

    def _clear_err(self) -> None:
        self._err_lbl.configure(text="")

    def _field(self, label: str) -> ctk.CTkEntry:
        ctk.CTkLabel(self.scroll, text=label, font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        entry = ctk.CTkEntry(self.scroll, font=ctk.CTkFont(size=15),
                             fg_color=PALETTE["CARD"],
                             border_color=PALETTE["BORDER"],
                             text_color=PALETTE["TEXT"], height=46)
        entry.pack(fill="x", padx=4)
        if not self._can_edit:
            entry.configure(state="disabled")
        return entry

    def _selector(self, label: str, var: tk.StringVar,
                  values: list[str]) -> ctk.CTkOptionMenu:
        ctk.CTkLabel(self.scroll, text=label, font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        menu = ctk.CTkOptionMenu(self.scroll, variable=var, values=values,
                                 fg_color=PALETTE["CARD"],
                                 button_color=PALETTE["ACCENT"],
                                 button_hover_color=PALETTE["ACCENT_HOVER"],
                                 text_color=PALETTE["TEXT"],
                                 font=ctk.CTkFont(size=15), height=46)
        menu.pack(fill="x", padx=4)
        if not self._can_edit:
            menu.configure(state="disabled")
        return menu

    def _save_btn(self, command) -> None:
        if not self._can_edit:
            return
        ctk.CTkButton(self.scroll, text=t("common.save"),
                      font=ctk.CTkFont(size=16, weight="bold"),
                      fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
                      text_color=PALETTE["WHITE"], height=52, corner_radius=12,
                      command=command).pack(fill="x", padx=4, pady=16)

    def _delete_btn(self, command, text: str = "", is_enable: bool = False) -> None:
        if not self._can_edit:
            return
        btn_text = text if text else t("common.disable")
        is_enable_action = is_enable
        fg_color = PALETTE["SUCCESS"] if is_enable_action else PALETTE["DANGER"]
        hover_color = "#1e8449" if is_enable_action else "#922b21"
        ctk.CTkButton(self.scroll, text=btn_text,
                      font=ctk.CTkFont(size=16, weight="bold"),
                      fg_color=fg_color, hover_color=hover_color,
                      text_color=PALETTE["WHITE"], height=52, corner_radius=12,
                      command=command).pack(fill="x", padx=4, pady=(0, 8))

    def _delete_btn_permanent(self, command) -> None:
        if not is_superadmin():
            return
        ctk.CTkButton(self.scroll, text=t("common.delete_permanent"),
                      font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color="#6d1a1a", hover_color="#4a0f0f",
                      text_color=PALETTE["WHITE"], height=48, corner_radius=12,
                      command=command).pack(fill="x", padx=4, pady=(0, 8))

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        self.destroy()


# ── Área ──────────────────────────────────────────────────────────────────────

class AreaFormOverlay(_BaseFormOverlay):
    def __init__(self, parent, row: dict | None, on_close=None):
        is_edit = row is not None
        super().__init__(parent, t("areas.edit_area") if is_edit else t("areas.new_area"),
                         on_close=on_close)
        self._row = row

        # Cargar unidades activas para el dropdown
        unidades = fetch_all(
            "SELECT idUnidadAcademica, nombreUnidadAcademica FROM unidad_academica "
            "WHERE estado='activo' ORDER BY nombreUnidadAcademica"
        )
        _no_unit = t("areas.no_unidad")
        self._unidad_opts = [_no_unit] + [u["nombreUnidadAcademica"] for u in unidades]
        self._unidad_map = {_no_unit: None}
        self._unidad_map.update({u["nombreUnidadAcademica"]: u["idUnidadAcademica"] for u in unidades})

        self._nombre_var = tk.StringVar()
        limit_var(self._nombre_var, MAX_AREA_NOMBRE)
        self.e_nombre = self._field(t("areas.field_area_name", n=MAX_AREA_NOMBRE))
        self.e_nombre.configure(textvariable=self._nombre_var)

        self._unidad_var = tk.StringVar(value=_no_unit)
        self._selector(t("areas.field_unidad"), self._unidad_var, self._unidad_opts)

        self._estado_var = tk.StringVar(
            value=row.get("estado", "activo") if row else "activo"
        )
        self._selector(t("common.status"), self._estado_var, ["activo", "inactivo"])

        if is_edit:
            self._nombre_var.set(row.get("nombreArea", ""))
            current_uid = row.get("idUnidadAcademica")
            if current_uid:
                for label, uid in self._unidad_map.items():
                    if uid == current_uid:
                        self._unidad_var.set(label)
                        break

        self._save_btn(self._save)
        if is_edit:
            _is_enable = row.get("estado", "activo") == "inactivo"
            self._delete_btn(self._toggle_status, text=t("common.enable") if _is_enable else t("common.disable"), is_enable=_is_enable)
            self._delete_btn_permanent(self._confirm_delete_area)

    def _save(self) -> None:
        nombre = self._nombre_var.get().strip()
        err = validate_area_nombre(nombre)
        if err:
            self._show_err(err)
            return

        # Unicidad: verificar que no exista otra área con el mismo nombre
        current_id = self._row["idArea"] if self._row else None
        dup = fetch_one(
            "SELECT 1 FROM area_lockers WHERE nombreArea=? AND idArea!=? LIMIT 1"
            if current_id else
            "SELECT 1 FROM area_lockers WHERE nombreArea=? LIMIT 1",
            (nombre, current_id) if current_id else (nombre,),
        )
        if dup:
            self._show_err(f"Ya existe un área con el nombre '{nombre}'")
            return

        unidad_id = self._unidad_map.get(self._unidad_var.get())
        self._clear_err()
        if self._row:
            execute(
                "UPDATE area_lockers SET nombreArea=?, idUnidadAcademica=?, estado=?, "
                "fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), "
                "modificadoPor=1 WHERE idArea=?",
                (nombre, unidad_id, self._estado_var.get(), self._row["idArea"])
            )
        else:
            execute(
                "INSERT INTO area_lockers (nombreArea, idUnidadAcademica, estado, creadoPor) "
                "VALUES (?, ?, ?, 1)",
                (nombre, unidad_id, self._estado_var.get())
            )
        self._close()

    def _toggle_status(self) -> None:
        current_state = (self._row.get("estado") or "activo").strip().lower()
        new_state = "activo" if current_state == "inactivo" else "inactivo"
        execute(
            "UPDATE area_lockers SET estado=?, "
            "fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), "
            "modificadoPor=1 WHERE idArea=?",
            (new_state, self._row["idArea"])
        )
        self._close()

    def _confirm_delete_area(self) -> None:
        area_id = self._row["idArea"]
        count = fetch_one("SELECT COUNT(*) AS n FROM lockers WHERE idArea=?", (area_id,))
        if count and count["n"] > 0:
            messagebox.showwarning(
                "No permitido",
                f"Esta área tiene {count['n']} locker(s) asignado(s). Reasígnalos antes de eliminar.",
            )
            return
        nombre = self._row.get("nombreArea", "")
        if not messagebox.askyesno(
            "Eliminar área",
            f"¿Eliminar permanentemente el área '{nombre}'?\n\nEsta acción no se puede deshacer.",
        ):
            return
        try:
            execute("DELETE FROM area_lockers WHERE idArea=?", (area_id,))
        except Exception:
            messagebox.showerror("Error", "No se pudo eliminar el área. Puede haber dependencias.")
            return
        self._close()


# ── Unidad académica ──────────────────────────────────────────────────────────

class UnidadFormOverlay(_BaseFormOverlay):
    def __init__(self, parent, row: dict | None, on_close=None):
        is_edit = row is not None
        super().__init__(parent,
                         t("areas.edit_unit") if is_edit else t("areas.new_unit"),
                         on_close=on_close)
        self._row = row
        self._nombre_var = tk.StringVar()
        limit_var(self._nombre_var, MAX_UNIDAD_NOMBRE)

        self.e_nombre = self._field(t("areas.field_unit_name", n=MAX_UNIDAD_NOMBRE))
        self.e_nombre.configure(textvariable=self._nombre_var)

        self._estado_var = tk.StringVar(
            value=row.get("estado", "activo") if row else "activo"
        )
        self._selector(t("common.status"), self._estado_var, ["activo", "inactivo"])

        if is_edit:
            self._nombre_var.set(row.get("nombreUnidadAcademica", ""))

        self._save_btn(self._save)
        if is_edit:
            _is_enable = row.get("estado", "activo") == "inactivo"
            self._delete_btn(self._toggle_status, text=t("common.enable") if _is_enable else t("common.disable"), is_enable=_is_enable)
            self._delete_btn_permanent(self._confirm_delete_unidad)

    def _save(self) -> None:
        nombre = self._nombre_var.get().strip()
        err = validate_unidad_nombre(nombre)
        if err:
            self._show_err(err)
            return

        # Unicidad: nombre de unidad
        current_id = self._row["idUnidadAcademica"] if self._row else None
        dup = fetch_one(
            "SELECT 1 FROM unidad_academica WHERE nombreUnidadAcademica=? AND idUnidadAcademica!=? LIMIT 1"
            if current_id else
            "SELECT 1 FROM unidad_academica WHERE nombreUnidadAcademica=? LIMIT 1",
            (nombre, current_id) if current_id else (nombre,),
        )
        if dup:
            self._show_err(f"Ya existe una unidad con el nombre '{nombre}'")
            return

        self._clear_err()
        if self._row:
            execute(
                "UPDATE unidad_academica SET nombreUnidadAcademica=?, "
                "estado=?, fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), "
                "modificadoPor=1 WHERE idUnidadAcademica=?",
                (nombre, self._estado_var.get(), self._row["idUnidadAcademica"])
            )
        else:
            execute(
                "INSERT INTO unidad_academica (nombreUnidadAcademica, estado, creadoPor) "
                "VALUES (?, ?, 1)",
                (nombre, self._estado_var.get())
            )
        self._close()

    def _toggle_status(self) -> None:
        current_state = (self._row.get("estado") or "activo").strip().lower()
        new_state = "activo" if current_state == "inactivo" else "inactivo"
        execute(
            "UPDATE unidad_academica SET estado=?, "
            "fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), "
            "modificadoPor=1 WHERE idUnidadAcademica=?",
            (new_state, self._row["idUnidadAcademica"])
        )
        self._close()

    def _confirm_delete_unidad(self) -> None:
        uid = self._row["idUnidadAcademica"]
        ur = fetch_one(
            "SELECT COUNT(*) AS n FROM usuarios WHERE idUnidadAcademica=? AND estado != 'eliminado'",
            (uid,),
        )
        if ur and ur["n"] > 0:
            messagebox.showwarning(
                "No permitido",
                f"Esta unidad tiene {ur['n']} usuario(s) activos. Reasígnalos antes de eliminar.",
            )
            return
        nombre = self._row.get("nombreUnidadAcademica", "")
        if not messagebox.askyesno(
            "Eliminar unidad",
            f"¿Eliminar permanentemente '{nombre}'?\n\nEsta acción no se puede deshacer.",
        ):
            return
        try:
            execute("DELETE FROM unidad_academica WHERE idUnidadAcademica=?", (uid,))
        except Exception:
            messagebox.showerror("Error", "No se pudo eliminar la unidad. Puede haber dependencias.")
            return
        self._close()


# ══ Historial de Accesos (pantalla independiente) ═════════════════════════════

_MOTIVO_LABELS: dict[str, str] = {
    "facial":               "Facial",
    "no_reconocido":        "Rostro no reconocido",
    "pin":                  "PIN",
    "pin_incorrecto":       "PIN incorrecto",
    "limite_intentos_pin":  "Exceso de intentos PIN",
    "matricula_incorrecta": "Matrícula incorrecta",
    "sin_asignacion":       "Sin asignación de locker",
}


class AccessHistoryScreen(ctk.CTkFrame):
    """Pantalla dedicada al historial de accesos del sistema."""

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._build_ui()

    def _build_ui(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64, corner_radius=0)
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
            hdr, text=t("cat.types.label"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=4)

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=PALETTE["BG"],
            scrollbar_button_color=PALETTE["BORDER"],
            scrollbar_button_hover_color=PALETTE["ACCENT"],
        )
        self._list_frame.pack(fill="both", expand=True, padx=10, pady=8)

    def _load(self) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()
        rows = fetch_all("SELECT * FROM v_historial_detalle LIMIT 200")
        if not rows:
            ctk.CTkLabel(self._list_frame, text=t("hist.no_records"),
                         font=ctk.CTkFont(size=16),
                         text_color=PALETTE["MUTED"],
                         fg_color="transparent").pack(pady=40)
            return
        for r in rows:
            self._make_row(r)

    def _make_row(self, r: dict) -> None:
        concedido = (r.get("accesoPermitido") or "no").strip().lower() == "si"
        dot_color = "#27ae60" if concedido else PALETTE["DANGER"]

        fecha = r.get("fechaHoraAcceso", "")
        if fecha and "T" in fecha:
            fecha = fecha.replace("T", "  ")

        usuario = (r.get("nombreCompleto") or "").strip() or t("hist.unknown_user")
        matricula = r.get("matricula")
        usuario_label = f"{usuario}  ({t('common.matr_prefix')} {matricula})" if matricula else usuario

        locker_num = r.get("idLocker")
        locker_label = f"Locker {locker_num}" if locker_num else "—"

        motivo_raw = (r.get("motivo") or "").strip()
        motivo_label = _MOTIVO_LABELS.get(motivo_raw, motivo_raw or "—")
        resultado = t("hist.granted") if concedido else t("hist.denied")

        row_frame = ctk.CTkFrame(self._list_frame, fg_color=PALETTE["CARD"],
                                 corner_radius=12, border_width=1,
                                 border_color=PALETTE["BORDER"])
        row_frame.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(row_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        inner.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(inner, text="●", font=ctk.CTkFont(size=14),
                     text_color=dot_color, fg_color="transparent").grid(
                         row=0, column=0, rowspan=2, padx=(0, 10))

        ctk.CTkLabel(inner, text=f"{resultado}  ·  {locker_label}  ·  {motivo_label}",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=dot_color, fg_color="transparent",
                     anchor="w").grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(inner, text=f"{usuario_label}  ·  {fecha}",
                     font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"], fg_color="transparent",
                     anchor="w").grid(row=1, column=1, sticky="ew")

    def _go_back(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    def on_show(self, **_kwargs) -> None:
        self._load()
