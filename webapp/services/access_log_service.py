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


def _base_query():
    return """
        FROM historial_accesos h
        LEFT JOIN asignacion_locker al
            ON h.idLockerAsignado = al.idLockerAsignado
        LEFT JOIN usuarios u1
            ON al.idUsuario = u1.idUsuario
        LEFT JOIN usuarios u2
            ON h.idUsuario = u2.idUsuario
        LEFT JOIN lockers l
            ON al.idLocker = l.idLocker
        LEFT JOIN area_lockers a
            ON l.idArea = a.idArea
    """


def get_access_history(
    page: int = 1,
    per_page: int = 15,
    search: str = "",
    resultado: str = "",
) -> tuple[list[dict], int]:
    """
    Obtiene el historial de accesos paginado.

    Retorna:
        rows: registros de la página actual
        total: cantidad total de registros que coinciden con los filtros
    """

    # Evitar valores inválidos
    page = max(page, 1)
    per_page = max(per_page, 1)

    offset = (page - 1) * per_page

    # -----------------------------
    # Filtros
    # -----------------------------
    conditions = []
    params = []

    if search:
        search_like = f"%{search}%"

        conditions.append(
            """
            (
                COALESCE(u1.nombre || ' ' || u1.apPaterno, '') LIKE %s
                OR COALESCE(u2.nombre || ' ' || u2.apPaterno, '') LIKE %s
                OR CAST(COALESCE(u1.matricula, u2.matricula) AS TEXT) LIKE %s
                OR CAST(l.idLocker AS TEXT) LIKE %s
            )
            """
        )

        params.extend([
            search_like,
            search_like,
            search_like,
            search_like,
        ])

    if resultado == "si":
        conditions.append("h.accesoPermitido = 'si'")
    
    elif resultado == "no":
        conditions.append(
            "(h.accesoPermitido IS NULL OR h.accesoPermitido <> 'si')"
        )

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # -----------------------------
    # Total de registros
    # -----------------------------
    total_query = f"""
        SELECT COUNT(*) AS total
        {_base_query()}
        {where_clause}
    """

    total_result = fetch_all(total_query, tuple(params))

    total = 0

    if total_result:
        total = int(total_result[0]["total"])

    # -----------------------------
    # Registros de la página
    # -----------------------------
    query = f"""
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

        {_base_query()}

        {where_clause}

        ORDER BY h.fechaHoraAcceso DESC

        LIMIT %s OFFSET %s
    """

    query_params = params + [per_page, offset]

    rows = fetch_all(query, tuple(query_params))

    return rows, total