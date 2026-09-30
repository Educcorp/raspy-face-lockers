"""
Operaciones de negocio sobre recursos compartidos y sus sesiones de uso.

Equivalente, del lado Pi, a webapp/services/resource_service.py (que solo
maneja el catálogo/autorizaciones desde el panel web) — aquí además se
reclaman, consultan y cierran sesiones de uso en tiempo real contra
`recurso_uso`, la tabla que hace de candado de concurrencia (ver
webapp/migrations/add_recurso_uso.sql).
"""

from __future__ import annotations

from typing import Optional

from database.connection import execute, execute_returning, fetch_all, fetch_one


def get_active_resources() -> list[dict]:
    """Catálogo real de recursos activos (reemplaza el AVAILABLE_RESOURCES
    hardcodeado que tenía ui/locker_screen/resource_select_screen.py)."""
    return fetch_all(
        """
        SELECT idRecurso AS "idRecurso", nombre, descripcion
        FROM recursos
        WHERE estado = 'activo'
        ORDER BY nombre
        """
    )


def is_user_authorized(recurso_id: int, user_id: int) -> bool:
    """True si el usuario tiene permiso de recurso Y está autorizado en ese
    recurso específico (misma regla que webapp/services/resource_service.py::
    get_authorizable_users, aplicada aquí para verificar a un usuario puntual)."""
    row = fetch_one(
        """
        SELECT 1
        FROM recurso_autorizados ra
        JOIN usuarios u ON u.idUsuario = ra.idUsuario
        WHERE ra.idRecurso = %s AND ra.idUsuario = %s
          AND ra.estado = 'activo' AND u.estado = 'activo'
          AND u.permisoActivacion IN ('recurso_compartido', 'ambos')
        """,
        (recurso_id, user_id),
    )
    return row is not None


def get_active_session(recurso_id: int) -> Optional[dict]:
    """Sesión 'en_uso' de un recurso, si existe (de cualquier usuario)."""
    return fetch_one(
        """
        SELECT idRecursoUso AS "idRecursoUso", idRecurso AS "idRecurso",
               idUsuario AS "idUsuario",
               fechaHoraInicio AS "fechaHoraInicio",
               duracionMinutos AS "duracionMinutos",
               fechaFinPrevista AS "fechaFinPrevista"
        FROM recurso_uso
        WHERE idRecurso = %s AND estado = 'en_uso'
        """,
        (recurso_id,),
    )


def claim_session(recurso_id: int, user_id: int, duracion_minutos: int) -> Optional[dict]:
    """
    Reclama una sesión de uso nueva sin condición de carrera entre procesos.

    El candado es el índice único parcial uq_recurso_uso_activo (solo una fila
    'en_uso' por recurso): si ya existe una, el INSERT con ON CONFLICT no
    inserta nada y esta función devuelve None ("recurso ocupado"). Si el
    recurso estaba libre, devuelve la fila recién creada.
    """
    return execute_returning(
        """
        INSERT INTO recurso_uso (idRecurso, idUsuario, duracionMinutos, fechaFinPrevista)
        VALUES (%s, %s, %s, now() + make_interval(mins => %s))
        ON CONFLICT (idRecurso) WHERE estado = 'en_uso' DO NOTHING
        RETURNING idRecursoUso AS "idRecursoUso", fechaFinPrevista AS "fechaFinPrevista"
        """,
        (recurso_id, user_id, duracion_minutos, duracion_minutos),
    )


def finish_session(session_id: int, finalizado_por: str = "usuario") -> None:
    """Cierra una sesión de uso. finalizado_por: 'usuario' (botón "Terminar de
    usar") | 'sistema' (expiración automática, ver resource_session_worker)."""
    estado = "expirado" if finalizado_por == "sistema" else "finalizado"
    execute(
        """
        UPDATE recurso_uso
           SET estado = %s, fechaFinReal = now(), finalizadoPor = %s
         WHERE idRecursoUso = %s AND estado = 'en_uso'
        """,
        (estado, finalizado_por, session_id),
    )


def expire_overdue_sessions() -> list[dict]:
    """Cierra sesiones vencidas (fechaFinPrevista < now()) que nadie terminó a
    mano. Retorna las filas cerradas para que el llamador registre el evento
    en el historial de accesos."""
    return fetch_all(
        """
        UPDATE recurso_uso
           SET estado = 'expirado', fechaFinReal = now(), finalizadoPor = 'sistema'
         WHERE estado = 'en_uso' AND fechaFinPrevista < now()
        RETURNING idRecursoUso AS "idRecursoUso", idRecurso AS "idRecurso",
                  idUsuario AS "idUsuario"
        """
    )
