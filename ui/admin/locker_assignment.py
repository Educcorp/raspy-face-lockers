"""Pantalla de asignación manual de lockers para alumnos registrados."""

from __future__ import annotations

import sqlite3
import threading
import tkinter as tk

import customtkinter as ctk

from auth.session import can_edit_catalogs
from database.connection import db_session, fetch_all, fetch_one
from services import locker_service
from ui.admin_app import PALETTE


class LockerAssignmentScreen(ctk.CTkFrame):
	"""Gestión manual de asignaciones alumno → locker."""

	def __init__(self, parent, controller):
		super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
		self.controller = controller
		self._can_edit = can_edit_catalogs()

		self._students: list[dict] = []
		self._lockers: list[dict] = []
		self._assignments: list[dict] = []

		self._student_var = tk.StringVar()
		self._locker_var = tk.StringVar()
		self._assigned_var = tk.StringVar()

		self._build_ui()

	def _build_ui(self) -> None:
		hdr = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], height=64, corner_radius=0)
		hdr.pack(fill="x")
		hdr.pack_propagate(False)

		ctk.CTkButton(
			hdr,
			text="←",
			width=46,
			height=46,
			font=ctk.CTkFont(size=22, weight="bold"),
			fg_color="transparent",
			hover_color=PALETTE["BORDER"],
			text_color=PALETTE["TEXT"],
			command=self._go_back,
		).pack(side="left", padx=8)

		ctk.CTkLabel(
			hdr,
			text="Asignación de Lockers",
			font=ctk.CTkFont(size=19, weight="bold"),
			text_color=PALETTE["TEXT"],
			fg_color="transparent",
		).pack(side="left", padx=4)

		body = ctk.CTkScrollableFrame(self, fg_color=PALETTE["BG"])
		body.pack(fill="both", expand=True, padx=14, pady=12)

		ctk.CTkLabel(
			body,
			text="Usuario (alumno, admin o superadmin)",
			font=ctk.CTkFont(size=12),
			text_color=PALETTE["MUTED"],
			fg_color="transparent",
		).pack(anchor="w", padx=4, pady=(2, 2))

		self.menu_student = ctk.CTkOptionMenu(
			body,
			variable=self._student_var,
			values=["Sin alumnos activos"],
			fg_color=PALETTE["CARD"],
			button_color=PALETTE["ACCENT"],
			button_hover_color=PALETTE["ACCENT_HOVER"],
			text_color=PALETTE["TEXT"],
			font=ctk.CTkFont(size=15),
			height=48,
		)
		self.menu_student.pack(fill="x", padx=4)

		ctk.CTkLabel(
			body,
			text="Locker disponible",
			font=ctk.CTkFont(size=12),
			text_color=PALETTE["MUTED"],
			fg_color="transparent",
		).pack(anchor="w", padx=4, pady=(12, 2))

		self.menu_locker = ctk.CTkOptionMenu(
			body,
			variable=self._locker_var,
			values=["Sin lockers disponibles"],
			fg_color=PALETTE["CARD"],
			button_color=PALETTE["ACCENT"],
			button_hover_color=PALETTE["ACCENT_HOVER"],
			text_color=PALETTE["TEXT"],
			font=ctk.CTkFont(size=15),
			height=48,
		)
		self.menu_locker.pack(fill="x", padx=4)

		ctk.CTkLabel(
			body,
			text="Locker asignado (para liberar)",
			font=ctk.CTkFont(size=12),
			text_color=PALETTE["MUTED"],
			fg_color="transparent",
		).pack(anchor="w", padx=4, pady=(12, 2))

		self.menu_assigned = ctk.CTkOptionMenu(
			body,
			variable=self._assigned_var,
			values=["Sin asignaciones activas"],
			fg_color=PALETTE["CARD"],
			button_color=PALETTE["ACCENT"],
			button_hover_color=PALETTE["ACCENT_HOVER"],
			text_color=PALETTE["TEXT"],
			font=ctk.CTkFont(size=15),
			height=48,
		)
		self.menu_assigned.pack(fill="x", padx=4)

		actions = ctk.CTkFrame(body, fg_color="transparent")
		actions.pack(fill="x", padx=4, pady=(14, 8))
		actions.grid_columnconfigure((0, 1), weight=1)

		self.btn_assign = ctk.CTkButton(
			actions,
			text="Asignar",
			font=ctk.CTkFont(size=15, weight="bold"),
			fg_color=PALETTE["ACCENT"],
			hover_color=PALETTE["ACCENT_HOVER"],
			text_color=PALETTE["WHITE"],
			height=50,
			corner_radius=12,
			command=self._assign_selected,
		)
		self.btn_assign.grid(row=0, column=0, sticky="ew", padx=(0, 6))

		self.btn_release = ctk.CTkButton(
			actions,
			text="Liberar locker",
			font=ctk.CTkFont(size=15, weight="bold"),
			fg_color=PALETTE["DANGER"],
			hover_color="#922b21",
			text_color=PALETTE["WHITE"],
			height=50,
			corner_radius=12,
			command=self._release_selected,
		)
		self.btn_release.grid(row=0, column=1, sticky="ew", padx=(6, 0))

		self.lbl_feedback = ctk.CTkLabel(
			body,
			text="",
			font=ctk.CTkFont(size=13),
			text_color=PALETTE["MUTED"],
			fg_color="transparent",
		)
		self.lbl_feedback.pack(anchor="w", padx=4, pady=(2, 8))

		ctk.CTkLabel(
			body,
			text="Asignaciones activas",
			font=ctk.CTkFont(size=14, weight="bold"),
			text_color=PALETTE["TEXT"],
			fg_color="transparent",
		).pack(anchor="w", padx=4, pady=(6, 6))

		self.assignments_frame = ctk.CTkFrame(body, fg_color="transparent")
		self.assignments_frame.pack(fill="both", expand=True)

		# ── Apertura manual de lockers (solo admin/superadmin) ────────────────
		if self._can_edit:
			ctk.CTkLabel(
				body,
				text="Abrir locker manualmente",
				font=ctk.CTkFont(size=14, weight="bold"),
				text_color=PALETTE["TEXT"],
				fg_color="transparent",
			).pack(anchor="w", padx=4, pady=(18, 6))

			self.manual_open_frame = ctk.CTkFrame(body, fg_color="transparent")
			self.manual_open_frame.pack(fill="x", padx=4, pady=(0, 8))

			self.lbl_manual_feedback = ctk.CTkLabel(
				body,
				text="",
				font=ctk.CTkFont(size=12),
				text_color=PALETTE["MUTED"],
				fg_color="transparent",
			)
			self.lbl_manual_feedback.pack(anchor="w", padx=4, pady=(0, 6))
		else:
			self.manual_open_frame = None
			self.lbl_manual_feedback = None

		if not self._can_edit:
			self.menu_student.configure(state="disabled")
			self.menu_locker.configure(state="disabled")
			self.menu_assigned.configure(state="disabled")
			self.btn_assign.configure(state="disabled")
			self.btn_release.configure(state="disabled")
			self.lbl_feedback.configure(text="Tu rol no permite editar asignaciones")

	def _go_back(self) -> None:
		from ui.admin.dashboard import DashboardScreen

		self.controller.show_frame(DashboardScreen)

	def _student_label(self, row: dict) -> str:
		full_name = " ".join(
			p
			for p in [row.get("nombre"), row.get("apPaterno"), row.get("apMaterno")]
			if p
		).strip()
		return f"{full_name} · Matr. {row.get('matricula')}"

	def _locker_label(self, row: dict) -> str:
		area = row.get("nombreArea") or "Sin área"
		return f"Locker {row.get('idLocker')} · {area}"

	def _assigned_label(self, row: dict) -> str:
		full_name = " ".join(
			p for p in [row.get("nombre"), row.get("apPaterno"), row.get("apMaterno")] if p
		).strip()
		return f"Locker {row.get('idLocker')} · {full_name}"

	def _friendly_error(self, action: str, exc: Exception) -> str:
		if isinstance(exc, sqlite3.IntegrityError):
			return f"No se pudo {action}: conflicto de asignación. Intenta recargar y repetir."
		if isinstance(exc, sqlite3.OperationalError):
			return f"No se pudo {action}: problema de base de datos."
		return f"No se pudo {action}."

	def _load_catalogs(self) -> None:
		# Todos los usuarios activos (sin filtro de tipo — admin también puede tener locker)
		self._students = fetch_all(
			"""
			SELECT
				u.idUsuario,
				u.nombre,
				u.apPaterno,
				u.apMaterno,
				u.matricula,
				t.nombreTipoUsuario AS tipo
			FROM usuarios u
			LEFT JOIN tipo_usuarios t ON t.idTipoUsuario = u.idTipoUsuario
			WHERE u.estado = 'activo'
			ORDER BY u.nombre, u.apPaterno
			"""
		)

		lockers_available = fetch_all(
			"""
			SELECT
				l.idLocker,
				a.nombreArea
			FROM lockers l
			LEFT JOIN area_lockers a ON a.idArea = l.idArea
			WHERE l.estado = 'activo'
			  AND NOT EXISTS (
					SELECT 1
					FROM asignacion_locker al
					WHERE al.idLocker = l.idLocker
					  AND al.estado = 'activo'
			  )
			ORDER BY l.idLocker
			LIMIT 4
			"""
		)

		self._lockers = lockers_available

		student_labels = [self._student_label(row) for row in self._students]
		locker_labels = [self._locker_label(row) for row in self._lockers]

		self.menu_student.configure(values=student_labels or ["Sin usuarios activos"])
		self.menu_locker.configure(values=locker_labels or ["Sin lockers disponibles"])

		self._student_var.set(student_labels[0] if student_labels else "Sin usuarios activos")
		self._locker_var.set(locker_labels[0] if locker_labels else "Sin lockers disponibles")

	def _load_assignments(self) -> None:
		self._assignments = fetch_all(
			"""
			SELECT
				al.idLockerAsignado,
				al.idUsuario,
				al.idLocker,
				u.nombre,
				u.apPaterno,
				u.apMaterno,
				u.matricula,
				al.fechaHoraReg
			FROM asignacion_locker al
			JOIN usuarios u ON u.idUsuario = al.idUsuario
			WHERE al.estado = 'activo'
			ORDER BY al.idLocker
			"""
		)

		assignment_labels = [self._assigned_label(row) for row in self._assignments]
		self.menu_assigned.configure(values=assignment_labels or ["Sin asignaciones activas"])
		self._assigned_var.set(
			assignment_labels[0] if assignment_labels else "Sin asignaciones activas"
		)

		for widget in self.assignments_frame.winfo_children():
			widget.destroy()

		if not self._assignments:
			ctk.CTkLabel(
				self.assignments_frame,
				text="No hay asignaciones activas",
				font=ctk.CTkFont(size=14),
				text_color=PALETTE["MUTED"],
				fg_color="transparent",
			).pack(pady=16)
			return

		for row in self._assignments:
			full_name = " ".join(
				p for p in [row.get("nombre"), row.get("apPaterno"), row.get("apMaterno")] if p
			).strip()

			card = ctk.CTkFrame(
				self.assignments_frame,
				fg_color=PALETTE["CARD"],
				corner_radius=12,
				border_width=1,
				border_color=PALETTE["BORDER"],
			)
			card.pack(fill="x", padx=4, pady=4)

			ctk.CTkLabel(
				card,
				text=f"Locker {row.get('idLocker')}  →  {full_name}",
				font=ctk.CTkFont(size=14, weight="bold"),
				text_color=PALETTE["TEXT"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=12, pady=(10, 0))

			ctk.CTkLabel(
				card,
				text=f"Matr. {row.get('matricula')}  ·  Desde {row.get('fechaHoraReg')}",
				font=ctk.CTkFont(size=12),
				text_color=PALETTE["MUTED"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=12, pady=(2, 10))

	def _selected_student(self) -> dict | None:
		selected = self._student_var.get()
		for row in self._students:
			if self._student_label(row) == selected:
				return row
		return None

	def _selected_locker(self) -> dict | None:
		selected = self._locker_var.get()
		for row in self._lockers:
			if self._locker_label(row) == selected:
				return row
		return None

	def _selected_assignment(self) -> dict | None:
		selected = self._assigned_var.get()
		for row in self._assignments:
			if self._assigned_label(row) == selected:
				return row
		return None

	def _close_active_assignment(self, conn, user_id: int, locker_id: int) -> None:
		"""Cierra asignaciones activas evitando conflicto por restricciones únicas históricas."""
		conn.execute(
			"""
			DELETE FROM asignacion_locker
			WHERE estado='vencido'
			  AND (idUsuario=? OR idLocker=?)
			""",
			(user_id, locker_id),
		)
		conn.execute(
			"""
			UPDATE asignacion_locker
			SET estado='vencido', disponible='si',
				fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'),
				modificadoPor=1
			WHERE idUsuario=? AND estado='activo'
			""",
			(user_id,),
		)
		conn.execute(
			"""
			UPDATE asignacion_locker
			SET estado='vencido', disponible='si',
				fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'),
				modificadoPor=1
			WHERE idLocker=? AND estado='activo'
			""",
			(locker_id,),
		)

	def _assign_selected(self) -> None:
		if not self._can_edit:
			return

		student = self._selected_student()
		locker = self._selected_locker()
		if not student or not locker:
			self.lbl_feedback.configure(
				text="Selecciona alumno y locker disponibles",
				text_color=PALETTE["DANGER"],
			)
			return

		user_id = student["idUsuario"]
		locker_id = locker["idLocker"]

		existing_for_user = fetch_one(
			"SELECT idLocker FROM asignacion_locker WHERE idUsuario=? AND estado='activo'",
			(user_id,),
		)
		if existing_for_user and existing_for_user.get("idLocker") == locker_id:
			self.lbl_feedback.configure(
				text="Ese alumno ya tiene asignado ese locker",
				text_color=PALETTE["WARN"],
			)
			return

		try:
			with db_session() as conn:
				self._close_active_assignment(conn, user_id, locker_id)
				conn.execute(
					"""
					INSERT INTO asignacion_locker
						(idUsuario, idLocker, disponible, estado, creadoPor)
					VALUES (?, ?, 'no', 'activo', 1)
					""",
					(user_id, locker_id),
				)
		except Exception as exc:
			self.lbl_feedback.configure(
				text=self._friendly_error("asignar locker", exc),
				text_color=PALETTE["DANGER"],
			)
			return

		self.lbl_feedback.configure(
			text=f"Locker {locker_id} asignado correctamente",
			text_color=PALETTE["SUCCESS"],
		)
		self._refresh_data()

	def _release_selected(self) -> None:
		if not self._can_edit:
			return

		assignment = self._selected_assignment()
		if not assignment:
			self.lbl_feedback.configure(
				text="Selecciona un locker asignado para liberar",
				text_color=PALETTE["DANGER"],
			)
			return

		locker_id = assignment["idLocker"]
		user_id = assignment["idUsuario"]
		try:
			with db_session() as conn:
				before = conn.execute(
					"SELECT COUNT(*) FROM asignacion_locker WHERE idLocker=? AND estado='activo'",
					(locker_id,),
				).fetchone()[0]
				self._close_active_assignment(conn, user_id, locker_id)
				after = conn.execute(
					"SELECT COUNT(*) FROM asignacion_locker WHERE idLocker=? AND estado='activo'",
					(locker_id,),
				).fetchone()[0]
				updated = 1 if before > after else 0
		except Exception as exc:
			self.lbl_feedback.configure(
				text=self._friendly_error("liberar locker", exc),
				text_color=PALETTE["DANGER"],
			)
			return

		if updated:
			self.lbl_feedback.configure(
				text=f"Locker {locker_id} liberado correctamente",
				text_color=PALETTE["SUCCESS"],
			)
		else:
			self.lbl_feedback.configure(
				text="Ese locker ya no tenía una asignación activa",
				text_color=PALETTE["WARN"],
			)

		self._refresh_data()

	def _refresh_data(self) -> None:
		self._load_catalogs()
		self._load_assignments()

	def _build_manual_open_buttons(self) -> None:
		"""Construye botones de apertura manual, uno por locker activo."""
		if not self._can_edit or self.manual_open_frame is None:
			return
		for widget in self.manual_open_frame.winfo_children():
			widget.destroy()

		lockers = fetch_all(
			"SELECT idLocker FROM lockers WHERE estado='activo' ORDER BY idLocker"
		)
		for i, row in enumerate(lockers):
			lid = int(row["idLocker"])

			btn = ctk.CTkButton(
				self.manual_open_frame,
				text=f"  Locker {lid}",
				font=ctk.CTkFont(size=14, weight="bold"),
				fg_color=PALETTE["ACCENT"],
				hover_color=PALETTE["ACCENT_HOVER"],
				text_color=PALETTE["WHITE"],
				height=48,
				corner_radius=12,
			)
			btn.grid(row=0, column=i, padx=6, pady=4, sticky="ew")

			def _open(l=lid, b=btn) -> None:
				b.configure(state="disabled", fg_color=PALETTE["BORDER"])
				if self.lbl_manual_feedback:
					self.lbl_manual_feedback.configure(
						text=f"Abriendo Locker {l}…", text_color=PALETTE["MUTED"]
					)
				def _task(l=l, b=b):
					ok = locker_service.open_locker(l, seconds=3.0)
					msg = f"Locker {l} abierto" if ok else f"No se pudo abrir Locker {l}"
					color = PALETTE.get("SUCCESS", "#27ae60") if ok else PALETTE["DANGER"]
					def _done(m=msg, c=color, b=b):
						if b.winfo_exists():
							b.configure(state="normal", fg_color=PALETTE["ACCENT"])
						if self.lbl_manual_feedback and self.lbl_manual_feedback.winfo_exists():
							self.lbl_manual_feedback.configure(text=m, text_color=c)
					if self.lbl_manual_feedback and self.lbl_manual_feedback.winfo_exists():
						self.lbl_manual_feedback.after(0, _done)
				threading.Thread(target=_task, daemon=True).start()

			btn.configure(command=_open)

		for i in range(len(lockers)):
			self.manual_open_frame.grid_columnconfigure(i, weight=1)

	def on_show(self, **_kwargs) -> None:
		self.lbl_feedback.configure(text="", text_color=PALETTE["MUTED"])
		if self.lbl_manual_feedback is not None:
			self.lbl_manual_feedback.configure(text="")
		self._refresh_data()
		self._build_manual_open_buttons()

