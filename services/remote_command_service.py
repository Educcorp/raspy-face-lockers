"""
Puente web → Pi para abrir lockers a distancia.

La web (Railway) no puede tocar los GPIO de la Pi, así que escribe comandos en
`comandos_locker` y esta Pi los ejecuta. El mismo hilo publica en `estado_puerta`
el estado de los sensores de puerta; esa tabla es también el "latido" con el que
la web sabe si la Pi está conectada.

Seguridad: un comando pendiente solo se ejecuta si tiene menos de
`COMMAND_MAX_AGE_S` segundos. Una Pi que estuvo apagada NO debe abrir lockers
horas después por clics viejos.
"""

from __future__ import annotations

import logging
import threading
import time

from config import DOOR_SWITCH_CONFIG
from database.connection import execute, fetch_all
from services import locker_service

logger = logging.getLogger(__name__)

DOOR_TICK_S = 0.5          # cada cuánto se leen los sensores
COMMAND_POLL_S = 1.5       # cada cuánto se consulta la cola de comandos
HEARTBEAT_S = 10.0         # republicar el estado aunque no cambie
COMMAND_MAX_AGE_S = 30     # más viejo que esto → 'expirado', nunca se ejecuta

_worker_lock = threading.Lock()
_worker_thread: threading.Thread | None = None


def _claim_pending() -> list[dict]:
    """Toma (atómicamente) los comandos pendientes y frescos. Varios procesos
    pueden competir: `SKIP LOCKED` garantiza que solo uno se lleve cada comando."""
    return fetch_all(
        """
        UPDATE comandos_locker
           SET estado = 'ejecutando', fechaHoraEjecucion = now()
         WHERE idComando IN (
                SELECT idComando FROM comandos_locker
                 WHERE estado = 'pendiente'
                   AND accion = 'abrir'
                   AND fechaHoraSolicitud > now() - make_interval(secs => %s)
                 ORDER BY idComando
                 FOR UPDATE SKIP LOCKED
         )
        RETURNING idComando AS "idComando", idLocker AS "idLocker"
        """,
        (COMMAND_MAX_AGE_S,),
    )


def _expire_stale() -> None:
    """Cierra comandos que nunca se ejecutaron (Pi offline) o se quedaron colgados."""
    execute(
        """
        UPDATE comandos_locker
           SET estado = 'expirado', detalle = 'No se ejecutó a tiempo'
         WHERE estado = 'pendiente'
           AND fechaHoraSolicitud <= now() - make_interval(secs => %s)
        """,
        (COMMAND_MAX_AGE_S,),
    )
    execute(
        """
        UPDATE comandos_locker
           SET estado = 'error', detalle = 'La Raspberry no confirmó la ejecución'
         WHERE estado = 'ejecutando'
           AND fechaHoraEjecucion <= now() - interval '60 seconds'
        """
    )


def _finish(command_id: int, ok: bool, detail: str | None = None) -> None:
    execute(
        "UPDATE comandos_locker SET estado=%s, detalle=%s WHERE idComando=%s",
        ("completado" if ok else "error", detail, command_id),
    )


def _run_command(command: dict) -> None:
    """Ejecuta un comando en su propio hilo: el relé se mantiene segundos y el
    bucle principal no debe dejar de publicar el estado de las puertas."""
    cid, lid = int(command["idComando"]), int(command["idLocker"])
    try:
        ok = locker_service.open_locker(lid, seconds=locker_service.MANUAL_OPEN_SECONDS)
        detail = None if ok else "No se pudo activar el relé (¿locker sin relé o ya en apertura?)"
    except Exception as exc:  # noqa: BLE001 — cualquier fallo debe quedar registrado
        logger.error("Comando %s (locker %s) falló: %s", cid, lid, exc)
        ok, detail = False, f"Error: {str(exc)[:150]}"
    try:
        _finish(cid, ok, detail)
    except Exception as exc:  # noqa: BLE001
        logger.error("No se pudo cerrar el comando %s: %s", cid, exc)
    logger.info("Comando remoto %s: abrir locker %s → %s", cid, lid, "OK" if ok else "ERROR")


def _read_doors() -> dict[int, bool | None]:
    """Estado actual de cada puerta con sensor (True=cerrada, False=abierta, None=sin lectura)."""
    from core.door_switch_controller import get_door_switch_controller

    controller = get_door_switch_controller()
    ids = [int(x) for x in DOOR_SWITCH_CONFIG.get("active_lockers", [])]
    if not controller.is_available():
        return {lid: None for lid in ids}
    return {lid: controller.read_state(lid) for lid in ids}


def _publish_doors(doors: dict[int, bool | None]) -> None:
    """Upsert de todas las puertas en UNA sentencia (solo lockers que existen en la BD)."""
    if not doors:
        return
    items = sorted(doors.items())
    values = ", ".join("(%s, %s::boolean)" for _ in items)
    params: list = []
    for lid, closed in items:
        params += [lid, closed]
    execute(
        f"""
        INSERT INTO estado_puerta (idLocker, cerrada, fechaHoraAct)
        SELECT v.id, v.c, now()
          FROM (VALUES {values}) AS v(id, c)
          JOIN lockers l ON l.idLocker = v.id
        ON CONFLICT (idLocker)
        DO UPDATE SET cerrada = EXCLUDED.cerrada, fechaHoraAct = now()
        """,
        tuple(params),
    )


def _loop() -> None:
    last_doors: dict[int, bool | None] | None = None
    last_publish = 0.0
    last_poll = 0.0
    last_expire = 0.0
    logger.info("Servicio de comandos remotos iniciado")

    while True:
        now = time.monotonic()
        try:
            doors = _read_doors()
            if doors != last_doors or now - last_publish >= HEARTBEAT_S:
                _publish_doors(doors)
                last_doors, last_publish = doors, now

            if now - last_poll >= COMMAND_POLL_S:
                last_poll = now
                for command in _claim_pending():
                    threading.Thread(
                        target=_run_command, args=(command,), daemon=True,
                        name=f"remote-open-{command['idLocker']}",
                    ).start()

            if now - last_expire >= HEARTBEAT_S:
                last_expire = now
                _expire_stale()
        except Exception as exc:  # noqa: BLE001 — el servicio nunca debe morir
            logger.warning("Servicio de comandos remotos: %s", exc)
            time.sleep(3.0)
        time.sleep(DOOR_TICK_S)


def start_worker() -> None:
    """Arranca el hilo (idempotente). Llamar una vez desde main.py."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(
            target=_loop, daemon=True, name="remote-commands"
        )
        _worker_thread.start()
