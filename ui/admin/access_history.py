"""Historial de accesos al locker."""

from __future__ import annotations

import customtkinter as ctk

from services import access_log_service
from ui.admin_app import PALETTE


class AccessHistoryScreen(ctk.CTkFrame):
	"""Listado de accesos con locker, propietario y hora."""

	def __init__(self, parent, controller):
		super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
		self.controller = controller
		self._rows: list[dict] = []
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
			text="Historial de accesos",
			font=ctk.CTkFont(size=19, weight="bold"),
			text_color=PALETTE["TEXT"],
			fg_color="transparent",
		).pack(side="left", padx=4)

		self._list_frame = ctk.CTkScrollableFrame(
			self,
			fg_color=PALETTE["BG"],
			scrollbar_button_color=PALETTE["BORDER"],
			scrollbar_button_hover_color=PALETTE["ACCENT"],
		)
		self._list_frame.pack(fill="both", expand=True, padx=12, pady=10)

	def _go_back(self) -> None:
		from ui.admin.dashboard import DashboardScreen
		self.controller.show_frame(DashboardScreen)

	def _render_rows(self, rows: list[dict]) -> None:
		for w in self._list_frame.winfo_children():
			w.destroy()

		if not rows:
			ctk.CTkLabel(
				self._list_frame,
				text="No hay registros",
				font=ctk.CTkFont(size=16),
				text_color=PALETTE["MUTED"],
				fg_color="transparent",
			).pack(pady=40)
			return

		for row in rows:
			locker_num = row.get("idLocker") or "—"
			owner = row.get("nombreCompleto") or "Sin asignacion"
			access_time = row.get("fechaHoraAcceso") or "—"
			date_part = "—"
			time_part = "—"
			if isinstance(access_time, str):
				clean = access_time.replace("T", " ")
				parts = clean.split()
				if len(parts) >= 2:
					date_part = parts[0]
					time_part = parts[1]
				elif len(parts) == 1:
					date_part = parts[0]
			motivo = self._format_motivo(row.get("motivo"))

			card = ctk.CTkFrame(
				self._list_frame,
				fg_color=PALETTE["CARD"],
				corner_radius=12,
				border_width=1,
				border_color=PALETTE["BORDER"],
			)
			card.pack(fill="x", padx=4, pady=4)

			ctk.CTkLabel(
				card,
				text=f"Locker {locker_num}",
				font=ctk.CTkFont(size=15, weight="bold"),
				text_color=PALETTE["TEXT"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=12, pady=(10, 0))

			ctk.CTkLabel(
				card,
				text=owner,
				font=ctk.CTkFont(size=13, weight="bold"),
				text_color=PALETTE["TEXT"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=12, pady=(2, 0))

			ctk.CTkLabel(
				card,
				text=f"Fecha: {date_part}",
				font=ctk.CTkFont(size=12),
				text_color=PALETTE["MUTED"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=12, pady=(2, 0))

			ctk.CTkLabel(
				card,
				text=f"Tiempo: {time_part}",
				font=ctk.CTkFont(size=12),
				text_color=PALETTE["MUTED"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=12, pady=(2, 10))

			ctk.CTkLabel(
				card,
				text=f"Motivo: {motivo}",
				font=ctk.CTkFont(size=12),
				text_color=PALETTE["MUTED"],
				fg_color="transparent",
				anchor="w",
			).pack(fill="x", padx=12, pady=(0, 10))

	def _load(self) -> None:
		self._rows = access_log_service.get_access_history(limit=200)
		self._render_rows(self._rows)

	@staticmethod
	def _format_motivo(motivo: str | None) -> str:
		mapping = {
			"facial": "Rostro",
			"pin": "PIN",
			"pin_cancelado": "Intento fallido (cancelado)",
			"pin_incorrecto": "PIN incorrecto",
			"limite_intentos_pin": "Intentos agotados",
			"no_reconocido": "Rostro no reconocido",
			"matricula_incorrecta": "Matricula no encontrada",
			"sin_asignacion": "Sin asignacion",
		}
		return mapping.get(motivo or "", "—")

	def on_show(self, **_kwargs) -> None:
		self._load()
