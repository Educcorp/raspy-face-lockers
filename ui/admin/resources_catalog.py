"""
ResourcesCatalogScreen – Catálogo de recursos compartidos (480×800 px, touch-friendly).

Equivalente en la Pi de /recursos/catalogo en la web (webapp/blueprints/
resources_bp.py + webapp/services/resource_service.py) — antes este módulo
solo existía en la web; el panel admin de la Pi no tenía forma de dar de
alta/editar un recurso, así que había que hacerlo desde una computadora aparte
aunque el resto de la administración ya se pudiera hacer desde el kiosco.

Mismo patrón visual y de permisos que ui/admin/lockers_catalog.py: crear/
editar/estado los puede hacer cualquier admin (can_edit_catalogs), eliminar
queda reservado a Superadmin. Contra la misma BD remota que todo lo demás
(database.connection), sin capa aparte.
"""

import customtkinter as ctk
import tkinter as tk

from database.connection import fetch_all, fetch_one, execute, db_session
from ui.admin_app import PALETTE, get_icon
from ui.i18n import t
from auth.session import can_edit_catalogs, is_superadmin
from utils.validators import validate_recurso_nombre, validate_recurso_descripcion


def _estado_badge(estado: str) -> tuple[str, str]:
    labels = {
        "es": {"activo": "Activo", "inactivo": "Inactivo"},
        "en": {"activo": "Active", "inactivo": "Inactive"},
    }
    from ui.i18n import get_lang
    lang = get_lang()
    label = labels.get(lang, labels["es"]).get(estado, "?")
    colors = {"activo": "#27ae60", "inactivo": PALETTE["MUTED"]}
    return f"●  {label}", colors.get(estado, PALETTE["MUTED"])


