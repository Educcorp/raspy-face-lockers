"""
Operaciones de negocio sobre lockers y apertura de hardware.
"""

from __future__ import annotations

import logging

from database.connection import fetch_all, fetch_one, execute

logger = logging.getLogger(__name__)


# ── Consultas de lockers ───────────────────────────────────────────────────────

def get_all_lockers() -> list[dict]:
    """Lista todos los lockers con su unidad académica y área."""
    return fetch_all("""
        SELECT l.idLocker, l.estado,
               ua.nombreUnidadAcademica AS unidad,
               a.nombreArea AS area
        FROM lockers l
        JOIN unidad_academica ua ON ua.idUnidadAcademica = l.idUnidadAcademica
        JOIN area_lockers a ON a.idArea = l.idArea
        ORDER BY l.idLocker
    """)


def get_available_lockers() -> list[dict]:
    """Lista los lockers sin asignación activa."""
    return fetch_all("""
        SELECT * FROM v_lockers_disponibles
    """)


def get_active_assignments() -> list[dict]:
    """Lista todas las asignaciones activas con datos de usuario y locker."""
    return fetch_all("""
        SELECT al.idLockerAsignado, al.estado,
               u.nombre, u.apPaterno, u.matricula,
               l.idLocker,
               a.nombreArea AS area
        FROM asignacion_locker al
        JOIN usuarios u ON u.idUsuario = al.idUsuario
        JOIN lockers l ON l.idLocker = al.idLocker
        JOIN area_lockers a ON a.idArea = l.idArea
        WHERE al.estado = 'activo'
        ORDER BY al.idLockerAsignado
    """)


# ── Control de hardware ────────────────────────────────────────────────────────

def open_locker(locker_id: int, seconds: float | None = None) -> bool:
    """
    Abre el locker físico activando el relay GPIO correspondiente.
    Retorna True si el relay se activó correctamente.
    """
    from core.gpio_controller import get_locker_gpio_controller
    from config import GPIO_CONFIG

    hold = float(
        seconds if seconds is not None
        else GPIO_CONFIG.get("locker_open_seconds", 3.0)
    )
    controller = get_locker_gpio_controller()
    ok = controller.open_locker_by_id(locker_id, seconds=hold)
    if not ok:
        logger.warning("No se pudo activar relay del locker %s", locker_id)
    return ok
