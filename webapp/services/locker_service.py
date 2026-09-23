"""
Gestión de inventario de lockers y asignaciones (panel web).

La apertura física (relevador GPIO) NO se ejecuta aquí: la web solo encola un
comando en `comandos_locker` (ver "Apertura remota" al final) y la Raspberry Pi
lo ejecuta.
"""

from __future__ import annotations

from webapp.db import cursor, execute, execute_returning, fetch_all, fetch_one


def get_all_lockers() -> list[dict]:
    return fetch_all(
        """
        SELECT l.idLocker, l.estado,
               l.idUnidadAcademica, l.idArea,
               ua.nombreUnidadAcademica AS unidad,
               a.nombreArea AS area
        FROM lockers l
        JOIN unidad_academica ua ON ua.idUnidadAcademica = l.idUnidadAcademica
        JOIN area_lockers a ON a.idArea = l.idArea
        ORDER BY l.idLocker
        """
    )


def create_locker(unidad_id: int, area_id: int, creado_por: int) -> int:
    row = execute_returning(
        "INSERT INTO lockers (idUnidadAcademica, idArea, creadoPor) VALUES (%s, %s, %s) "
        "RETURNING idLocker",
        (unidad_id, area_id, creado_por),
    )
    return row["idlocker"]


def set_locker_status(locker_id: int, estado: str, modificado_por: int) -> None:
    execute(
        "UPDATE lockers SET estado=%s, modificadoPor=%s WHERE idLocker=%s",
        (estado, modificado_por, locker_id),
    )


def update_locker_location(locker_id: int, unidad_id: int, area_id: int, modificado_por: int) -> None:
    execute(
        "UPDATE lockers SET idUnidadAcademica=%s, idArea=%s, modificadoPor=%s WHERE idLocker=%s",
        (unidad_id, area_id, modificado_por, locker_id),
    )


def get_protected_locker_ids() -> set[int]:
    """Los 4 lockers físicos originales (los de menor idLocker) no se pueden eliminar:
    el sistema debe poder mostrarse escalando a más lockers, pero solo hay 4 gabinetes
    reales, así que esos siempre deben seguir existiendo en el catálogo."""
    rows = fetch_all("SELECT idLocker FROM lockers ORDER BY idLocker ASC LIMIT 4")
    return {r["idlocker"] for r in rows}


def has_active_assignment(locker_id: int) -> bool:
    row = fetch_one(
        "SELECT 1 AS x FROM asignacion_locker WHERE idLocker=%s AND estado='activo' LIMIT 1",
        (locker_id,),
    )
    return row is not None


def delete_locker(locker_id: int) -> None:
    """Elimina el locker junto con TODO su historial (asignaciones y accesos).

    asignacion_locker.idLocker es ON DELETE RESTRICT, así que el historial debe
    borrarse antes que el locker; todo en una sola transacción.
    """
    with cursor() as cur:
        cur.execute(
            "DELETE FROM historial_accesos WHERE idLockerAsignado IN "
            "(SELECT idLockerAsignado FROM asignacion_locker WHERE idLocker=%s)",
            (locker_id,),
        )
        cur.execute("DELETE FROM asignacion_locker WHERE idLocker=%s", (locker_id,))
        cur.execute("DELETE FROM lockers WHERE idLocker=%s", (locker_id,))


def get_available_lockers() -> list[dict]:
    return fetch_all("SELECT * FROM v_lockers_disponibles")


def get_users_without_locker() -> list[dict]:
    """Usuarios activos sin un locker asignado actualmente (equivalente a
    v_lockers_disponibles, pero del lado del usuario en vez del locker)."""
    return fetch_all(
        """
        SELECT u.idUsuario, u.nombre, u.apPaterno, u.matricula
        FROM usuarios u
        WHERE u.estado = 'activo'
          AND u.idUsuario NOT IN (
              SELECT idUsuario FROM asignacion_locker WHERE estado = 'activo'
          )
        ORDER BY u.nombre, u.apPaterno
        """
    )


def get_active_assignments() -> list[dict]:
    return fetch_all(
        """
        SELECT al.idLockerAsignado, al.estado, al.fechaHoraReg,
               u.idUsuario, u.nombre, u.apPaterno, u.apMaterno, u.matricula,
               l.idLocker, a.nombreArea AS area
        FROM asignacion_locker al
        JOIN usuarios u ON u.idUsuario = al.idUsuario
        JOIN lockers l ON l.idLocker = al.idLocker
        JOIN area_lockers a ON a.idArea = l.idArea
        WHERE al.estado = 'activo'
        ORDER BY al.idLocker
        """
    )