class ResourcesCatalogScreen(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._search_var = tk.StringVar()
        self._rows: list[dict] = []
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
            hdr, text=t("resources.title"),
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

        sf = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=12, height=48)
        sf.pack(fill="x", padx=14, pady=(12, 6))
        sf.pack_propagate(False)
        _ic = get_icon("search", size=17, color=PALETTE["MUTED"])
        ctk.CTkLabel(sf, image=_ic, text="", fg_color="transparent").pack(side="left", padx=10)
        entry = ctk.CTkEntry(
            sf, textvariable=self._search_var,
            placeholder_text=t("resources.search_placeholder"),
            fg_color="transparent", border_width=0,
            text_color=PALETTE["TEXT"], font=ctk.CTkFont(size=15),
        )
        entry.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self._search_var.trace_add("write", lambda *_: self._filter())

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
        is_inactive = r.get("estado") == "inactivo"

        row_bg = "#e8e8e8" if is_inactive else PALETTE["CARD"]
        text_color = "#888888" if is_inactive else PALETTE["TEXT"]
        subtitle_color = "#999999" if is_inactive else PALETTE["MUTED"]

        row_frame = ctk.CTkFrame(self._list_frame, fg_color=row_bg,
                                  corner_radius=12, border_width=1,
                                  border_color=PALETTE["BORDER"], cursor="hand2")
        row_frame.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(row_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        inner.grid_columnconfigure(0, weight=1)

        nombre_text = r.get("nombre") or "—"
        if is_inactive:
            nombre_text += f" {t('common.inactive_badge')}"
        ctk.CTkLabel(inner, text=nombre_text,
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=text_color, fg_color="transparent",
                     anchor="w").grid(row=0, column=0, sticky="ew")

        area = r.get("nombrearea") or t("areas.no_area")
        unidad = r.get("nombreunidadacademica") or "—"
        ctk.CTkLabel(inner, text=f"{area} · {unidad}",
                     font=ctk.CTkFont(size=12),
                     text_color=subtitle_color, fg_color="transparent",
                     anchor="w").grid(row=1, column=0, sticky="ew")

        ctk.CTkLabel(inner, text=badge_text,
                     font=ctk.CTkFont(size=12),
                     text_color=badge_color, fg_color="transparent",
                     ).grid(row=0, column=1, rowspan=2, padx=(10, 0))

        rid = r["idrecurso"]
        for w in [row_frame, inner] + inner.winfo_children():
            w.bind("<Button-1>", lambda e, i=rid: self._open_detail(i))

    def _filter(self) -> None:
        q = self._search_var.get().lower()
        if not q:
            self._render_rows(self._rows)
            return
        self._render_rows([
            r for r in self._rows
            if q in (r.get("nombre", "") or "").lower()
            or q in (r.get("nombrearea", "") or "").lower()
            or q in (r.get("nombreunidadacademica", "") or "").lower()
        ])

    def _load(self) -> None:
        self._rows = fetch_all("""
            SELECT r.idRecurso AS idrecurso, r.nombre, r.descripcion, r.estado,
                   r.idUnidadAcademica AS idunidadacademica, r.idArea AS idarea,
                   ua.nombreUnidadAcademica AS nombreunidadacademica,
                   a.nombreArea AS nombrearea
            FROM recursos r
            LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = r.idUnidadAcademica
            LEFT JOIN area_lockers a ON a.idArea = r.idArea
            ORDER BY r.nombre
        """)
        self._filter()

    def _go_back(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    def _open_create(self) -> None:
        if not can_edit_catalogs():
            return
        ResourceCreateOverlay(self, on_close=self._load)

    def _open_detail(self, recurso_id: int) -> None:
        ResourceDetailOverlay(self, recurso_id, on_close=self._load)

    def on_show(self, **_kwargs) -> None:
        self._load()


# ── Diálogos overlay (mismo patrón que ui/admin/lockers_catalog.py) ──────────

class _AlertDialog(ctk.CTkFrame):
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
            card, text=message, font=ctk.CTkFont(size=15),
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
            card, text=message, font=ctk.CTkFont(size=15),
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


# ── Detalle / edición ──────────────────────────────────────────────────────

class ResourceDetailOverlay(ctk.CTkFrame):
    """Overlay de pantalla completa para ver/editar un recurso existente."""

    def __init__(self, parent, recurso_id: int, on_close=None):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self.recurso_id = recurso_id
        self._on_close = on_close
        self._can_edit = can_edit_catalogs()
        self._unidades: list[dict] = []
        self._areas: list[dict] = []
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkButton(hdr, text="←", width=46, height=46,
                      font=ctk.CTkFont(size=22, weight="bold"),
                      fg_color="transparent", hover_color=PALETTE["BORDER"],
                      text_color=PALETTE["TEXT"], command=self._close,
                      ).pack(side="left", padx=8)
        ctk.CTkLabel(hdr, text=t("resources.detail_title"),
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=PALETTE["TEXT"],
                     fg_color="transparent").pack(side="left", padx=4)

        scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
        scroll.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(scroll, text=t("resources.field_name"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._nombre_var = tk.StringVar()
        self._nombre_entry = ctk.CTkEntry(
            scroll, textvariable=self._nombre_var,
            fg_color=PALETTE["CARD"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._nombre_entry.pack(fill="x", padx=4)

        ctk.CTkLabel(scroll, text=t("resources.field_desc"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._desc_var = tk.StringVar()
        self._desc_entry = ctk.CTkEntry(
            scroll, textvariable=self._desc_var,
            fg_color=PALETTE["CARD"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._desc_entry.pack(fill="x", padx=4)

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

        ctk.CTkLabel(scroll, text=t("common.status"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._estado_var = tk.StringVar()
        self._estado_menu = ctk.CTkOptionMenu(
            scroll, variable=self._estado_var, values=["activo", "inactivo"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._estado_menu.pack(fill="x", padx=4)

        self._lbl_err = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=13),
                                      text_color=PALETTE["DANGER"], fg_color="transparent",
                                      wraplength=380)
        self._lbl_err.pack(pady=(8, 0))

        if not self._can_edit:
            for w in (self._nombre_entry, self._desc_entry, self._unidad_menu,
                      self._area_menu, self._estado_menu):
                w.configure(state="disabled")

        if self._can_edit:
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
                    scroll, text=t("resources.delete_btn"),
                    font=ctk.CTkFont(size=15, weight="bold"),
                    fg_color="#8B1A1A", hover_color="#6B0000",
                    text_color=PALETTE["WHITE"], height=50, corner_radius=12,
                    command=self._confirm_delete,
                ).pack(fill="x", padx=4, pady=(0, 8))
        else:
            self.btn_toggle = None

    def _on_unit_change(self) -> None:
        unit_name = self._unidad_var.get()
        unit = next((u for u in self._unidades if u["nombreunidadacademica"] == unit_name), None)
        if unit:
            self._areas = fetch_all(
                'SELECT idArea AS idarea, nombreArea AS nombrearea FROM area_lockers '
                "WHERE idUnidadAcademica=%s AND estado='activo' ORDER BY nombreArea",
                (unit["idunidadacademica"],),
            )
        else:
            self._areas = []
        area_names = [a["nombrearea"] for a in self._areas]
        self._area_menu.configure(values=area_names if area_names else ["—"])
        if self._area_var.get() not in area_names:
            self._area_var.set(area_names[0] if area_names else "—")

    def _load(self) -> None:
        row = fetch_one("""
            SELECT r.idRecurso AS idrecurso, r.nombre, r.descripcion, r.estado,
                   ua.nombreUnidadAcademica AS nombreunidadacademica,
                   a.nombreArea AS nombrearea
            FROM recursos r
            LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = r.idUnidadAcademica
            LEFT JOIN area_lockers a ON a.idArea = r.idArea
            WHERE r.idRecurso=%s
        """, (self.recurso_id,))
        if not row:
            self._close()
            return

        self._nombre_var.set(row.get("nombre") or "")
        self._desc_var.set(row.get("descripcion") or "")

        self._unidades = fetch_all(
            'SELECT idUnidadAcademica AS idunidadacademica, '
            'nombreUnidadAcademica AS nombreunidadacademica FROM unidad_academica '
            "WHERE estado='activo' ORDER BY nombreUnidadAcademica"
        )
        unit_names = [u["nombreunidadacademica"] for u in self._unidades]
        self._unidad_menu.configure(values=unit_names if unit_names else ["—"])

        current_unidad = row.get("nombreunidadacademica") or ""
        if current_unidad and current_unidad in unit_names:
            self._unidad_var.set(current_unidad)
        elif unit_names:
            self._unidad_var.set(unit_names[0])
        else:
            self._unidad_var.set("—")

        current_area = row.get("nombrearea") or ""
        area_names = [a["nombrearea"] for a in self._areas]
        if current_area and current_area in area_names:
            self._area_var.set(current_area)
        elif area_names:
            self._area_var.set(area_names[0])

        self._estado_var.set(row.get("estado", "activo"))
        self._refresh_toggle_button()

    def _refresh_toggle_button(self) -> None:
        if not self.btn_toggle:
            return
        is_inactive = (self._estado_var.get() or "activo").strip().lower() == "inactivo"
        self.btn_toggle.configure(
            text=t("common.enable") if is_inactive else t("common.disable"),
            fg_color=PALETTE["SUCCESS"] if is_inactive else PALETTE["DANGER"],
            hover_color="#1e8449" if is_inactive else "#922b21",
        )

    def _validate_fields(self, nombre: str, descripcion: str | None,
                          unit: dict | None, area: dict | None) -> str | None:
        err = validate_recurso_nombre(nombre) or validate_recurso_descripcion(descripcion or "")
        if err:
            return err
        if not unit or not area:
            return t("resources.err_unit_area")
        existing = fetch_one(
            "SELECT 1 FROM recursos WHERE nombre=%s AND idRecurso!=%s LIMIT 1",
            (nombre, self.recurso_id),
        )
        if existing:
            return t("resources.err_duplicate", nombre=nombre)
        return None

    def _save(self) -> None:
        if not self._can_edit:
            return
        nombre = self._nombre_var.get().strip()
        descripcion = self._desc_var.get().strip() or None
        unit = next((u for u in self._unidades
                     if u["nombreunidadacademica"] == self._unidad_var.get()), None)
        area = next((a for a in self._areas
                     if a["nombrearea"] == self._area_var.get()), None)
        new_state = (self._estado_var.get() or "activo").strip()

        err = self._validate_fields(nombre, descripcion, unit, area)
        if err:
            self._lbl_err.configure(text=err)
            return

        execute(
            "UPDATE recursos SET nombre=%s, descripcion=%s, idUnidadAcademica=%s, "
            "idArea=%s, estado=%s, modificadoPor=1 WHERE idRecurso=%s",
            (nombre, descripcion, unit["idunidadacademica"], area["idarea"],
             new_state, self.recurso_id),
        )
        self._close()

    def _toggle_status(self) -> None:
        if not self._can_edit:
            return
        current = (self._estado_var.get() or "activo").strip().lower()
        self._estado_var.set("activo" if current == "inactivo" else "inactivo")
        self._refresh_toggle_button()
        self._save()

    def _confirm_delete(self) -> None:
        if not is_superadmin():
            return
        _ConfirmDialog(
            self,
            t("resources.confirm_delete", nombre=self._nombre_var.get()),
            on_confirm=self._do_delete,
        )

    def _do_delete(self) -> None:
        # recurso_uso.idRecurso es ON DELETE RESTRICT (candado de concurrencia,
        # ver webapp/schema.sql): hay que borrar las sesiones de uso antes de
        # poder borrar el recurso — mismo tipo de bug que bloqueaba eliminar
        # usuarios con una sesión de recurso sin terminar (services/
        # user_service.py::delete_user_permanent). recurso_autorizados sí es
        # ON DELETE CASCADE, no hace falta borrarlo a mano.
        with db_session() as conn:
            conn.execute("DELETE FROM recurso_uso WHERE idRecurso=%s", (self.recurso_id,))
            conn.execute("DELETE FROM recursos WHERE idRecurso=%s", (self.recurso_id,))
        self._close()

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        self.destroy()


# ── Formulario nuevo recurso ──────────────────────────────────────────────

class ResourceCreateOverlay(ctk.CTkFrame):

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
        ctk.CTkLabel(hdr, text=t("resources.create_title"),
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=PALETTE["TEXT"],
                     fg_color="transparent").pack(side="left", padx=4)

        scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
        scroll.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(scroll, text=t("resources.field_name"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._nombre_var = tk.StringVar()
        ctk.CTkEntry(
            scroll, textvariable=self._nombre_var,
            fg_color=PALETTE["CARD"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        ).pack(fill="x", padx=4)

        ctk.CTkLabel(scroll, text=t("resources.field_desc"), font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._desc_var = tk.StringVar()
        ctk.CTkEntry(
            scroll, textvariable=self._desc_var,
            fg_color=PALETTE["CARD"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        ).pack(fill="x", padx=4)

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

        self._lbl_err = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=13),
                                      text_color=PALETTE["DANGER"], fg_color="transparent",
                                      wraplength=380)
        self._lbl_err.pack(pady=(8, 0))

        ctk.CTkButton(
            scroll, text=t("resources.create_btn"),
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"], height=52, corner_radius=12,
            command=self._save,
        ).pack(fill="x", padx=4, pady=(16, 8))

    def _load_catalogs(self) -> None:
        self._unidades = fetch_all(
            'SELECT idUnidadAcademica AS idunidadacademica, '
            'nombreUnidadAcademica AS nombreunidadacademica FROM unidad_academica '
            "WHERE estado='activo' ORDER BY nombreUnidadAcademica"
        )
        unit_names = [u["nombreunidadacademica"] for u in self._unidades]
        self._unidad_menu.configure(values=unit_names if unit_names else ["—"])
        self._unidad_var.set(unit_names[0] if unit_names else "—")

    def _on_unit_change(self) -> None:
        unit_name = self._unidad_var.get()
        unit = next((u for u in self._unidades if u["nombreunidadacademica"] == unit_name), None)
        if unit:
            self._areas = fetch_all(
                'SELECT idArea AS idarea, nombreArea AS nombrearea FROM area_lockers '
                "WHERE idUnidadAcademica=%s AND estado='activo' ORDER BY nombreArea",
                (unit["idunidadacademica"],),
            )
        else:
            self._areas = []
        area_names = [a["nombrearea"] for a in self._areas]
        self._area_menu.configure(values=area_names if area_names else ["—"])
        self._area_var.set(area_names[0] if area_names else "—")

    def _save(self) -> None:
        nombre = self._nombre_var.get().strip()
        descripcion = self._desc_var.get().strip() or None
        unit = next((u for u in self._unidades
                     if u["nombreunidadacademica"] == self._unidad_var.get()), None)
        area = next((a for a in self._areas
                     if a["nombrearea"] == self._area_var.get()), None)

        err = validate_recurso_nombre(nombre) or validate_recurso_descripcion(descripcion or "")
        if not err and (not unit or not area):
            err = t("resources.err_unit_area")
        if not err and fetch_one("SELECT 1 FROM recursos WHERE nombre=%s LIMIT 1", (nombre,)):
            err = t("resources.err_duplicate", nombre=nombre)
        if err:
            self._lbl_err.configure(text=err)
            return

        try:
            execute(
                "INSERT INTO recursos (nombre, descripcion, idUnidadAcademica, idArea, creadoPor) "
                "VALUES (%s, %s, %s, %s, 1)",
                (nombre, descripcion, unit["idunidadacademica"], area["idarea"]),
            )
        except Exception as exc:
            self._lbl_err.configure(text=f"{t('common.error_generic')}: {str(exc)[:80]}")
            return
        self._close()

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        self.destroy()
