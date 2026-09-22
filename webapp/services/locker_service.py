"""
Gestión de inventario de lockers y asignaciones (panel web).

La apertura física (relevador GPIO) NO vive aquí — eso sigue siendo
responsabilidad exclusiva del software embebido en la Raspberry Pi.
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


def delete_locker(locker_id: int) -> None:
    execute("DELETE FROM lockers WHERE idLocker=%s", (locker_id,))


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
