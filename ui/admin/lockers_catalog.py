"""
LockersCatalogScreen – Catálogo de lockers (480×800 px, touch-friendly).

Lista todos los lockers con su área, unidad y estado.
Al tocar uno → overlay de detalle con edición de estado.
Botón "+" → formulario para crear un nuevo locker.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from database.connection import fetch_all, fetch_one, execute
from ui.admin_app import PALETTE
from ui.i18n import t
from auth.session import can_edit_catalogs, is_superadmin

# Lockers 1-4 son predeterminados del sistema — no se pueden modificar ni eliminar
_DEFAULT_LOCKER_IDS = frozenset({1, 2, 3, 4})


def _estado_badge(estado: str) -> tuple[str, str]:
    return {
        "activo":        ("●  Activo",       "#27ae60"),
        "inactivo":      ("●  Inactivo",     PALETTE["MUTED"]),
        "mantenimiento": ("●  Mantenimiento", "#d4a034"),
    }.get(estado, ("●  ?", PALETTE["MUTED"]))


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

        # Búsqueda
        sf = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=12, height=48)
        sf.pack(fill="x", padx=14, pady=(12, 6))
        sf.pack_propagate(False)
        ctk.CTkLabel(sf, text="🔍", fg_color="transparent",
                     text_color=PALETTE["MUTED"],
                     font=ctk.CTkFont(size=18)).pack(side="left", padx=10)
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
            ctk.CTkLabel(self._list_frame, text="Sin resultados",
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
        area_text = f"Área: {r.get('area', '—')}"
        if is_inactive:
            area_text += " [INACTIVO]"
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

    def _open_detail(self, locker_id: int) -> None:
        LockerDetailOverlay(self, locker_id, on_close=self._load)

    def on_show(self, **_kwargs) -> None:
        self._load()


# ── Detalle Locker ────────────────────────────────────────────────────────────

class LockerDetailOverlay(ctk.CTkFrame):
    """Overlay de pantalla completa – compatible con Linux/RPi."""

    def __init__(self, parent, locker_id: int, on_close=None):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self.locker_id = locker_id
        self._on_close = on_close
        self._can_edit = can_edit_catalogs()
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
        ctk.CTkLabel(hdr, text="Detalle de Locker",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=PALETTE["TEXT"],
                     fg_color="transparent").pack(side="left", padx=4)

        scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
        scroll.pack(fill="both", expand=True, padx=14, pady=10)

        fields = [
            ("idLocker", "ID Locker"),
            ("area", "Área"),
            ("unidad", "Unidad académica"),
        ]
        self._labels: dict[str, ctk.CTkLabel] = {}
        for key, label in fields:
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12),
                         text_color=PALETTE["MUTED"],
                         fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
            lbl = ctk.CTkLabel(scroll, text="—",
                               font=ctk.CTkFont(size=15, weight="bold"),
                               text_color=PALETTE["TEXT"],
                               fg_color=PALETTE["CARD"], corner_radius=8,
                               height=42)
            lbl.pack(fill="x", padx=4)
            self._labels[key] = lbl

        # Estado selector
        ctk.CTkLabel(scroll, text="Estado", font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
        self._estado_var = tk.StringVar()
        self._estado_menu = ctk.CTkOptionMenu(
            scroll,
            variable=self._estado_var,
            values=["activo", "inactivo", "mantenimiento"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=46,
        )
        self._estado_menu.pack(fill="x", padx=4)
        if not self._can_edit:
            self._estado_menu.configure(state="disabled")

        # Asignación actual
        ctk.CTkLabel(scroll, text="Asignación actual",
                     font=ctk.CTkFont(size=12), text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(anchor="w", padx=4, pady=(12, 2))
        self.lbl_asign = ctk.CTkLabel(scroll, text="—",
                                      font=ctk.CTkFont(size=14),
                                      text_color=PALETTE["TEXT"],
                                      fg_color=PALETTE["CARD"],
                                      corner_radius=8, height=42)
        self.lbl_asign.pack(fill="x", padx=4)

        # Botones
        self.btn_toggle = None
        if int(self.locker_id) in _DEFAULT_LOCKER_IDS:
            # Locker de sistema — bloquear toda edición
            self._estado_menu.configure(state="disabled")
            ctk.CTkLabel(
                scroll,
                text="Locker de sistema — protegido",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#D4A34A",
                fg_color=PALETTE["CARD"],
                corner_radius=8,
                height=40,
            ).pack(fill="x", padx=4, pady=(16, 4))
            ctk.CTkLabel(
                scroll,
                text="Los lockers 1-4 son predeterminados del sistema\ny no pueden modificarse ni eliminarse.",
                font=ctk.CTkFont(size=12),
                text_color=PALETTE["MUTED"],
                fg_color="transparent",
                justify="center",
            ).pack(pady=(0, 8))
        elif self._can_edit:
            ctk.CTkButton(
                scroll,
                text="Guardar estado",
                font=ctk.CTkFont(size=15, weight="bold"),
                fg_color=PALETTE["ACCENT"],
                hover_color=PALETTE["ACCENT_HOVER"],
                text_color=PALETTE["WHITE"],
                height=50,
                corner_radius=12,
                command=self._save,
            ).pack(fill="x", padx=4, pady=(16, 8))

            self.btn_toggle = ctk.CTkButton(
                scroll,
                text="Inhabilitar",
                font=ctk.CTkFont(size=15, weight="bold"),
                fg_color=PALETTE["DANGER"],
                hover_color="#922b21",
                text_color=PALETTE["WHITE"],
                height=50,
                corner_radius=12,
                command=self._toggle_status,
            )
            self.btn_toggle.pack(fill="x", padx=4, pady=(0, 8))

            if is_superadmin():
                ctk.CTkButton(
                    scroll,
                    text="Eliminar locker",
                    font=ctk.CTkFont(size=15, weight="bold"),
                    fg_color="#8B1A1A",
                    hover_color="#6B0000",
                    text_color=PALETTE["WHITE"],
                    height=50,
                    corner_radius=12,
                    command=self._confirm_delete_locker,
                ).pack(fill="x", padx=4, pady=(0, 8))

    def _load(self) -> None:
        row = fetch_one("""
            SELECT l.idLocker, l.estado,
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
        self._labels["idLocker"].configure(text=str(row["idLocker"]))
        self._labels["area"].configure(text=row.get("area", "—") or "—")
        self._labels["unidad"].configure(text=row.get("unidad", "—") or "—")
        self._estado_var.set(row.get("estado", "activo"))
        if self._can_edit:
            self._refresh_toggle_button()

        asign = fetch_one("""
            SELECT u.nombre || ' ' || u.apPaterno AS usuario,
                   al.estado AS asignEstado
            FROM asignacion_locker al
            JOIN usuarios u ON u.idUsuario = al.idUsuario
            WHERE al.idLocker=? AND al.estado='activo'
        """, (self.locker_id,))
        if asign:
            self.lbl_asign.configure(
                text=f"[OK] {asign['usuario']}  ({asign['asignEstado']})")
        else:
            self.lbl_asign.configure(text="Sin asignación activa")

    def _save(self) -> None:
        if not self._can_edit:
            return
        new_state = (self._estado_var.get() or "activo").strip().lower()
        if new_state != "activo" and self._has_active_assignment():
            messagebox.showwarning(
                "Acción no permitida",
                "No puedes deshabilitar un locker con asignación activa. Libéralo primero.",
            )
            return
        execute(
            "UPDATE lockers SET estado=?, fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), modificadoPor=1 WHERE idLocker=?",
            (self._estado_var.get(), self.locker_id),
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
            text="Habilitar" if is_inactive else "Inhabilitar",
            fg_color=PALETTE["SUCCESS"] if is_inactive else PALETTE["DANGER"],
            hover_color="#1e8449" if is_inactive else "#922b21",
        )

    def _toggle_status(self) -> None:
        if not self._can_edit:
            return
        current_state = (self._estado_var.get() or "activo").strip().lower()
        new_state = "activo" if current_state == "inactivo" else "inactivo"
        if new_state != "activo" and self._has_active_assignment():
            messagebox.showwarning(
                "Acción no permitida",
                "No puedes deshabilitar un locker con asignación activa. Libéralo primero.",
            )
            return
        self._estado_var.set(new_state)
        execute(
            "UPDATE lockers SET estado=?, fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), modificadoPor=1 WHERE idLocker=?",
            (new_state, self.locker_id),
        )
        self._close()

    def _confirm_delete_locker(self) -> None:
        if not is_superadmin():
            return
        if int(self.locker_id) in _DEFAULT_LOCKER_IDS:
            messagebox.showwarning("Protegido", "Los lockers predeterminados no pueden eliminarse.")
            return
        if self._has_active_assignment():
            messagebox.showwarning(
                "No permitido",
                "Este locker tiene una asignación activa.\nLibéralo primero en el módulo de Asignaciones.",
            )
            return
        confirmed = messagebox.askyesno(
            "Eliminar locker",
            f"¿Eliminar permanentemente el Locker #{self.locker_id}?\n\n"
            "Se borrarán también sus asignaciones históricas.\n"
            "Esta acción NO se puede deshacer.",
        )
        if not confirmed:
            return
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
