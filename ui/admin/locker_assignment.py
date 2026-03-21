"""
LockerAssignmentScreen – Gestión de asignación Usuario ↔ Locker.

Permite:
  • Ver asignaciones activas
  • Crear nueva asignación (usuario activo + locker activo)
  • Desasignar (marcar inactiva)
"""

import tkinter as tk
import customtkinter as ctk

from auth.session import can_edit_catalogs
from database.connection import execute, fetch_all, fetch_one
from ui.admin_app import PALETTE


class LockerAssignmentScreen(ctk.CTkFrame):
	def __init__(self, parent, controller):
		super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
		self.controller = controller
		self._can_edit = can_edit_catalogs()

		self._users: list[dict] = []
		self._lockers: list[dict] = []
		self._assignments: list[dict] = []

		self._user_var = tk.StringVar()
		self._locker_var = tk.StringVar()
		self._status_var = tk.StringVar(value="Selecciona usuario y locker")

		self._build_ui()

	def _build_ui(self) -> None:
		header = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=0, height=64)
		header.pack(fill="x")
		header.pack_propagate(False)

		ctk.CTkButton(
			header,
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
			header,
			text="Asignación de Lockers",
			font=ctk.CTkFont(size=19, weight="bold"),
			text_color=PALETTE["TEXT"],
			fg_color="transparent",
		).pack(side="left", padx=4)

		form = ctk.CTkFrame(self, fg_color=PALETTE["CARD"], corner_radius=12)
		form.pack(fill="x", padx=14, pady=(12, 8))

		ctk.CTkLabel(
			form,
			text="Usuario",
			font=ctk.CTkFont(size=12),
			text_color=PALETTE["MUTED"],
			fg_color="transparent",
		).pack(anchor="w", padx=10, pady=(10, 2))

		self.user_menu = ctk.CTkOptionMenu(
			form,
			variable=self._user_var,
			values=["Sin usuarios"],
			fg_color=PALETTE["CARD"],
			button_color=PALETTE["ACCENT"],
			button_hover_color=PALETTE["ACCENT_HOVER"],
			text_color=PALETTE["TEXT"],
			height=44,
		)
		self.user_menu.pack(fill="x", padx=10)

		ctk.CTkLabel(
			form,
			text="Locker",
			font=ctk.CTkFont(size=12),
			text_color=PALETTE["MUTED"],
			fg_color="transparent",
		).pack(anchor="w", padx=10, pady=(10, 2))

		self.locker_menu = ctk.CTkOptionMenu(
			form,
			variable=self._locker_var,
			values=["Sin lockers"],
			fg_color=PALETTE["CARD"],
			button_color=PALETTE["ACCENT"],
			button_hover_color=PALETTE["ACCENT_HOVER"],
			text_color=PALETTE["TEXT"],
			height=44,
		)
		self.locker_menu.pack(fill="x", padx=10)

		self.btn_assign = ctk.CTkButton(
			form,
			text="Asignar locker",
			font=ctk.CTkFont(size=15, weight="bold"),
			fg_color=PALETTE["ACCENT"] if self._can_edit else PALETTE["BORDER"],
			hover_color=PALETTE["ACCENT_HOVER"] if self._can_edit else PALETTE["BORDER"],
			text_color=PALETTE["WHITE"],
			height=48,
			command=self._assign if self._can_edit else None,
		)
		self.btn_assign.pack(fill="x", padx=10, pady=(12, 10))

		self.lbl_status = ctk.CTkLabel(
			self,
			textvariable=self._status_var,
			font=ctk.CTkFont(size=12),
			text_color=PALETTE["MUTED"],
			fg_color="transparent",
		)
		self.lbl_status.pack(anchor="w", padx=18, pady=(0, 2))

		ctk.CTkLabel(
			self,
			text="Asignaciones activas",
			font=ctk.CTkFont(size=14, weight="bold"),
			text_color=PALETTE["MUTED"],
			fg_color="transparent",
		).pack(anchor="w", padx=18, pady=(6, 4))

		self.list_frame = ctk.CTkScrollableFrame(
			self,
			fg_color=PALETTE["BG"],
			scrollbar_button_color=PALETTE["BORDER"],
			scrollbar_button_hover_color=PALETTE["ACCENT"],
		)
		self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

	def _go_back(self) -> None:
		from ui.admin.dashboard import DashboardScreen

		self.controller.show_frame(DashboardScreen)

	def _load_users(self) -> None:
		self._users = fetch_all(
			"""
			SELECT idUsuario, nombre, apPaterno, matricula
			FROM usuarios
			WHERE estado = 'activo'
			ORDER BY nombre, apPaterno
			"""
		)

		labels = [
			f"{u['idUsuario']} · {u['nombre']} {u['apPaterno']} ({u['matricula']})"
			for u in self._users
		]
		if not labels:
			labels = ["Sin usuarios"]

		self.user_menu.configure(values=labels)
		self._user_var.set(labels[0])

	def _load_lockers(self) -> None:
		self._lockers = fetch_all(
			"""
			SELECT l.idLocker
			FROM lockers l
			WHERE l.estado = 'activo'
			ORDER BY l.idLocker
			"""
		)
		labels = [f"Locker {l['idLocker']}" for l in self._lockers]
		if not labels:
			labels = ["Sin lockers"]

		self.locker_menu.configure(values=labels)
		self._locker_var.set(labels[0])

	def _load_assignments(self) -> None:
		self._assignments = fetch_all(
			"""
			SELECT
				al.idLockerAsignado,
				al.idUsuario,
				al.idLocker,
				u.nombre,
				u.apPaterno,
				u.matricula
			FROM asignacion_locker al
			JOIN usuarios u ON u.idUsuario = al.idUsuario
			WHERE al.estado = 'activo'
			ORDER BY al.idLockerAsignado DESC
			"""
		)

		for widget in self.list_frame.winfo_children():
			widget.destroy()

		if not self._assignments:
			ctk.CTkLabel(
				self.list_frame,
				text="No hay asignaciones activas",
				font=ctk.CTkFont(size=15),
				text_color=PALETTE["MUTED"],
				fg_color="transparent",
			).pack(pady=28)
			return

		for row in self._assignments:
			card = ctk.CTkFrame(
				self.list_frame,
				fg_color=PALETTE["CARD"],
				corner_radius=12,
				border_width=1,
				border_color=PALETTE["BORDER"],
			)
			card.pack(fill="x", padx=4, pady=4)

			user_text = f"{row['nombre']} {row['apPaterno']} · Matrícula {row['matricula']}"
			locker_text = f"Locker {row['idLocker']}"

			ctk.CTkLabel(
				card,
				text=user_text,
				font=ctk.CTkFont(size=14, weight="bold"),
				text_color=PALETTE["TEXT"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=10, pady=(8, 2))

			ctk.CTkLabel(
				card,
				text=locker_text,
				font=ctk.CTkFont(size=13),
				text_color=PALETTE["ACCENT"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=10, pady=(0, 8))

			if self._can_edit:
				ctk.CTkButton(
					card,
					text="Desasignar",
					font=ctk.CTkFont(size=13, weight="bold"),
					fg_color=PALETTE["DANGER"],
					hover_color="#922b21",
					text_color=PALETTE["WHITE"],
					width=110,
					height=32,
					command=lambda aid=row["idLockerAsignado"]: self._unassign(aid),
				).pack(anchor="e", padx=10, pady=(0, 8))

	@staticmethod
	def _extract_id_from_label(label: str) -> int | None:
		if not label:
			return None
		token = label.split("·", 1)[0].replace("Locker", "").strip()
		try:
			return int(token)
		except ValueError:
			return None

	def _assign(self) -> None:
		user_id = self._extract_id_from_label(self._user_var.get())
		locker_id = self._extract_id_from_label(self._locker_var.get())

		if user_id is None or locker_id is None:
			self._status_var.set("Selecciona usuario y locker válidos")
			return

		user_ok = fetch_one("SELECT idUsuario FROM usuarios WHERE idUsuario=? AND estado='activo'", (user_id,))
		locker_ok = fetch_one("SELECT idLocker FROM lockers WHERE idLocker=? AND estado='activo'", (locker_id,))
		if not user_ok or not locker_ok:
			self._status_var.set("Usuario o locker no están activos")
			return

		execute(
			"""
			UPDATE asignacion_locker
			SET estado='inactivo', fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), modificadoPor=1
			WHERE estado='activo' AND (idUsuario=? OR idLocker=?)
			""",
			(user_id, locker_id),
		)

		execute(
			"""
			INSERT INTO asignacion_locker (idUsuario, idLocker, disponible, estado, creadoPor)
			VALUES (?, ?, 'no', 'activo', 1)
			""",
			(user_id, locker_id),
		)

		self._status_var.set(f"Asignación guardada: usuario {user_id} → locker {locker_id}")
		self._load_assignments()

	def _unassign(self, assignment_id: int) -> None:
		execute(
			"""
			UPDATE asignacion_locker
			SET estado='inactivo', disponible='si', fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), modificadoPor=1
			WHERE idLockerAsignado=?
			""",
			(assignment_id,),
		)
		self._status_var.set("Asignación eliminada")
		self._load_assignments()

	def on_show(self, **_kwargs) -> None:
		self._load_users()
		self._load_lockers()
		self._load_assignments()

