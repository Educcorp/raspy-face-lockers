"""CRUD de recursos compartidos y de sus usuarios autorizados."""

from __future__ import annotations

from webapp.db import cursor, execute, execute_returning, fetch_all, fetch_one


# ── Catálogo de recursos ────────────────────────────────────────────────────

def _recursos_select_query() -> str:
    return """
        SELECT r.idRecurso, r.nombre, r.descripcion, r.idUnidadAcademica, r.idArea,
               r.estado, r.fechaHoraReg, r.fechaHoraAct, r.creadoPor, r.modificadoPor,
               ua.nombreUnidadAcademica, a.nombreArea
        FROM recursos r
        LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = r.idUnidadAcademica
        LEFT JOIN area_lockers a ON a.idArea = r.idArea
    """


def get_all_recursos() -> list[dict]:
    return fetch_all(_recursos_select_query() + " ORDER BY r.nombre")


def get_active_recursos() -> list[dict]:
    return fetch_all(_recursos_select_query() + " WHERE r.estado='activo' ORDER BY r.nombre")


def get_recurso_by_id(recurso_id: int) -> dict | None:
    return fetch_one(_recursos_select_query() + " WHERE r.idRecurso=%s", (recurso_id,))


def recurso_nombre_exists(nombre: str, exclude_id: int | None = None) -> bool:
    if exclude_id is not None:
        row = fetch_one(
            "SELECT 1 FROM recursos WHERE nombre=%s AND idRecurso!=%s LIMIT 1",
            (nombre, exclude_id),
        )
    else:
        row = fetch_one("SELECT 1 FROM recursos WHERE nombre=%s LIMIT 1", (nombre,))
    return row is not None


def create_recurso(
    nombre: str, descripcion: str | None, unidad_id: int, area_id: int, creado_por: int
) -> int:
    row = execute_returning(
        "INSERT INTO recursos (nombre, descripcion, idUnidadAcademica, idArea, creadoPor) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING idRecurso",
        (nombre, descripcion, unidad_id, area_id, creado_por),
    )
    return row["idrecurso"]


def update_recurso(
    recurso_id: int,
    nombre: str,
    descripcion: str | None,
    unidad_id: int,
    area_id: int,
    modificado_por: int,
) -> None:
    execute(
        "UPDATE recursos SET nombre=%s, descripcion=%s, idUnidadAcademica=%s, idArea=%s, "
        "modificadoPor=%s WHERE idRecurso=%s",
        (nombre, descripcion, unidad_id, area_id, modificado_por, recurso_id),
    )


def set_recurso_estado(recurso_id: int, estado: str, modificado_por: int) -> None:
    execute(
        "UPDATE recursos SET estado=%s, modificadoPor=%s WHERE idRecurso=%s",
        (estado, modificado_por, recurso_id),
    )


def delete_recurso(recurso_id: int) -> None:
    """Elimina el recurso; sus autorizaciones se borran en cascada (FK).

    recurso_uso.idRecurso es ON DELETE RESTRICT (es el candado de concurrencia
    de una sesión activa, ver webapp/schema.sql) — un recurso que alguna vez
    se usó (aunque la sesión ya haya terminado) bloqueaba este DELETE con un
    error sin manejar. Mismo tipo de bug que bloqueaba eliminar usuarios con
    una sesión de recurso sin cerrar (ver user_service.py::
    delete_user_permanent); se corrige igual, en una sola transacción.
    """
    with cursor() as cur:
        cur.execute("DELETE FROM recurso_uso WHERE idRecurso=%s", (recurso_id,))
        cur.execute("DELETE FROM recursos WHERE idRecurso=%s", (recurso_id,))


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


