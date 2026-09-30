"""
Expiración automática de sesiones de uso de recursos compartidos.

El relé de la herramienta ya se apaga solo (core.tool_gpio_controller corre su
propio Event.wait(timeout=...) en un hilo aparte, lanzado al reclamar la
sesión) — este worker solo sincroniza el estado en BD: si nadie presionó
"Terminar de usar" antes de que se cumpliera el tiempo, libera el candado
(uq_recurso_uso_activo) para que el siguiente usuario pueda reclamar el
recurso, y registra el cierre en el historial de accesos.

Mismo patrón que services/remote_command_service.py (hilo singleton, poll
periódico, nunca debe morir).
"""

from __future__ import annotations

import logging
import threading
import time

from services import access_log_service, resource_service

logger = logging.getLogger(__name__)

POLL_S = 5.0

_worker_lock = threading.Lock()
_worker_thread: threading.Thread | None = None


def _tick() -> None:
    for row in resource_service.expire_overdue_sessions():
        try:
            access_log_service.register_access(
                None,
                permitted=True,
                motivo="recurso_expirado",
                user_id=row["idUsuario"],
                tipo_acceso="recurso",
                resource_use_id=row["idRecursoUso"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo registrar expiración de recurso_uso=%s: %s",
                            row.get("idRecursoUso"), exc)
        logger.info("Sesión de recurso %s (idRecurso=%s) expirada automáticamente",
                    row.get("idRecursoUso"), row.get("idRecurso"))


def _loop() -> None:
    logger.info("Worker de expiración de recursos iniciado")
    while True:
        try:
            _tick()
        except Exception as exc:  # noqa: BLE001 — el worker nunca debe morir
            logger.warning("Worker de expiración de recursos: %s", exc)
        time.sleep(POLL_S)


def start_worker() -> None:
    """Arranca el hilo (idempotente). Llamar una vez desde main.py."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(
            target=_loop, daemon=True, name="resource-session-expiry"
        )
        _worker_thread.start()
