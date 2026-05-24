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
) -> None:
    """
    Registra un intento de acceso en historial_accesos.

    locker_assignment_id: FK a asignacion_locker (puede ser None si el usuario
                          no tiene locker asignado o si fue un rechazo sin match).
    permitted: True si el acceso fue concedido, False si fue denegado.
        motivo: 'facial' | 'no_reconocido' | 'pin' | 'pin_incorrecto' |
            'limite_intentos_pin' | 'matricula_incorrecta' | 'sin_asignacion' |
            'puerta_cerrada' | 'puerta_no_cerrada'
    """
    try:
        now = datetime.now()
        expires_at = now + (timedelta(minutes=5) if permitted else timedelta(minutes=1))
        execute(
            """
            INSERT INTO historial_accesos
                (idLockerAsignado, accesoPermitido, motivo, fechaExpiracion)
            VALUES (?, ?, ?, ?)
            """,
            (
                locker_assignment_id,
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
            COALESCE(u.nombre || ' ' || u.apPaterno, 'Desconocido') AS nombreCompleto,
            u.matricula,
            l.idLocker,
            a.nombreArea,
            h.fechaHoraAcceso,
            h.accesoPermitido,
            h.motivo,
            h.fechaExpiracion
        FROM historial_accesos h
        LEFT JOIN asignacion_locker al ON h.idLockerAsignado = al.idLockerAsignado
        LEFT JOIN usuarios u ON al.idUsuario = u.idUsuario
        LEFT JOIN lockers l ON al.idLocker = l.idLocker
        LEFT JOIN area_lockers a ON l.idArea = a.idArea
        ORDER BY h.fechaHoraAcceso DESC
        LIMIT ?
        """,
        (limit,),
    )