def _close_active_assignment(cur, user_id: int, locker_id: int) -> None:
    """Vence asignaciones activas previas del usuario y/o del locker."""
    cur.execute(
        "DELETE FROM asignacion_locker WHERE estado='vencido' AND (idUsuario=%s OR idLocker=%s)",
        (user_id, locker_id),
    )
    cur.execute(
        "UPDATE asignacion_locker SET estado='vencido', disponible='si' "
        "WHERE idUsuario=%s AND estado='activo'",
        (user_id,),
    )
    cur.execute(
        "UPDATE asignacion_locker SET estado='vencido', disponible='si' "
        "WHERE idLocker=%s AND estado='activo'",
        (locker_id,),
    )


def assign_locker(user_id: int, locker_id: int, creado_por: int) -> None:
    existing = fetch_one(
        "SELECT idLocker FROM asignacion_locker WHERE idUsuario=%s AND estado='activo'",
        (user_id,),
    )
    if existing:
        raise ValueError("El usuario ya tiene un locker asignado.")

    with cursor() as cur:
        _close_active_assignment(cur, user_id, locker_id)
        cur.execute(
            "INSERT INTO asignacion_locker (idUsuario, idLocker, disponible, estado, creadoPor) "
            "VALUES (%s, %s, 'no', 'activo', %s)",
            (user_id, locker_id, creado_por),
        )


def release_assignment(assignment_id: int) -> bool:
    row = fetch_one(
        "SELECT idUsuario, idLocker FROM asignacion_locker WHERE idLockerAsignado=%s",
        (assignment_id,),
    )
    if not row:
        return False
    with cursor() as cur:
        _close_active_assignment(cur, row["idusuario"], row["idlocker"])
    return True


# ── Apertura remota (web → Pi) ───────────────────────────────────────────────
# La web solo encola el comando; la Raspberry lo ejecuta (services/remote_command_service.py
# en la Pi) y publica el estado de las puertas en `estado_puerta`.

PI_ONLINE_SECONDS = 30      # sin latido en este tiempo → Pi desconectada
COMMAND_RECENT_SECONDS = 60  # ventana en que un comando cuenta como "reciente"


def get_remote_status() -> dict:
    """Estado para los botones de apertura: latido de la Pi, puerta y último comando por locker."""
    hb = fetch_one(
        "SELECT EXTRACT(EPOCH FROM (now() - MAX(fechaHoraAct))) AS age FROM estado_puerta"
    )
    age = hb["age"] if hb else None
    rows = fetch_all(
        """
        SELECT l.idLocker, ep.cerrada,
               c.idComando AS comando_id, c.estado AS comando, c.detalle AS detalle
        FROM lockers l
        LEFT JOIN estado_puerta ep ON ep.idLocker = l.idLocker
        LEFT JOIN LATERAL (
            SELECT idComando, estado, detalle FROM comandos_locker
            WHERE idLocker = l.idLocker
              AND fechaHoraSolicitud > now() - make_interval(secs => %s)
            ORDER BY idComando DESC LIMIT 1
        ) c ON TRUE
        WHERE l.estado = 'activo'
        ORDER BY l.idLocker
        """,
        (COMMAND_RECENT_SECONDS,),
    )
    return {
        "online": age is not None and float(age) <= PI_ONLINE_SECONDS,
        "lockers": [
            {
                "id": r["idlocker"],
                "cerrada": r["cerrada"],
                "comando_id": r["comando_id"],
                "comando": r["comando"],
                "detalle": r["detalle"],
            }
            for r in rows
        ],
    }


def request_open_locker(locker_id: int, solicitado_por: int) -> tuple[bool, str]:
    """Encola la apertura de un locker. Devuelve (ok, mensaje)."""
    locker = fetch_one("SELECT estado FROM lockers WHERE idLocker=%s", (locker_id,))
    if not locker or (locker["estado"] or "").lower() != "activo":
        return False, "El locker no existe o está deshabilitado."

    if not get_remote_status()["online"]:
        return False, "La Raspberry Pi está desconectada; no se puede abrir el locker ahora."

    busy = fetch_one(
        """
        SELECT 1 AS x FROM comandos_locker
        WHERE idLocker=%s AND estado IN ('pendiente', 'ejecutando')
          AND fechaHoraSolicitud > now() - make_interval(secs => %s)
        LIMIT 1
        """,
        (locker_id, COMMAND_RECENT_SECONDS),
    )
    if busy:
        return False, "Ese locker ya se está abriendo."

    execute(
        "INSERT INTO comandos_locker (idLocker, accion, solicitadoPor) VALUES (%s, 'abrir', %s)",
        (locker_id, solicitado_por),
    )
    return True, "Abriendo…"
