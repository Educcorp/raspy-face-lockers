"""Gestión de sesión y permisos del panel administrativo."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from database.connection import fetch_one


ROLE_SUPERADMIN = "superadmin"
ROLE_ADMIN = "admin"
ROLE_USER = "usuario"

ENV_ROLE = "SMART_LOCKER_ROLE"


def normalize_role(name: str | None) -> str:
	value = (name or "").strip().lower()
	if value in {"superadmin", "super administrador", "superadministrador"}:
		return ROLE_SUPERADMIN
	if value in {"admin", "administrador"}:
		return ROLE_ADMIN
	if value in {"usuario", "alumno", "docente", "user"}:
		return ROLE_USER
	return ROLE_SUPERADMIN


def normalize_user_type_name(name: str | None) -> str:
	"""Normaliza nombres de tipo guardados en la BD a rol de negocio."""
	return normalize_role(name)


def has_env_role_override() -> bool:
	return bool((os.getenv(ENV_ROLE) or "").strip())


@dataclass
class SessionContext:
	user_id: int | None = None
	role: str = ROLE_SUPERADMIN
	full_name: str = ""
	matricula: str = ""
	authenticated: bool = False


_session = SessionContext()


def initialize_session_from_env() -> None:
	"""Inicializa sesión en modo bypass usando SMART_LOCKER_ROLE."""
	role = normalize_role(os.getenv(ENV_ROLE))
	_session.user_id = None
	_session.role = role
	_session.full_name = f"ENV {get_current_role_label()}"
	_session.matricula = ""
	_session.authenticated = True


def clear_session() -> None:
	_session.user_id = None
	_session.role = ROLE_SUPERADMIN
	_session.full_name = ""
	_session.matricula = ""
	_session.authenticated = False


def set_current_user(user: dict) -> None:
	_session.user_id = user.get("idUsuario")
	_session.role = normalize_user_type_name(user.get("tipo"))
	_session.full_name = user.get("full_name", "")
	_session.matricula = str(user.get("matricula", ""))
	_session.authenticated = True


def is_authenticated() -> bool:
	return _session.authenticated


def get_current_role() -> str:
	return _session.role


def get_current_role_label() -> str:
	role = get_current_role()
	if role == ROLE_SUPERADMIN:
		return "Superadmin"
	if role == ROLE_ADMIN:
		return "Admin"
	return "Usuario"


def is_superadmin() -> bool:
	return get_current_role() == ROLE_SUPERADMIN


def is_admin() -> bool:
	return get_current_role() == ROLE_ADMIN


def is_user() -> bool:
	return get_current_role() == ROLE_USER


def can_create_users() -> bool:
	return get_current_role() in {ROLE_SUPERADMIN, ROLE_ADMIN}


def can_assign_privileged_user_types() -> bool:
	return is_superadmin()


def can_edit_catalogs() -> bool:
	return get_current_role() in {ROLE_SUPERADMIN, ROLE_ADMIN}


def filter_assignable_user_types(rows: list[dict]) -> list[dict]:
	"""Filtra tipos asignables según rol actual.

	- Superadmin: todos los tipos activos.
	- Admin: solo tipo Usuario.
	- Usuario: ninguno.
	"""
	if is_superadmin():
		return rows
	if is_admin():
		return [
			r for r in rows
			if normalize_user_type_name(r.get("nombreTipoUsuario")) == ROLE_USER
		]
	return []


def _pin_matches(pin_input: str, pin_stored: str | None) -> bool:
	if not pin_stored:
		return False
	hashed = hashlib.sha256(pin_input.encode()).hexdigest()
	# Compatibilidad: aceptar hash SHA-256 o texto plano legacy.
	return hmac.compare_digest(pin_stored, hashed) or hmac.compare_digest(pin_stored, pin_input)


def authenticate_admin_user(matricula: str, pin: str) -> dict | None:
	"""Autentica un usuario admin contra BD por matrícula + PIN.

	Devuelve dict con datos de sesión si es válido y activo.
	"""
	row = fetch_one(
		"""
		SELECT u.idUsuario, u.matricula, u.pin, u.estado,
			   u.nombre || ' ' || u.apPaterno AS full_name,
			   t.nombreTipoUsuario AS tipo,
			   t.estado AS tipo_estado
		FROM usuarios u
		LEFT JOIN tipo_usuarios t ON t.idTipoUsuario = u.idTipoUsuario
		WHERE CAST(u.matricula AS TEXT) = ?
		LIMIT 1
		""",
		(str(matricula).strip(),),
	)

	if not row:
		return None
	if (row.get("estado") or "").strip().lower() != "activo":
		return None
	if (row.get("tipo_estado") or "activo").strip().lower() != "activo":
		return None
	if not _pin_matches(pin.strip(), row.get("pin")):
		return None

	role = normalize_user_type_name(row.get("tipo"))
	return {
		"idUsuario": row.get("idUsuario"),
		"matricula": str(row.get("matricula") or ""),
		"full_name": row.get("full_name") or "",
		"tipo": role,
	}
