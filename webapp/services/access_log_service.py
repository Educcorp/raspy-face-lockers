"""Consulta del historial de accesos (solo lectura desde el panel web)."""

from __future__ import annotations

from webapp.db import fetch_all

MOTIVO_LABELS: dict[str, str] = {
    "facial": "Facial",
    "no_reconocido": "Rostro no reconocido",
    "pin": "PIN",
    "pin_incorrecto": "PIN incorrecto",
    "limite_intentos": "Exceso de intentos",
    "limite_intentos_pin": "Exceso de intentos PIN",
    "matricula_incorrecta": "Matrícula incorrecta",
    "sin_asignacion": "Sin asignación de locker",
    "pin_cancelado": "PIN cancelado",
    "puerta_cerrada": "Puerta cerrada",
    "puerta_no_cerrada": "Puerta no cerrada",
}


def get_access_history(limit: int = 200) -> list[dict]:
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
        LIMIT %s
        """,
        (limit,),
    )
