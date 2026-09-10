"""Autenticación y control de roles del panel web (equivalente web de auth/session.py)."""

from __future__ import annotations

import functools
import hashlib
import hmac

from flask import flash, g, redirect, session, url_for

from webapp.db import fetch_one

ROLE_SUPERADMIN = "superadmin"
ROLE_ADMIN = "admin"
ROLE_USER = "usuario"


def normalize_role(name: str | None) -> str:
    value = (name or "").strip().lower()
    if value in {"superadmin", "super administrador", "superadministrador"}:
        return ROLE_SUPERADMIN
    if value in {"admin", "administrador"}:
        return ROLE_ADMIN
    return ROLE_USER


def _pin_matches(pin_input: str, pin_stored: str | None) -> bool:
    if not pin_stored:
        return False
    hashed = hashlib.sha256(pin_input.encode()).hexdigest()
    return hmac.compare_digest(pin_stored, hashed) or hmac.compare_digest(pin_stored, pin_input)


def authenticate_admin_user(matricula: str, pin: str) -> tuple[str | None, dict | None]:
    """Autentica por matrícula + PIN. Solo Admin/Superadmin pueden entrar al panel web.

    Nota: psycopg2 (RealDictCursor) devuelve las columnas en minúsculas porque el
    esquema las declara sin comillas (Postgres pliega los identificadores a
    minúsculas). Por eso todas las claves de los dicts en webapp/ son lowercase,
    a diferencia del código del Pi (services/*.py, SQLite) que sí preserva camelCase.
    """
    row = fetch_one(
        """
        SELECT u.idUsuario, u.matricula, u.pin, u.estado,
               u.nombre || ' ' || u.apPaterno AS full_name,
               t.nombreTipoUsuario AS tipo,
               t.estado AS tipo_estado
        FROM usuarios u
        LEFT JOIN tipo_usuarios t ON t.idTipoUsuario = u.idTipoUsuario
        WHERE CAST(u.matricula AS TEXT) = %s
        LIMIT 1
        """,
        (str(matricula).strip(),),
    )

    if not row:
        return "not_found", None
    if (row.get("estado") or "").strip().lower() != "activo":
        return "inactive", None
    if (row.get("tipo_estado") or "activo").strip().lower() != "activo":
        return "inactive", None
    if not _pin_matches(pin.strip(), row.get("pin")):
        return "wrong_pin", None

    role = normalize_role(row.get("tipo"))
    if role not in {ROLE_SUPERADMIN, ROLE_ADMIN}:
        return "no_permission", None

    return None, {
        "idusuario": row.get("idusuario"),
        "matricula": str(row.get("matricula") or ""),
        "full_name": row.get("full_name") or "",
        "tipo": role,
    }


ERROR_MESSAGES = {
    "not_found": "Matrícula no encontrada.",
    "inactive": "El usuario o su tipo de usuario está inactivo.",
    "wrong_pin": "PIN incorrecto.",
    "no_permission": "Este usuario no tiene permisos de administración.",
}


def login_user(user: dict) -> None:
    session.clear()
    session["user_id"] = user["idusuario"]
    session["full_name"] = user["full_name"]
    session["matricula"] = user["matricula"]
    session["role"] = user["tipo"]


def logout_user() -> None:
    session.clear()


def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = {
            "idusuario": user_id,
            "full_name": session.get("full_name", ""),
            "matricula": session.get("matricula", ""),
            "role": session.get("role", ROLE_USER),
        }


def current_role() -> str:
    return (g.user or {}).get("role", ROLE_USER) if hasattr(g, "user") else ROLE_USER


def is_superadmin() -> bool:
    return current_role() == ROLE_SUPERADMIN


def is_admin() -> bool:
    return current_role() == ROLE_ADMIN


def can_edit_catalogs() -> bool:
    return current_role() in {ROLE_SUPERADMIN, ROLE_ADMIN}


def can_assign_privileged_user_types() -> bool:
    return is_superadmin()


def filter_assignable_user_types(rows: list[dict]) -> list[dict]:
    """Tipos de usuario que el rol actual puede asignar al crear/editar usuarios."""
    if is_superadmin():
        return [r for r in rows if normalize_role(r.get("nombretipousuario")) != ROLE_SUPERADMIN]
    if is_admin():
        return [r for r in rows if normalize_role(r.get("nombretipousuario")) == ROLE_USER]
    return []


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Debes iniciar sesión para continuar.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def superadmin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        if not is_superadmin():
            flash("Solo un superadministrador puede realizar esta acción.", "danger")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)
    return wrapped
