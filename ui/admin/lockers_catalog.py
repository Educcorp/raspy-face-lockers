"""
LockersCatalogScreen – Catálogo de lockers (480×800 px, touch-friendly).

Lista todos los lockers con su área, unidad y estado.
Al tocar uno → overlay de detalle con edición de estado.
Botón "+" → formulario para crear un nuevo locker.
"""

import customtkinter as ctk
import tkinter as tk
from database.connection import fetch_all, fetch_one, execute
from ui.admin_app import PALETTE


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
            hdr, text="🔒  Lockers",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            hdr, text="➕", width=46, height=46,
            font=ctk.CTkFont(size=22),
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"],
            command=self._new_locker,
        ).pack(side="right", padx=8)

        # Búsqueda
        sf = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=12, height=48)
        sf.pack(fill="x", padx=14, pady=(12, 6))
        sf.pack_propagate(False)
        ctk.CTkLabel(sf, text="🔍", fg_color="transparent",
                     text_color=PALETTE["MUTED"],
                     font=ctk.CTkFont(size=18)).pack(side="left", padx=10)
        entry = ctk.CTkEntry(
            sf, textvariable=self._search_var,
            placeholder_text="Buscar por área o ID…",
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

        row_frame = ctk.CTkFrame(self._list_frame, fg_color=PALETTE["CARD"],
                                 corner_radius=12, border_width=1,
                                 border_color=PALETTE["BORDER"], cursor="hand2")
        row_frame.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(row_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        inner.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(inner, text=f"#  {r['idLocker']}",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=PALETTE["ACCENT"], fg_color="transparent",
                     ).grid(row=0, column=0, rowspan=2, padx=(0, 14))

        ctk.CTkLabel(inner, text=f"Área: {r.get('area', '—')}",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=PALETTE["TEXT"], fg_color="transparent",
                     anchor="w").grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(inner, text=f"{r.get('unidad', '—')}",
                     font=ctk.CTkFont(size=12),
                     text_color=PALETTE["MUTED"], fg_color="transparent",
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

    def _new_locker(self) -> None:
        LockerFormOverlay(self, on_close=self._load)

    def on_show(self, **_kwargs) -> None:
        self._load()


# ── Detalle Locker ────────────────────────────────────────────────────────────

class LockerDetailOverlay(ctk.CTkToplevel):
    def __init__(self, parent, locker_id: int, on_close=None):
        super().__init__(parent)
        self.locker_id = locker_id
        self._on_close = on_close
        self.title("Detalle Locker")
        self.geometry("480x560")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["BG"])
        self.grab_set()
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
        btn_row = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=74,
                               corner_radius=0)
        btn_row.pack(fill="x")
        btn_row.pack_propagate(False)
        ctk.CTkButton(btn_row, text="💾  Guardar estado",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
                      text_color=PALETTE["WHITE"], height=50, corner_radius=12,
                      command=self._save).pack(fill="x", padx=14, pady=12)

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

        asign = fetch_one("""
            SELECT u.nombre || ' ' || u.apPaterno AS usuario,
                   al.estado AS asignEstado
            FROM asignacion_locker al
            JOIN usuarios u ON u.idUsuario = al.idUsuario
            WHERE al.idLocker=? AND al.estado='activo'
        """, (self.locker_id,))
        if asign:
            self.lbl_asign.configure(
                text=f"✅ {asign['usuario']}  ({asign['asignEstado']})")
        else:
            self.lbl_asign.configure(text="Sin asignación activa")

    def _save(self) -> None:
        execute(
            "UPDATE lockers SET estado=?, fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), modificadoPor=1 WHERE idLocker=?",
            (self._estado_var.get(), self.locker_id),
        )
        self._close()

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        self.destroy()


# ── Formulario nuevo locker ───────────────────────────────────────────────────

class LockerFormOverlay(ctk.CTkToplevel):
    def __init__(self, parent, on_close=None):
        super().__init__(parent)
        self._on_close = on_close
        self.title("Nuevo Locker")
        self.geometry("480x420")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["BG"])
        self.grab_set()

        self._areas: list[dict] = fetch_all(
            "SELECT idArea, nombreArea FROM area_lockers ORDER BY nombreArea"
        )
        self._unidades: list[dict] = fetch_all(
            "SELECT idUnidadAcademica, nombreUnidadAcademica FROM unidad_academica ORDER BY nombreUnidadAcademica"
        )
        self._area_var   = tk.StringVar()
        self._unidad_var = tk.StringVar()
        self._estado_var = tk.StringVar(value="activo")
        self._build_ui()

    def _build_ui(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkButton(hdr, text="←", width=46, height=46,
                      font=ctk.CTkFont(size=22, weight="bold"),
                      fg_color="transparent", hover_color=PALETTE["BORDER"],
                      text_color=PALETTE["TEXT"],
                      command=self.destroy).pack(side="left", padx=8)
        ctk.CTkLabel(hdr, text="Nuevo Locker",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=PALETTE["TEXT"],
                     fg_color="transparent").pack(side="left", padx=4)

        frm = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
        frm.pack(fill="both", expand=True, padx=14, pady=10)

        def selector(label, var, values):
            ctk.CTkLabel(frm, text=label, font=ctk.CTkFont(size=12),
                         text_color=PALETTE["MUTED"],
                         fg_color="transparent").pack(anchor="w", padx=4, pady=(8, 2))
            ctk.CTkOptionMenu(frm, variable=var, values=values,
                              fg_color=PALETTE["CARD"],
                              button_color=PALETTE["ACCENT"],
                              button_hover_color=PALETTE["ACCENT_HOVER"],
                              text_color=PALETTE["TEXT"],
                              font=ctk.CTkFont(size=15), height=46,
                              ).pack(fill="x", padx=4)

        area_names   = [a["nombreArea"]             for a in self._areas]
        unidad_names = [u["nombreUnidadAcademica"]  for u in self._unidades]
        if area_names:
            self._area_var.set(area_names[0])
        if unidad_names:
            self._unidad_var.set(unidad_names[0])

        selector("Área / Zona",      self._area_var,   area_names or ["—"])
        selector("Unidad Académica", self._unidad_var, unidad_names or ["—"])
        selector("Estado",           self._estado_var, ["activo", "inactivo", "mantenimiento"])

        ctk.CTkButton(frm, text="💾  Crear Locker",
                      font=ctk.CTkFont(size=16, weight="bold"),
                      fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
                      text_color=PALETTE["WHITE"], height=52, corner_radius=12,
                      command=self._create).pack(fill="x", padx=4, pady=18)

    def _create(self) -> None:
        area_name   = self._area_var.get()
        unidad_name = self._unidad_var.get()
        area_id   = next((a["idArea"]              for a in self._areas   if a["nombreArea"] == area_name),   None)
        unidad_id = next((u["idUnidadAcademica"]   for u in self._unidades if u["nombreUnidadAcademica"] == unidad_name), None)
        if not area_id or not unidad_id:
            return
        execute("""
            INSERT INTO lockers (idUnidadAcademica, idArea, estado, creadoPor)
            VALUES (?, ?, ?, 1)
        """, (unidad_id, area_id, self._estado_var.get()))
        if self._on_close:
            self._on_close()
        self.destroy()
