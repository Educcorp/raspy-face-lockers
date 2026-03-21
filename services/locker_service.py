from __future__ import annotations

from typing import Optional

from database.connection import execute, fetch_one


_ALLOWED_ACCESS_REASONS = {"facial", "pin", "sin_asignacion", "limite_intentos"}


def _normalize_access_reason(reason: str, access_allowed: bool) -> str:
	reason_clean = (reason or "").strip().lower()
	if reason_clean in _ALLOWED_ACCESS_REASONS:
		return reason_clean
	if access_allowed:
		return "facial"
	return "limite_intentos"


def get_active_locker_assignment(user_id: int) -> Optional[dict]:
	return fetch_one(
		"""
		SELECT
			al.idLockerAsignado,
			al.idLocker,
			al.disponible,
			al.estado AS estadoAsignacion,
			l.estado AS estadoLocker
		FROM asignacion_locker al
		JOIN lockers l ON l.idLocker = al.idLocker
		WHERE al.idUsuario = ?
		  AND al.estado = 'activo'
		ORDER BY al.idLockerAsignado DESC
		LIMIT 1
		""",
		(user_id,),
	)


def register_access_attempt(id_locker_asignado: Optional[int], access_allowed: bool, reason: str) -> int:
	allowed = "si" if access_allowed else "no"
	normalized_reason = _normalize_access_reason(reason, access_allowed)
	return execute(
		"""
		INSERT INTO historial_accesos
			(idLockerAsignado, accesoPermitido, motivo, fechaExpiracion)
		VALUES
			(?, ?, ?, strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '+1 minute'))
		""",
		(id_locker_asignado, allowed, normalized_reason),
	)


def build_access_payload(user_match: dict) -> dict:
	assignment = get_active_locker_assignment(int(user_match["user_id"]))

	if assignment:
		locker_numero = assignment.get("idLocker")
		id_locker_asignado = assignment.get("idLockerAsignado")
		access_title = f"Acceso garantizado · Locker {locker_numero}"
		access_reason = f"rostro reconocido y locker asignado {locker_numero}"
	else:
		locker_numero = "SIN ASIGNAR"
		id_locker_asignado = None
		access_title = "Acceso garantizado"
		access_reason = "rostro reconocido sin locker asignado"

	register_access_attempt(id_locker_asignado, True, access_reason)

	return {
		"user_id": user_match["user_id"],
		"nombre": user_match["nombre"],
		"locker_numero": locker_numero,
		"acceso_titulo": access_title,
		"distance": user_match.get("distance"),
		"threshold": user_match.get("threshold"),
	}
