"""
ResourceAuthorizationScreen – usuarios autorizados a activar cada recurso
compartido (480×800 px, touch-friendly).

Equivalente en la Pi de /recursos/autorizaciones en la web (webapp/blueprints/
resources_bp.py) — antes esto solo se podía hacer desde el panel web; el
kiosco no tenía forma de autorizar/retirar usuarios de un recurso.

A diferencia de la asignación de lockers (1 usuario por locker), un recurso
puede tener varios usuarios autorizados y un usuario puede estar autorizado en
varios recursos (recurso_autorizados es una relación N a N) — solo se puede
autorizar a usuarios cuyo permisoActivacion sea 'recurso_compartido' o 'ambos'
(services/resource_service.py::is_user_authorized aplica esa misma regla en
el kiosco al activar un recurso).
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from auth.session import can_edit_catalogs
from database.connection import execute, fetch_all, fetch_one
from ui.admin_app import PALETTE
from ui.i18n import t


class ResourceAuthorizationScreen(ctk.CTkFrame):
    """Gestión de usuarios autorizados por recurso."""

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._can_edit = can_edit_catalogs()

        self._recursos: list[dict] = []
        self._authorized: list[dict] = []
        self._authorizable: list[dict] = []

        self._recurso_var = tk.StringVar()
        self._recurso_var.trace_add("write", lambda *_: self._on_recurso_change())
        self._authorizable_var = tk.StringVar()

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
            hdr, text=t("resource_auth.title"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
        ).pack(side="left", padx=4)

        body = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
        body.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(
            body, text=t("resource_auth.resource_label"),
            font=ctk.CTkFont(size=12), text_color=PALETTE["MUTED"],
            fg_color="transparent",
        ).pack(anchor="w", padx=4, pady=(2, 2))

        self.menu_recurso = ctk.CTkOptionMenu(
            body, variable=self._recurso_var,
            values=[t("resource_auth.no_resources")],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=48,
        )
        self.menu_recurso.pack(fill="x", padx=4)

        # ── Autorizar un usuario nuevo ────────────────────────────────────────
        ctk.CTkLabel(
            body, text=t("resource_auth.authorize_label"),
            font=ctk.CTkFont(size=14, weight="bold"), text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=4, pady=(18, 6))

        self.menu_authorizable = ctk.CTkOptionMenu(
            body, variable=self._authorizable_var,
            values=[t("resource_auth.no_authorizable")],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=15), height=48,
        )
        self.menu_authorizable.pack(fill="x", padx=4)

        self.btn_authorize = ctk.CTkButton(
            body, text=t("resource_auth.btn_authorize"),
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"], height=50, corner_radius=12,
            command=self._authorize_selected,
        )
        self.btn_authorize.pack(fill="x", padx=4, pady=(10, 4))

        self.lbl_feedback = ctk.CTkLabel(
            body, text="", font=ctk.CTkFont(size=13),
            text_color=PALETTE["MUTED"], fg_color="transparent",
        )
        self.lbl_feedback.pack(anchor="w", padx=4, pady=(2, 0))

        # ── Usuarios ya autorizados ───────────────────────────────────────────
        ctk.CTkLabel(
            body, text=t("resource_auth.authorized_section"),
            font=ctk.CTkFont(size=14, weight="bold"), text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w", padx=4, pady=(18, 6))

        self.authorized_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.authorized_frame.pack(fill="both", expand=True)

        if not self._can_edit:
            self.menu_recurso.configure(state="disabled")
            self.menu_authorizable.configure(state="disabled")
            self.btn_authorize.configure(state="disabled")
            self.lbl_feedback.configure(text=t("assignment.no_permission"))

    def _go_back(self) -> None:
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    # ── Etiquetas ─────────────────────────────────────────────────────────────

    @staticmethod
    def _recurso_label(row: dict) -> str:
        area = row.get("nombrearea") or t("areas.no_area")
        return f"{row.get('nombre')} · {area}"

    @staticmethod
    def _user_label(row: dict) -> str:
        full_name = " ".join(
            p for p in [row.get("nombre"), row.get("appaterno"), row.get("apmaterno")] if p
        ).strip()
        return f"{full_name} · {t('common.matr_prefix')} {row.get('matricula')}"

    def _selected_recurso(self) -> dict | None:
        selected = self._recurso_var.get()
        return next((r for r in self._recursos if self._recurso_label(r) == selected), None)

    def _selected_authorizable(self) -> dict | None:
        selected = self._authorizable_var.get()
        return next((u for u in self._authorizable if self._user_label(u) == selected), None)

    # ── Carga de datos ────────────────────────────────────────────────────────

    def _load_recursos(self) -> None:
        self._recursos = fetch_all("""
            SELECT r.idRecurso AS idrecurso, r.nombre, a.nombreArea AS nombrearea
            FROM recursos r
            LEFT JOIN area_lockers a ON a.idArea = r.idArea
            WHERE r.estado = 'activo'
            ORDER BY r.nombre
        """)
        labels = [self._recurso_label(r) for r in self._recursos]
        self.menu_recurso.configure(values=labels or [t("resource_auth.no_resources")])
        if labels and self._recurso_var.get() not in labels:
            self._recurso_var.set(labels[0])
        elif not labels:
            self._recurso_var.set(t("resource_auth.no_resources"))
            self._render_authorized()

    def _on_recurso_change(self) -> None:
        self._load_authorized_and_authorizable()

    def _load_authorized_and_authorizable(self) -> None:
        recurso = self._selected_recurso()
        recurso_id = recurso["idrecurso"] if recurso else None

        if recurso_id is None:
            self._authorized = []
            self._authorizable = []
        else:
            self._authorized = fetch_all("""
                SELECT ra.idRecursoAutorizado AS idrecursoautorizado, ra.fechaHoraReg AS fechahorareg,
                       u.idUsuario AS idusuario, u.nombre, u.apPaterno AS appaterno,
                       u.apMaterno AS apmaterno, u.matricula
                FROM recurso_autorizados ra
                JOIN usuarios u ON u.idUsuario = ra.idUsuario
                WHERE ra.idRecurso = %s AND ra.estado = 'activo' AND u.estado = 'activo'
                ORDER BY u.nombre, u.apPaterno
            """, (recurso_id,))

            self._authorizable = fetch_all("""
                SELECT u.idUsuario AS idusuario, u.nombre, u.apPaterno AS appaterno,
                       u.apMaterno AS apmaterno, u.matricula
                FROM usuarios u
                WHERE u.estado = 'activo'
                  AND u.permisoActivacion IN ('recurso_compartido', 'ambos')
                  AND u.idUsuario NOT IN (
                      SELECT idUsuario FROM recurso_autorizados
                      WHERE idRecurso = %s AND estado = 'activo'
                  )
                ORDER BY u.nombre, u.apPaterno
            """, (recurso_id,))

        authorizable_labels = [self._user_label(u) for u in self._authorizable]
        self.menu_authorizable.configure(
            values=authorizable_labels or [t("resource_auth.no_authorizable")]
        )
        self._authorizable_var.set(
            authorizable_labels[0] if authorizable_labels else t("resource_auth.no_authorizable")
        )

        self._render_authorized()

    def _render_authorized(self) -> None:
        for w in self.authorized_frame.winfo_children():
            w.destroy()

        if not self._authorized:
            ctk.CTkLabel(
                self.authorized_frame, text=t("resource_auth.no_authorized"),
                font=ctk.CTkFont(size=14), text_color=PALETTE["MUTED"],
                fg_color="transparent", wraplength=380, justify="center",
            ).pack(pady=16)
            return

        for row in self._authorized:
            full_name = " ".join(
                p for p in [row.get("nombre"), row.get("appaterno"), row.get("apmaterno")] if p
            ).strip()

            card = ctk.CTkFrame(
                self.authorized_frame, fg_color=PALETTE["CARD"], corner_radius=12,
                border_width=1, border_color=PALETTE["BORDER"],
            )
            card.pack(fill="x", padx=4, pady=4)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)
            inner.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                inner, text=full_name, font=ctk.CTkFont(size=14, weight="bold"),
                text_color=PALETTE["TEXT"], fg_color="transparent", anchor="w",
            ).grid(row=0, column=0, sticky="ew")

            ctk.CTkLabel(
                inner, text=f"{t('common.matr_prefix')} {row.get('matricula')}",
                font=ctk.CTkFont(size=12), text_color=PALETTE["MUTED"],
                fg_color="transparent", anchor="w",
            ).grid(row=1, column=0, sticky="ew")

            if self._can_edit:
                ctk.CTkButton(
                    inner, text=t("resource_auth.btn_revoke"),
                    font=ctk.CTkFont(size=13, weight="bold"),
                    fg_color=PALETTE["DANGER"], hover_color="#922b21",
                    text_color=PALETTE["WHITE"], width=90, height=38, corner_radius=10,
                    command=lambda auth_id=row["idrecursoautorizado"]: self._revoke(auth_id),
                ).grid(row=0, column=1, rowspan=2, padx=(10, 0))

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _authorize_selected(self) -> None:
        if not self._can_edit:
            return
        recurso = self._selected_recurso()
        user = self._selected_authorizable()
        if not recurso or not user:
            self.lbl_feedback.configure(
                text=t("resource_auth.err_select"), text_color=PALETTE["DANGER"],
            )
            return

        recurso_id = recurso["idrecurso"]
        user_id = user["idusuario"]

        existing = fetch_one(
            "SELECT idRecursoAutorizado AS idrecursoautorizado FROM recurso_autorizados "
            "WHERE idRecurso=%s AND idUsuario=%s",
            (recurso_id, user_id),
        )
        if existing:
            execute(
                "UPDATE recurso_autorizados SET estado='activo', modificadoPor=1 "
                "WHERE idRecursoAutorizado=%s",
                (existing["idrecursoautorizado"],),
            )
        else:
            execute(
                "INSERT INTO recurso_autorizados (idRecurso, idUsuario, creadoPor) "
                "VALUES (%s, %s, 1)",
                (recurso_id, user_id),
            )

        self.lbl_feedback.configure(
            text=t("resource_auth.ok_authorized"), text_color=PALETTE["SUCCESS"],
        )
        self._load_authorized_and_authorizable()

    def _revoke(self, auth_id: int) -> None:
        if not self._can_edit:
            return
        execute(
            "UPDATE recurso_autorizados SET estado='inactivo', modificadoPor=1 "
            "WHERE idRecursoAutorizado=%s",
            (auth_id,),
        )
        self.lbl_feedback.configure(
            text=t("resource_auth.ok_revoked"), text_color=PALETTE["SUCCESS"],
        )
        self._load_authorized_and_authorizable()

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self, **_kwargs) -> None:
        self.lbl_feedback.configure(text="", text_color=PALETTE["MUTED"])
        self._load_recursos()
        self._load_authorized_and_authorizable()
