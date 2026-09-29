"""CRUD de recursos compartidos y de sus usuarios autorizados."""

from __future__ import annotations

from webapp.db import execute, execute_returning, fetch_all, fetch_one


# ── Catálogo de recursos ────────────────────────────────────────────────────

def get_all_recursos() -> list[dict]:
    return fetch_all("SELECT * FROM recursos ORDER BY nombre")


def get_active_recursos() -> list[dict]:
    return fetch_all("SELECT * FROM recursos WHERE estado='activo' ORDER BY nombre")


def get_recurso_by_id(recurso_id: int) -> dict | None:
    return fetch_one("SELECT * FROM recursos WHERE idRecurso=%s", (recurso_id,))


def recurso_nombre_exists(nombre: str, exclude_id: int | None = None) -> bool:
    if exclude_id is not None:
        row = fetch_one(
            "SELECT 1 FROM recursos WHERE nombre=%s AND idRecurso!=%s LIMIT 1",
            (nombre, exclude_id),
        )
    else:
        row = fetch_one("SELECT 1 FROM recursos WHERE nombre=%s LIMIT 1", (nombre,))
    return row is not None


def create_recurso(nombre: str, descripcion: str | None, creado_por: int) -> int:
    row = execute_returning(
        "INSERT INTO recursos (nombre, descripcion, creadoPor) VALUES (%s, %s, %s) "
        "RETURNING idRecurso",
        (nombre, descripcion, creado_por),
    )
    return row["idrecurso"]


def update_recurso(recurso_id: int, nombre: str, descripcion: str | None, modificado_por: int) -> None:
    execute(
        "UPDATE recursos SET nombre=%s, descripcion=%s, modificadoPor=%s WHERE idRecurso=%s",
        (nombre, descripcion, modificado_por, recurso_id),
    )


def set_recurso_estado(recurso_id: int, estado: str, modificado_por: int) -> None:
    execute(
        "UPDATE recursos SET estado=%s, modificadoPor=%s WHERE idRecurso=%s",
        (estado, modificado_por, recurso_id),
    )


def delete_recurso(recurso_id: int) -> None:
    """Elimina el recurso; sus autorizaciones se borran en cascada (FK)."""
    execute("DELETE FROM recursos WHERE idRecurso=%s", (recurso_id,))


# ── Autorizaciones por usuario ──────────────────────────────────────────────

def get_authorized_users(recurso_id: int) -> list[dict]:
    """Usuarios activos autorizados para activar el recurso."""
    return fetch_all(
        """
        SELECT ra.idRecursoAutorizado, ra.fechaHoraReg,
               u.idUsuario, u.nombre, u.apPaterno, u.apMaterno, u.matricula
        FROM recurso_autorizados ra
        JOIN usuarios u ON u.idUsuario = ra.idUsuario
        WHERE ra.idRecurso = %s AND ra.estado = 'activo' AND u.estado = 'activo'
        ORDER BY u.nombre, u.apPaterno
        """,
        (recurso_id,),
    )


def get_authorizable_users(recurso_id: int) -> list[dict]:
    """Usuarios activos que pueden autorizarse para este recurso: deben tener el
    permiso de activación 'recurso_compartido' o 'ambos' (ver usuarios.permisoActivacion
    en users_bp.py) y no estar ya autorizados."""
    return fetch_all(
        """
        SELECT u.idUsuario, u.nombre, u.apPaterno, u.apMaterno, u.matricula
        FROM usuarios u
        WHERE u.estado = 'activo'
          AND u.permisoActivacion IN ('recurso_compartido', 'ambos')
          AND u.idUsuario NOT IN (
              SELECT idUsuario FROM recurso_autorizados
              WHERE idRecurso = %s AND estado = 'activo'
          )
        ORDER BY u.nombre, u.apPaterno
        """,
        (recurso_id,),
    )


def authorize_user(recurso_id: int, user_id: int, creado_por: int) -> None:
    """Autoriza a un usuario. Si ya existe una autorización revocada previa la
    reactiva en vez de duplicar la fila (conserva el historial)."""
    existing = fetch_one(
        "SELECT idRecursoAutorizado FROM recurso_autorizados WHERE idRecurso=%s AND idUsuario=%s",
        (recurso_id, user_id),
    )
    if existing:
        execute(
            "UPDATE recurso_autorizados SET estado='activo', modificadoPor=%s "
            "WHERE idRecursoAutorizado=%s",
            (creado_por, existing["idrecursoautorizado"]),
        )
    else:
        execute(
            "INSERT INTO recurso_autorizados (idRecurso, idUsuario, creadoPor) "
            "VALUES (%s, %s, %s)",
            (recurso_id, user_id, creado_por),
        )


def revoke_authorization(auth_id: int, modificado_por: int) -> None:
    execute(
        "UPDATE recurso_autorizados SET estado='inactivo', modificadoPor=%s "
        "WHERE idRecursoAutorizado=%s",
        (modificado_por, auth_id),
    )
