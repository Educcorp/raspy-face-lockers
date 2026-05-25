"""
Registro y consulta del historial de accesos al locker.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from database.connection import execute, fetch_all

logger = logging.getLogger(__name__)


def register_access(
    locker_assignment_id: Optional[int],
    permitted: bool,
    motivo: str = "facial",
    user_id: Optional[int] = None,
) -> None:
    """
    Registra un intento de acceso en historial_accesos.

    locker_assignment_id: FK a asignacion_locker (None si sin asignación o rechazo sin match).
    permitted: True si el acceso fue concedido, False si fue denegado.
    motivo: 'facial' | 'no_reconocido' | 'pin' | 'pin_incorrecto' |
            'limite_intentos_pin' | 'matricula_incorrecta' | 'sin_asignacion' |
            'puerta_cerrada' | 'puerta_no_cerrada'
    user_id: idUsuario directo (usado cuando no hay idLockerAsignado disponible).
    """
    try:
        now = datetime.now()
        expires_at = now + (timedelta(minutes=5) if permitted else timedelta(minutes=1))
        execute(
            """
            INSERT INTO historial_accesos
                (idLockerAsignado, idUsuario, accesoPermitido, motivo, fechaExpiracion)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                locker_assignment_id,
                user_id,
                "si" if permitted else "no",
                motivo,
                expires_at.strftime("%Y-%m-%dT%H:%M:%S"),
            ),
        )
    except Exception as exc:
        logger.warning("No se pudo registrar historial de acceso: %s", exc)


def get_access_history(limit: int = 200) -> list[dict]:
    """Devuelve los últimos accesos del historial de accesos."""
    return fetch_all(
        """
        SELECT
            h.idAcceso,
            COALESCE(
                u1.nombre || ' ' || u1.apPaterno,
                u2.nombre || ' ' || u2.apPaterno,
                'Desconocido'
            ) AS nombreCompleto,
            COALESCE(u1.matricula, u2.matricula) AS matricula,
            l.idLocker,
            a.nombreArea,
            h.fechaHoraAcceso,
            h.accesoPermitido,
            h.motivo,
            h.fechaExpiracion
        FROM historial_accesos h
        LEFT JOIN asignacion_locker al ON h.idLockerAsignado = al.idLockerAsignado
        LEFT JOIN usuarios u1 ON al.idUsuario = u1.idUsuario
        LEFT JOIN usuarios u2 ON h.idUsuario = u2.idUsuario
        LEFT JOIN lockers l ON al.idLocker = l.idLocker
        LEFT JOIN area_lockers a ON l.idArea = a.idArea
        ORDER BY h.fechaHoraAcceso DESC
        LIMIT ?
        """,
        (limit,),
    )