# ── Activación remota (web → Pi) ─────────────────────────────────────────────
# Mismo patrón que la apertura remota de lockers (locker_service): la web solo
# encola en `comandos_recurso`; la Pi (services/remote_command_service.py)
# reclama el comando, abre la sesión en `recurso_uso` a nombre de quien lo
# pidió y enciende el relé en el puerto BCM que ella tiene configurado para el
# recurso (config.py → TOOL_GPIO_CONFIG["pins"]).

RESOURCE_COMMAND_RECENT_SECONDS = 60
MAX_SESSION_SECONDS = 10800  # mismo tope que recurso_uso.duracionSegundos (3 h)


def get_resource_remote_status(recurso_id: int) -> dict:
    """Estado en vivo del recurso para el panel de autorizaciones."""
    from webapp.services.locker_service import pi_is_online

    session = fetch_one(
        """
        SELECT ru.idRecursoUso, ru.idUsuario, ru.fechaFinPrevista,
               GREATEST(0, EXTRACT(EPOCH FROM (ru.fechaFinPrevista - now())))::int AS restante,
               u.nombre, u.apPaterno
        FROM recurso_uso ru
        JOIN usuarios u ON u.idUsuario = ru.idUsuario
        WHERE ru.idRecurso = %s AND ru.estado = 'en_uso'
        """,
        (recurso_id,),
    )
    command = fetch_one(
        """
        SELECT idComando, accion, estado, detalle FROM comandos_recurso
        WHERE idRecurso = %s
          AND fechaHoraSolicitud > now() - make_interval(secs => %s)
        ORDER BY idComando DESC LIMIT 1
        """,
        (recurso_id, RESOURCE_COMMAND_RECENT_SECONDS),
    )
    return {
        "online": pi_is_online(),
        "active": session is not None,
        "user": f"{session['nombre']} {session['appaterno']}" if session else None,
        "remaining": session["restante"] if session else 0,
        "command": {
            "id": command["idcomando"],
            "accion": command["accion"],
            "estado": command["estado"],
            "detalle": command["detalle"],
        } if command else None,
    }


def request_resource_command(
    recurso_id: int, accion: str, solicitado_por: int, duracion_segundos: int | None = None
) -> tuple[bool, str]:
    """Encola 'activar' / 'desactivar' para la Pi. Devuelve (ok, mensaje)."""
    from webapp.services.locker_service import pi_is_online

    if accion not in ("activar", "desactivar"):
        return False, "Acción no válida."
    recurso = fetch_one("SELECT estado FROM recursos WHERE idRecurso=%s", (recurso_id,))
    if not recurso or (recurso["estado"] or "").lower() != "activo":
        return False, "El recurso no existe o está deshabilitado."
    if not pi_is_online():
        return False, "La Raspberry Pi está desconectada; no se puede controlar el recurso ahora."

    busy = fetch_one(
        """
        SELECT 1 AS x FROM comandos_recurso
        WHERE idRecurso=%s AND estado IN ('pendiente', 'ejecutando')
          AND fechaHoraSolicitud > now() - make_interval(secs => %s)
        LIMIT 1
        """,
        (recurso_id, RESOURCE_COMMAND_RECENT_SECONDS),
    )
    if busy:
        return False, "Ya hay una orden en curso para este recurso."

    in_use = fetch_one(
        "SELECT 1 AS x FROM recurso_uso WHERE idRecurso=%s AND estado='en_uso'", (recurso_id,)
    )
    if accion == "activar":
        if in_use:
            return False, "El recurso ya está en uso."
        if not duracion_segundos or not 0 < duracion_segundos <= MAX_SESSION_SECONDS:
            return False, "Elige una duración válida (máximo 3 horas)."
    elif not in_use:
        return False, "El recurso no está activo."

    execute(
        "INSERT INTO comandos_recurso (idRecurso, accion, duracionSegundos, solicitadoPor) "
        "VALUES (%s, %s, %s, %s)",
        (recurso_id, accion, duracion_segundos if accion == "activar" else None, solicitado_por),
    )
    return True, "Enviando orden a la Raspberry…"
