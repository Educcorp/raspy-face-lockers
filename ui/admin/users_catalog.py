"""
UsersCatalogScreen – Catálogo de usuarios (480×800 px, touch-friendly).

Funcionalidades:
  • Lista scrolleable con datos básicos (nombre, matrícula, tipo, estado)
  • Toque en fila → detalle completo + opciones CRUD
  • Botón "Editar" → formulario de edición inline
  • Botón "Eliminar" → confirmación antes de borrar (solo inactiva al usuario)
  • Botón "+" redirige al wizard de registro con cámara
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from database.connection import fetch_all
from services import user_service
from ui.admin_app import PALETTE
from auth.session import (
    can_create_users,
    can_edit_catalogs,
    get_current_user_id,
    is_superadmin,
    normalize_user_type_name,
    ROLE_SUPERADMIN,
)
from utils.validators import (
    validate_name, validate_matricula, validate_email, validate_tel,
    limit_var, MAX_NOMBRE, MAX_APELLIDO, MAX_EMAIL, MAX_TEL,
)


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
            hdr, text="Usuarios",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=4)

        can_register = can_create_users()
        ctk.CTkButton(
            hdr, text="+", width=46, height=46,
            font=ctk.CTkFont(size=22),
            fg_color=PALETTE["ACCENT"] if can_register else PALETTE["BORDER"],
            hover_color=PALETTE["ACCENT_HOVER"] if can_register else PALETTE["BORDER"],
            text_color=PALETTE["WHITE"],
            command=self._go_register if can_register else None,
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

        # Determinar si está inactivo
        estado = u.get("estado", "activo")
        is_inactive = estado in ["inactivo", "suspendido"]
        
        # Color de fondo para estado inactivo
        row_bg = "#e8e8e8" if is_inactive else PALETTE["CARD"]

        row_frame = ctk.CTkFrame(
            self._list_frame,
            fg_color=row_bg,
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["BORDER"],
            cursor="hand2",
        )
        row_frame.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(row_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        inner.grid_columnconfigure(1, weight=1)

        # Determinar si está inactivo
        estado = u.get("estado", "activo")
        is_inactive = estado in ["inactivo", "suspendido"]
        
        # Colores para estado inactivo
        text_color = "#888888" if is_inactive else PALETTE["TEXT"]
        subtitle_color = "#999999" if is_inactive else PALETTE["MUTED"]
        arrow_color = "#888888" if is_inactive else PALETTE["ACCENT"]

        # Estado dot + indicador
        estado_text = "⊘" if is_inactive else "●"
        ctk.CTkLabel(
            inner, text=estado_text,
            font=ctk.CTkFont(size=14),
            text_color=_estado_color(estado),
            fg_color="transparent",
        ).grid(row=0, column=0, rowspan=2, padx=(0, 10))

        # Nombre + indicador inactivo
        name_text = full_name + (" [INACTIVO]" if is_inactive else "")
        ctk.CTkLabel(
            inner, text=name_text,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=text_color, fg_color="transparent",
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            inner,
            text=f"Matr. {u.get('matricula', '—')}  ·  {u.get('tipo', 'N/A')}  ·  {u.get('estado', '')}",
            font=ctk.CTkFont(size=12),
            text_color=subtitle_color, fg_color="transparent",
            anchor="w",
        ).grid(row=1, column=1, sticky="ew")

        # Flecha
        ctk.CTkLabel(
            inner, text="›",
            font=ctk.CTkFont(size=22),
            text_color=arrow_color, fg_color="transparent",
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
        self._rows = user_service.get_all_users()
        self._filter()

    # ── Navegación ────────────────────────────────────────────────────────────

    def _go_back(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    def _go_register(self) -> None:
        if not can_create_users():
            return
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

class UserDetailOverlay(ctk.CTkFrame):
    """
    Overlay de pantalla completa para detalle + edición de usuario.
    Reemplaza CTkToplevel para compatibilidad con Linux/Raspberry Pi.
    """

    # Límites de caracteres en campos editables
    _LIMITS: dict[str, int] = {
        "nombre":    MAX_NOMBRE,
        "apPaterno": MAX_APELLIDO,
        "apMaterno": MAX_APELLIDO,
        "matricula": 10,
        "emailInst": MAX_EMAIL,
        "tel":       MAX_TEL,
    }

    def __init__(self, parent, controller, user_id: int, on_close=None):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller  = controller
        self.user_id     = user_id
        self._on_close   = on_close
        self._edit_mode  = False
        self._can_edit = can_edit_catalogs()
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()

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
            hdr, text="Editar", width=90, height=40,
            font=ctk.CTkFont(size=14),
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"], command=self._toggle_edit if self._can_edit else None,
        )
        self.btn_edit.pack(side="right", padx=8)
        if not self._can_edit:
            self.btn_edit.configure(text="Solo lectura", fg_color=PALETTE["BORDER"])

        # Scroll area con formulario
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=PALETTE["BG"],
            scrollbar_button_color=PALETTE["BORDER"],
        )
        self._scroll.pack(fill="both", expand=True, padx=14, pady=10)

        # Campos definidos
        self._field_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}
        fields = [
            ("nombre",    f"Nombre  (máx. {MAX_NOMBRE} car.)"),
            ("apPaterno", f"Apellido Paterno  (máx. {MAX_APELLIDO} car.)"),
            ("apMaterno", f"Apellido Materno  (máx. {MAX_APELLIDO} car.)"),
            ("matricula", "Matrícula  (5-10 dígitos)"),
            ("emailInst", f"Correo institucional  (máx. {MAX_EMAIL} car.)"),
            ("tel",       "Teléfono  (opcional, 10-15 dígitos)"),
        ]
        for key, label in fields:
            self._vars[key] = tk.StringVar()
            limit_var(self._vars[key], self._LIMITS.get(key, 200))
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

        # Label de error para validaciones de edición
        self.lbl_err = ctk.CTkLabel(
            self._scroll, text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["DANGER"],
            fg_color="transparent",
            wraplength=430, justify="center",
        )
        self.lbl_err.pack(pady=(4, 0))

        # Botones de acción (mismo patrón visual que panel de Área)
        self.btn_save = ctk.CTkButton(
            self._scroll,
            text="Guardar cambios",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"], height=52, corner_radius=12,
            command=self._save,
        )

        self.btn_reregister_face = ctk.CTkButton(
            self._scroll,
            text="Re-registrar rostro",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#1a5276", hover_color="#154360",
            text_color=PALETTE["WHITE"], height=52, corner_radius=12,
            command=self._reregister_face,
        )
        self.btn_reregister_face.pack(fill="x", padx=4, pady=(0, 8))
        if not self._can_edit:
            self.btn_reregister_face.pack_forget()

        self.btn_delete = ctk.CTkButton(
            self._scroll,
            text="Inhabilitar",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PALETTE["DANGER"], hover_color="#922b21",
            text_color=PALETTE["WHITE"], height=52, corner_radius=12,
            command=self._confirm_delete,
        )
        self.btn_delete.pack(fill="x", padx=4, pady=(0, 8))
        if not self._can_edit:
            self.btn_delete.pack_forget()

        self.btn_delete_permanent = ctk.CTkButton(
            self._scroll,
            text="Eliminar permanentemente",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#6d1a1a", hover_color="#4a0f0f",
            text_color=PALETTE["WHITE"], height=48, corner_radius=12,
            command=self._confirm_delete_permanent,
        )
        self.btn_delete_permanent.pack(fill="x", padx=4, pady=(0, 16))
        if not self._can_edit:
            self.btn_delete_permanent.pack_forget()

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
            button_hover_color=PALETTE["ACCENT_HOVER"],
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
        row = user_service.get_user_by_id(self.user_id)

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

        current_state = (row.get("estado") or "activo").strip().lower()
        is_inactive = current_state == "inactivo"
        target_role = normalize_user_type_name(row.get("tipo"))
        is_target_superadmin = target_role == ROLE_SUPERADMIN
        is_self = get_current_user_id() == self.user_id
        self.btn_delete.configure(
            text="Habilitar" if is_inactive else "Inhabilitar",
            fg_color=PALETTE["SUCCESS"] if is_inactive else PALETTE["DANGER"],
            hover_color="#1e8449" if is_inactive else "#922b21",
        )
        if is_target_superadmin and not is_inactive:
            self.btn_delete.configure(
                text="Protegido",
                state="disabled",
                fg_color=PALETTE["BORDER"],
                hover_color=PALETTE["BORDER"],
            )
        elif is_self and not is_inactive:
            self.btn_delete.configure(
                text="Tu cuenta",
                state="disabled",
                fg_color=PALETTE["BORDER"],
                hover_color=PALETTE["BORDER"],
            )
        else:
            self.btn_delete.configure(state="normal")

        if self._can_edit:
            blocked = is_target_superadmin or is_self
            self.btn_delete_permanent.configure(
                state="disabled" if blocked else "normal",
                fg_color=PALETTE["BORDER"] if blocked else "#6d1a1a",
                hover_color=PALETTE["BORDER"] if blocked else "#4a0f0f",
            )

        n = user_service.count_face_encodings(self.user_id)
        self.face_badge.configure(
            text=f"[OK] {n} perfil(es) facial(es) registrado(s)"
                 if n else "(!) Sin rostro registrado",
            text_color=PALETTE["ACCENT"] if n else PALETTE["WARN"] if "WARN" in PALETTE else "#d4a034",
        )

    def _save(self) -> None:
        if not self._can_edit:
            return

        nombre    = self._vars["nombre"].get().strip()
        apPaterno = self._vars["apPaterno"].get().strip()
        apMaterno = self._vars["apMaterno"].get().strip() or None
        mat       = self._vars["matricula"].get().strip()
        email     = self._vars["emailInst"].get().strip().lower()
        tel       = self._vars["tel"].get().strip() or None

        # ── Validaciones de formato / longitud ────────────────────────────────
        err = validate_name(nombre, "Nombre")
        if err:
            self.lbl_err.configure(text=err, text_color=PALETTE["DANGER"])
            return

        err = validate_name(apPaterno, "Apellido paterno")
        if err:
            self.lbl_err.configure(text=err, text_color=PALETTE["DANGER"])
            return

        if apMaterno:
            err = validate_name(apMaterno, "Apellido materno")
            if err:
                self.lbl_err.configure(text=err, text_color=PALETTE["DANGER"])
                return

        err = validate_matricula(mat)
        if err:
            self.lbl_err.configure(text=err, text_color=PALETTE["DANGER"])
            return

        err = validate_email(email)
        if err:
            self.lbl_err.configure(text=err, text_color=PALETTE["DANGER"])
            return

        err = validate_tel(tel or "")
        if err:
            self.lbl_err.configure(text=err, text_color=PALETTE["DANGER"])
            return

        # ── Unicidad: matrícula (excluyendo usuario actual) ───────────────────
        if user_service.matricula_exists(int(mat), exclude_user_id=self.user_id):
            self.lbl_err.configure(
                text=f"La matrícula {mat} ya pertenece a otro usuario",
                text_color=PALETTE["DANGER"],
            )
            return

        # ── Unicidad: correo (excluyendo usuario actual) ──────────────────────
        if user_service.email_exists(email, exclude_user_id=self.user_id):
            self.lbl_err.configure(
                text=f"El correo {email} ya pertenece a otro usuario",
                text_color=PALETTE["DANGER"],
            )
            return

        tipo_name   = self._vars["tipo"].get()
        unidad_name = self._vars["unidad"].get()
        tipo_id   = next((t["idTipoUsuario"]     for t in self._tipos    if t["nombreTipoUsuario"] == tipo_name),   None)
        unidad_id = next((u["idUnidadAcademica"] for u in self._unidades if u["nombreUnidadAcademica"] == unidad_name), None)

        if not tipo_id or not unidad_id:
            self.lbl_err.configure(
                text="Selecciona un tipo de usuario y unidad académica válidos",
                text_color=PALETTE["DANGER"],
            )
            return

        self.lbl_err.configure(text="")
        try:
            user_service.update_user(self.user_id, {
                "nombre":            nombre,
                "apPaterno":         apPaterno,
                "apMaterno":         apMaterno,
                "matricula":         int(mat),
                "emailInst":         email,
                "tel":               tel,
                "idTipoUsuario":     tipo_id,
                "idUnidadAcademica": unidad_id,
                "estado":            self._vars["estado"].get(),
            })
        except Exception as exc:
            self.lbl_err.configure(
                text=f"Error al guardar: {str(exc)[:80]}",
                text_color=PALETTE["DANGER"],
            )
            return
        self._set_edit_mode(False)
        self._load_user()

    def _confirm_delete(self) -> None:
        if not self._can_edit:
            return
        current_state = (self._vars["estado"].get() or "activo").strip().lower()
        activating = current_state == "inactivo"
        _ConfirmDialog(
            self,
            message=(
                "¿Habilitar este usuario?\nSu acceso quedará activo nuevamente."
                if activating else
                "¿Inhabilitar este usuario?\nSu acceso quedará desactivado."
            ),
            on_confirm=self._do_delete,
        )

    def _do_delete(self) -> None:
        if not self._can_edit:
            return

        if get_current_user_id() == self.user_id:
            messagebox.showwarning("Acción no permitida", "No puedes deshabilitar tu propia cuenta.")
            return

        target_role = normalize_user_type_name(self._user.get("tipo"))
        if target_role == ROLE_SUPERADMIN:
            messagebox.showwarning("Acción no permitida", "No se puede deshabilitar una cuenta Superadmin.")
            return

        current_state = (self._vars["estado"].get() or "activo").strip().lower()
        new_state = "activo" if current_state == "inactivo" else "inactivo"
        try:
            user_service.set_user_status(self.user_id, new_state)
        except Exception:
            messagebox.showerror("Error", "No se pudo cambiar el estado del usuario.")
            return
        self.after(0, self._close)

    def _confirm_delete_permanent(self) -> None:
        if not self._can_edit:
            return
        target_role = normalize_user_type_name(self._user.get("tipo"))
        if target_role == ROLE_SUPERADMIN:
            messagebox.showwarning("Acción no permitida",
                                   "No se puede eliminar una cuenta Superadmin.")
            return
        if get_current_user_id() == self.user_id:
            messagebox.showwarning("Acción no permitida",
                                   "No puedes eliminar tu propia cuenta.")
            return
        full_name = f"{self._user.get('nombre', '')} {self._user.get('apPaterno', '')}"
        _ConfirmDialog(
            self,
            message=(
                f"¿Eliminar permanentemente a {full_name.strip()}?\n\n"
                "Se eliminarán sus datos biométricos y asignaciones.\n"
                "Esta acción no se puede deshacer."
            ),
            on_confirm=self._do_delete_permanent,
        )

    def _do_delete_permanent(self) -> None:
        if not self._can_edit:
            return
        try:
            user_service.delete_user_permanent(self.user_id)
        except Exception:
            messagebox.showerror("Error", "No se pudo eliminar al usuario.")
            return
        self.after(0, self._close)

    # ── Modo edición ──────────────────────────────────────────────────────────

    def _toggle_edit(self) -> None:
        if not self._can_edit:
            return
        self._set_edit_mode(not self._edit_mode)

    def _set_edit_mode(self, active: bool) -> None:
        if not self._can_edit:
            active = False
        self._edit_mode = active
        state = "normal" if active else "disabled"
        for w in self._field_widgets.values():
            w.configure(state=state)
        btn_color = PALETTE["ACCENT_HOVER"] if active else PALETTE["BORDER"]
        self.btn_edit.configure(
            text="Cancelar" if active else "Editar",
            fg_color=btn_color,
        )
        if active:
            self.btn_save.pack(fill="x", padx=4, pady=(16, 8), before=self.btn_delete)
        else:
            self.btn_save.pack_forget()

    def _reregister_face(self) -> None:
        """Navega al flujo de captura facial para actualizar el rostro del usuario."""
        if not self._can_edit:
            return
        nombre_var = self._vars.get("nombre", None)
        nombre_str = nombre_var.get().strip() if nombre_var else ""
        _ConfirmDialog(
            self,
            message=(
                f"¿Actualizar el rostro de {nombre_str or 'este usuario'}?\n\n"
                "Se capturarán 3 nuevas poses y los perfiles\n"
                "faciales anteriores serán reemplazados."
            ),
            on_confirm=self._do_reregister_face,
        )

    def _do_reregister_face(self) -> None:
        nombre_var = self._vars.get("nombre", None)
        nombre_str = nombre_var.get().strip() if nombre_var else ""
        from ui.admin.register_user import RegisterUserScreen
        reg_screen = self.controller._frames.get(RegisterUserScreen)
        if reg_screen is None:
            return
        self._close()
        reg_screen.start_reregister(self.user_id, nombre_str)
        self.controller.show_frame(RegisterUserScreen)

    def _close(self) -> None:
        if not self.winfo_exists():
            return
        if self._on_close:
            self._on_close()
        self.destroy()


# ── Diálogo de confirmación reutilizable ──────────────────────────────────────

class _ConfirmDialog(ctk.CTkFrame):
    """Diálogo de confirmación como overlay en-ventana (compatible Linux/RPi)."""

    def __init__(self, parent, message: str, on_confirm):
        root = parent.winfo_toplevel()
        super().__init__(root, fg_color=PALETTE["BG"], corner_radius=0)
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()

        # Tarjeta centrada — width/height van al constructor, no a place()
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
            btn_row, text="Cancelar", height=52,
            fg_color=PALETTE["BORDER"], hover_color=PALETTE["MUTED"],
            text_color=PALETTE["TEXT"],
            command=self.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Confirmar", height=52,
            fg_color=PALETTE["DANGER"], hover_color="#922b21",
            text_color=PALETTE["WHITE"],
            command=lambda: (on_confirm(), self.destroy()),
        ).pack(side="right", expand=True, fill="x", padx=(6, 0))
