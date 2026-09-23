"""
Registro y consulta del historial de accesos al locker.
"""

from __future__ import annotations

import atexit
import logging
import queue
import threading
from typing import Optional

from database.connection import execute, fetch_all

logger = logging.getLogger(__name__)

# ── Escritura en segundo plano ─────────────────────────────────────────────
# register_access() se llama desde el hilo del bucle de cámara y desde la UI.
# Escribir en la Postgres remota cuesta un viaje de red completo, y hacerlo en
# línea congelaba la vista previa en cada intento de reconocimiento. Como es un
# registro de auditoría cuyo resultado nadie consulta, se encola y lo escribe
# un único hilo trabajador.
#
# Un solo trabajador (no un hilo por llamada) mantiene el orden de los
# registros y evita agotar el pool de conexiones en una ráfaga de intentos.
_write_queue: "queue.Queue[tuple | None]" = queue.Queue(maxsize=200)
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()


def _write_worker() -> None:
    while True:
        item = _write_queue.get()
        try:
            if item is None:  # señal de apagado
                return
            _insert_access(*item)
        except Exception as exc:  # pragma: no cover - el worker nunca debe morir
            logger.warning("Fallo escribiendo historial de acceso: %s", exc)
        finally:
            _write_queue.task_done()


def _ensure_worker() -> None:
    global _worker
    if _worker is not None and _worker.is_alive():
        return
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(
                target=_write_worker, name="access-log-writer", daemon=True
            )
            _worker.start()


def flush_access_log(timeout: float = 5.0) -> None:
    """Espera a que se escriban los registros pendientes (al apagar la app)."""
    if _worker is None or not _worker.is_alive():
        return
    try:
        _write_queue.join()
    except Exception:
        pass


atexit.register(flush_access_log)


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
    _ensure_worker()
    try:
        _write_queue.put_nowait((locker_assignment_id, permitted, motivo, user_id))
    except queue.Full:
        logger.warning("Cola de historial llena; se descarta un registro de acceso")


def _insert_access(
    locker_assignment_id: Optional[int],
    permitted: bool,
    motivo: str,
    user_id: Optional[int],
) -> None:
    """Escritura real del registro. Corre en el hilo trabajador."""
    try:
        # fechaExpiracion es TIMESTAMPTZ: se calcula con el reloj de la BD. Antes se
        # mandaba la hora LOCAL de la Pi como texto sin zona y Postgres la leía como
        # UTC, dejando la expiración 6 h ANTES del propio acceso.
        expires_minutes = 5 if permitted else 1
        execute(
            """
            INSERT INTO historial_accesos
                (idLockerAsignado, idUsuario, accesoPermitido, motivo, fechaExpiracion)
            VALUES (%s, %s, %s, %s, now() + make_interval(mins => %s))
            """,
            (
                locker_assignment_id,
                user_id,
                "si" if permitted else "no",
                motivo,
                expires_minutes,
            ),
        )
    except Exception as exc:
        logger.warning("No se pudo registrar historial de acceso: %s", exc)


def get_access_history(limit: int = 200) -> list[dict]:
    """Devuelve los últimos accesos del historial de accesos."""
    return fetch_all(
        """
        SELECT
            h.idAcceso AS "idAcceso",
            COALESCE(
                u1.nombre || ' ' || u1.apPaterno,
                u2.nombre || ' ' || u2.apPaterno,
                'Desconocido'
            ) AS "nombreCompleto",
            COALESCE(u1.matricula, u2.matricula) AS matricula,
            l.idLocker AS "idLocker",
            a.nombreArea AS "nombreArea",
            h.fechaHoraAcceso AS "fechaHoraAcceso",
            h.accesoPermitido AS "accesoPermitido",
            h.motivo,
            h.fechaExpiracion AS "fechaExpiracion"
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
