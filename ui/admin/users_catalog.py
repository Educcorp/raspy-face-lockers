"""
UsersCatalogScreen – Catálogo de usuarios (480×800 px, touch-friendly).

Funcionalidades:
  • Lista scrolleable con datos básicos (nombre, matrícula, tipo, estado)
  • Toque en fila → detalle completo + opciones CRUD
  • Botón "Editar" → formulario de edición inline
  • Botón "Eliminar" → confirmación antes de borrar (solo inactiva al usuario)
  • Botón "+" redirige al wizard de registro con cámara
"""

import hashlib
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from database.connection import fetch_all, fetch_one, execute
from ui.admin_app import PALETTE


# ── Helpers de estilo ─────────────────────────────────────────────────────────

def _estado_color(estado: str) -> str:
    return {
        "activo":     PALETTE["SUCCESS"] if "SUCCESS" in PALETTE else "#27ae60",
        "inactivo":   PALETTE["MUTED"],
        "suspendido": PALETTE["WARN"] if "WARN" in PALETTE else "#d4a034",
    }.get(estado, PALETTE["MUTED"])


# ── Pantalla lista ────────────────────────────────────────────────────────────

class UsersCatalogScreen(ctk.CTkFrame):
    """Lista principal de usuarios con búsqueda y acceso a detalle."""

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._search_var = tk.StringVar()
        self._rows: list[dict] = []
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

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
            hdr, text="👤  Usuarios",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            hdr, text="➕", width=46, height=46,
            font=ctk.CTkFont(size=22),
            fg_color=PALETTE["ACCENT"], hover_color="#268f8a",
            text_color=PALETTE["WHITE"],
            command=self._go_register,
        ).pack(side="right", padx=8)

        # Search
        search_frame = ctk.CTkFrame(self, fg_color=PALETTE["CARD"],
                                    corner_radius=12, height=48)
        search_frame.pack(fill="x", padx=14, pady=(12, 6))
        search_frame.pack_propagate(False)

        ctk.CTkLabel(search_frame, text="🔍", fg_color="transparent",
                     text_color=PALETTE["MUTED"],
                     font=ctk.CTkFont(size=18)).pack(side="left", padx=10)

        entry = ctk.CTkEntry(
            search_frame, textvariable=self._search_var,
            placeholder_text="Buscar por nombre o matrícula…",
            fg_color="transparent", border_width=0,
            text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15),
        )
        entry.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self._search_var.trace_add("write", lambda *_: self._filter())

        # Lista
        list_container = ctk.CTkFrame(self, fg_color="transparent")
        list_container.pack(fill="both", expand=True, padx=10, pady=4)

        self._list_frame = ctk.CTkScrollableFrame(
            list_container,
            fg_color=PALETTE["BG"],
            scrollbar_button_color=PALETTE["BORDER"],
            scrollbar_button_hover_color=PALETTE["ACCENT"],
        )
        self._list_frame.pack(fill="both", expand=True)

    def _render_rows(self, rows: list[dict]) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()

        if not rows:
            ctk.CTkLabel(
                self._list_frame,
                text="Sin resultados",
                font=ctk.CTkFont(size=16),
                text_color=PALETTE["MUTED"],
                fg_color="transparent",
            ).pack(pady=40)
            return

        for u in rows:
            self._make_row(u)

    def _make_row(self, u: dict) -> None:
        full_name = f"{u['nombre']} {u['apPaterno']}"
        if u.get("apMaterno"):
            full_name += f" {u['apMaterno']}"

        row_frame = ctk.CTkFrame(
            self._list_frame,
            fg_color=PALETTE["CARD"],
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["BORDER"],
            cursor="hand2",
        )
        row_frame.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(row_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        inner.grid_columnconfigure(1, weight=1)

        # Estado dot
        ctk.CTkLabel(
            inner, text="●",
            font=ctk.CTkFont(size=14),
            text_color=_estado_color(u.get("estado", "activo")),
            fg_color="transparent",
        ).grid(row=0, column=0, rowspan=2, padx=(0, 10))

        ctk.CTkLabel(
            inner, text=full_name,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            inner,
            text=f"Matr. {u.get('matricula', '—')}  ·  {u.get('tipo', 'N/A')}  ·  {u.get('estado', '')}",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"], fg_color="transparent",
            anchor="w",
        ).grid(row=1, column=1, sticky="ew")

        # Flecha
        ctk.CTkLabel(
            inner, text="›",
            font=ctk.CTkFont(size=22),
            text_color=PALETTE["ACCENT"], fg_color="transparent",
        ).grid(row=0, column=2, rowspan=2, padx=(10, 0))

        # Bind táctil
        uid = u["idUsuario"]
        for w in [row_frame, inner] + inner.winfo_children():
            w.bind("<Button-1>", lambda e, i=uid: self._open_detail(i))

    def _filter(self) -> None:
        q = self._search_var.get().lower().strip()
        if not q:
            filtered = self._rows
        else:
            filtered = [
                r for r in self._rows
                if q in f"{r['nombre']} {r['apPaterno']}".lower()
                or q in str(r.get("matricula", ""))
            ]
        self._render_rows(filtered)

    # ── Carga de datos ────────────────────────────────────────────────────────

    def _load(self) -> None:
        self._rows = fetch_all("""
            SELECT u.idUsuario, u.nombre, u.apPaterno, u.apMaterno,
                   u.matricula, u.emailInst, u.tel, u.estado,
                   t.nombreTipoUsuario AS tipo,
                   ua.nombreUnidadAcademica AS unidad
            FROM usuarios u
            LEFT JOIN tipo_usuarios t  ON t.idTipoUsuario = u.idTipoUsuario
            LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = u.idUnidadAcademica
            ORDER BY u.nombre, u.apPaterno
        """)
        self._filter()

    # ── Navegación ────────────────────────────────────────────────────────────

    def _go_back(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    def _go_register(self) -> None:
        from ui.admin.register_user import RegisterUserScreen
        self.controller.show_frame(RegisterUserScreen)

    def _open_detail(self, user_id: int) -> None:
        UserDetailOverlay(self, self.controller, user_id,
                          on_close=self._load)

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def on_show(self, **_kwargs) -> None:
        self._load()

    def on_hide(self) -> None:
        self._search_var.set("")


# ── Detalle / edición de usuario ──────────────────────────────────────────────

class UserDetailOverlay(ctk.CTkToplevel):
    """
    Ventana de detalle + edición de un usuario.
    Se muestra como ventana modal sobre la pantalla de lista.
    Tamaño: 480×800 (igual que la pantalla del locker).
    """

    def __init__(self, parent, controller, user_id: int, on_close=None):
        super().__init__(parent)
        self.controller  = controller
        self.user_id     = user_id
        self._on_close   = on_close
        self._edit_mode  = False

        self.title("Detalle de Usuario")
        self.geometry("480x800")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["BG"])
        self.grab_set()   # modal

        self._vars: dict[str, tk.StringVar] = {}
        self._user: dict = {}
        self._tipos: list[dict] = []
        self._unidades: list[dict] = []

        self._load_catalogs()
        self._build_ui()
        self._load_user()

    def _load_catalogs(self) -> None:
        self._tipos = fetch_all(
            "SELECT idTipoUsuario, nombreTipoUsuario FROM tipo_usuarios WHERE estado='activo'"
        )
        self._unidades = fetch_all(
            "SELECT idUnidadAcademica, nombreUnidadAcademica FROM unidad_academica WHERE estado='activo'"
        )

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
            text_color=PALETTE["TEXT"], command=self._close,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            hdr, text="Detalle de Usuario",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=4)

        self.btn_edit = ctk.CTkButton(
            hdr, text="✏️  Editar", width=90, height=40,
            font=ctk.CTkFont(size=14),
            fg_color=PALETTE["ACCENT"], hover_color="#268f8a",
            text_color=PALETTE["WHITE"], command=self._toggle_edit,
        )
        self.btn_edit.pack(side="right", padx=8)

        # Scroll area con formulario
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=PALETTE["BG"],
            scrollbar_button_color=PALETTE["BORDER"],
        )
        self._scroll.pack(fill="both", expand=True, padx=14, pady=10)

        # Campos definidos
        self._field_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}
        fields = [
            ("nombre",    "Nombre"),
            ("apPaterno", "Apellido Paterno"),
            ("apMaterno", "Apellido Materno"),
            ("matricula", "Matrícula"),
            ("emailInst", "Correo institucional"),
            ("tel",       "Teléfono"),
        ]
        for key, label in fields:
            self._vars[key] = tk.StringVar()
            self._make_field(label, key)

        # Selectores
        self._vars["tipo"]   = tk.StringVar()
        self._vars["unidad"] = tk.StringVar()
        self._make_selector("Tipo de usuario", "tipo",
                            [t["nombreTipoUsuario"] for t in self._tipos])
        self._make_selector("Unidad académica", "unidad",
                            [u["nombreUnidadAcademica"] for u in self._unidades])

        # Estado
        self._vars["estado"] = tk.StringVar()
        self._make_selector("Estado", "estado",
                            ["activo", "inactivo", "suspendido"])

        # Face badge
        self.face_badge = ctk.CTkLabel(
            self._scroll, text="Sin rostro registrado",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["MUTED"], fg_color="transparent",
        )
        self.face_badge.pack(anchor="w", padx=4, pady=(6, 0))

        # Botones de acción
        self._action_frame = ctk.CTkFrame(self, fg_color=PALETTE["CARD"],
                                          corner_radius=0, height=80)
        self._action_frame.pack(fill="x")
        self._action_frame.pack_propagate(False)

        self.btn_save = ctk.CTkButton(
            self._action_frame,
            text="💾  Guardar cambios",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PALETTE["ACCENT"], hover_color="#268f8a",
            text_color=PALETTE["WHITE"], height=52, corner_radius=12,
            command=self._save,
        )
        self.btn_save.pack(side="left", expand=True, fill="both",
                           padx=(12, 6), pady=14)

        self.btn_delete = ctk.CTkButton(
            self._action_frame,
            text="🗑  Inhabilitar",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PALETTE["DANGER"], hover_color="#922b21",
            text_color=PALETTE["WHITE"], height=52, corner_radius=12,
            command=self._confirm_delete,
        )
        self.btn_delete.pack(side="right", expand=True, fill="both",
                             padx=(6, 12), pady=14)

        self._set_edit_mode(False)

    def _make_field(self, label: str, key: str) -> None:
        ctk.CTkLabel(
            self._scroll, text=label,
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"], fg_color="transparent",
        ).pack(anchor="w", padx=4, pady=(8, 2))

        entry = ctk.CTkEntry(
            self._scroll,
            textvariable=self._vars[key],
            font=ctk.CTkFont(size=15),
            fg_color=PALETTE["CARD"],
            border_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            height=46,
        )
        entry.pack(fill="x", padx=4)
        self._field_widgets[key] = entry

    def _make_selector(self, label: str, key: str, values: list[str]) -> None:
        ctk.CTkLabel(
            self._scroll, text=label,
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["MUTED"], fg_color="transparent",
        ).pack(anchor="w", padx=4, pady=(8, 2))

        menu = ctk.CTkOptionMenu(
            self._scroll,
            variable=self._vars[key],
            values=values,
            fg_color=PALETTE["CARD"],
            button_color=PALETTE["ACCENT"],
            button_hover_color="#268f8a",
            text_color=PALETTE["TEXT"],
            dropdown_fg_color=PALETTE["CARD"],
            dropdown_text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15),
            height=46,
        )
        menu.pack(fill="x", padx=4)
        self._field_widgets[key] = menu

    # ── Carga y guardado ──────────────────────────────────────────────────────

    def _load_user(self) -> None:
        row = fetch_one("""
            SELECT u.*, t.nombreTipoUsuario AS tipo,
                   ua.nombreUnidadAcademica AS unidad
            FROM usuarios u
            LEFT JOIN tipo_usuarios t  ON t.idTipoUsuario = u.idTipoUsuario
            LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = u.idUnidadAcademica
            WHERE u.idUsuario = ?
        """, (self.user_id,))

        if not row:
            self._close()
            return
        self._user = row

        self._vars["nombre"].set(row.get("nombre", ""))
        self._vars["apPaterno"].set(row.get("apPaterno", ""))
        self._vars["apMaterno"].set(row.get("apMaterno", "") or "")
        self._vars["matricula"].set(str(row.get("matricula", "")))
        self._vars["emailInst"].set(row.get("emailInst", ""))
        self._vars["tel"].set(row.get("tel", "") or "")
        self._vars["tipo"].set(row.get("tipo", ""))
        self._vars["unidad"].set(row.get("unidad", ""))
        self._vars["estado"].set(row.get("estado", "activo"))

        # Verificar si tiene rostro
        face_count = fetch_one(
            "SELECT COUNT(*) AS n FROM encoding WHERE idUsuario=? AND estado='activo'",
            (self.user_id,)
        )
        n = face_count["n"] if face_count else 0
        self.face_badge.configure(
            text=f"✅ {n} perfil(es) facial(es) registrado(s)"
                 if n else "⚠️  Sin rostro registrado",
            text_color=PALETTE["ACCENT"] if n else PALETTE["WARN"] if "WARN" in PALETTE else "#d4a034",
        )

    def _save(self) -> None:
        # Resolver FK de tipo y unidad
        tipo_name   = self._vars["tipo"].get()
        unidad_name = self._vars["unidad"].get()
        tipo_id   = next((t["idTipoUsuario"]      for t in self._tipos   if t["nombreTipoUsuario"] == tipo_name),   None)
        unidad_id = next((u["idUnidadAcademica"]  for u in self._unidades if u["nombreUnidadAcademica"] == unidad_name), None)

        if not tipo_id or not unidad_id:
            return  # datos incompletos

        execute("""
            UPDATE usuarios SET
                nombre=?, apPaterno=?, apMaterno=?,
                matricula=?, emailInst=?, tel=?,
                idTipoUsuario=?, idUnidadAcademica=?,
                estado=?,
                fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'),
                modificadoPor=1
            WHERE idUsuario=?
        """, (
            self._vars["nombre"].get().strip(),
            self._vars["apPaterno"].get().strip(),
            self._vars["apMaterno"].get().strip() or None,
            self._vars["matricula"].get().strip(),
            self._vars["emailInst"].get().strip(),
            self._vars["tel"].get().strip() or None,
            tipo_id, unidad_id,
            self._vars["estado"].get(),
            self.user_id,
        ))
        self._set_edit_mode(False)
        self._load_user()

    def _confirm_delete(self) -> None:
        _ConfirmDialog(
            self,
            message="¿Inhabilitar este usuario?\nSu acceso quedará desactivado.",
            on_confirm=self._do_delete,
        )

    def _do_delete(self) -> None:
        execute(
            "UPDATE usuarios SET estado='inactivo', modificadoPor=1 WHERE idUsuario=?",
            (self.user_id,),
        )
        self._close()

    # ── Modo edición ──────────────────────────────────────────────────────────

    def _toggle_edit(self) -> None:
        self._set_edit_mode(not self._edit_mode)

    def _set_edit_mode(self, active: bool) -> None:
        self._edit_mode = active
        state = "normal" if active else "disabled"
        for w in self._field_widgets.values():
            w.configure(state=state)
        btn_color = "#268f8a" if active else PALETTE["BORDER"]
        self.btn_edit.configure(
            text="✖  Cancelar" if active else "✏️  Editar",
            fg_color=btn_color,
        )
        if active:
            self.btn_save.pack(side="left", expand=True, fill="both",
                               padx=(12, 6), pady=14)
        else:
            self.btn_save.pack_forget()

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        self.destroy()


# ── Diálogo de confirmación reutilizable ──────────────────────────────────────

class _ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent, message: str, on_confirm):
        super().__init__(parent)
        self.title("Confirmar")
        self.geometry("360x220")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["CARD"])
        self.grab_set()

        ctk.CTkLabel(
            self, text=message,
            font=ctk.CTkFont(size=15),
            text_color=PALETTE["TEXT"], fg_color="transparent",
            wraplength=320,
        ).pack(pady=(28, 14))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            btn_row, text="Cancelar", height=50,
            fg_color=PALETTE["BORDER"], hover_color="#2a3a5a",
            text_color=PALETTE["TEXT"],
            command=self.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Confirmar", height=50,
            fg_color=PALETTE["DANGER"], hover_color="#922b21",
            text_color=PALETTE["WHITE"],
            command=lambda: (on_confirm(), self.destroy()),
        ).pack(side="right", expand=True, fill="x", padx=(6, 0))
