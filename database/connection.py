"""
database/connection.py – Conexión a la base de datos Postgres remota (Railway).

Misma base de datos que usa el panel web (webapp/db.py): el esquema vive en
webapp/schema.sql y ya está aplicado en Railway, así que este módulo NO
intenta crear ni migrar tablas — solo se conecta y ejecuta SQL.

POOL DE CONEXIONES
------------------
La versión anterior abría una conexión nueva en cada llamada. Contra un
Postgres local eso es despreciable, pero contra el TCP proxy de Railway el
handshake (TCP + TLS + autenticación) se midió en ~918 ms, mientras que la
consulta en sí cuesta ~141 ms: el 87% del tiempo se iba en reconectar. Con un
pool las conexiones se reutilizan y ese costo se paga una sola vez.

Se usa ThreadedConnectionPool porque hay varios hilos vivos (bucle de cámara,
apertura de lockers, registro de accesos) y cada uno necesita su propia
conexión: compartir una sola entre hilos mezclaría sus transacciones.

API pública (sin cambios de firma respecto a la versión anterior, para que
services/*.py y ui/admin/*.py no necesiten tocar sus imports):
    db_session()               – context manager: conexión del pool
    fetch_all(sql, params)     – list[dict]
    fetch_one(sql, params)     – dict | None
    execute(sql, params)       – rowcount
    execute_returning(sql, params) – dict | None (para INSERT ... RETURNING)
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

from config import DATABASE_URL

logger = logging.getLogger(__name__)

# maxconn cubre con holgura los hilos simultáneos del kiosko (UI + detección +
# apertura de locker + registro de acceso); si se agotara, getconn lanzaría
# PoolError en vez de bloquear, así que se deja margen.
_MIN_CONN = 1
_MAX_CONN = 6

# Límite de operaciones simultáneas contra la base remota.
#
# Medido en esta Raspberry contra el proxy TCP de Railway: el rendimiento NO
# crece con la concurrencia, se derrumba. Con 36 consultas repartidas en 6
# hilos: límite 1 -> 6.9 ops/s, límite 2 -> 8.4 ops/s, límite 3 -> 2.1 ops/s,
# sin límite -> 1.4 ops/s (y la latencia por operación pasó de 162 ms a más de
# 4 s). Dos en vuelo es el punto óptimo; a partir de tres el proxy se degrada.
#
# El pool permite más conexiones que esto a propósito: el semáforo regula
# cuántas están *ejecutando*, no cuántas existen, para que una conexión ya
# abierta no se cierre solo por esperar turno.
_MAX_INFLIGHT = 2
_inflight = threading.BoundedSemaphore(_MAX_INFLIGHT)

# Profundidad por hilo: si una operación anida otra (p. ej. un fetch dentro de
# un db_session abierto), el hilo ya tiene el permiso y no debe pedir otro, o
# se bloquearía a sí mismo.
_depth = threading.local()

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()

# Errores que indican que la conexión murió (Railway corta conexiones ociosas).
# No son errores de SQL: la misma sentencia suele funcionar al reintentar.
_CONN_ERRORS = (psycopg2.OperationalError, psycopg2.InterfaceError)


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Crea el pool la primera vez que se necesita (doble verificación bajo
    lock para que dos hilos no lo creen a la vez)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                if not DATABASE_URL:
                    raise RuntimeError(
                        "DATABASE_URL no está configurada. Copia .env.example a .env "
                        "y coloca la cadena de conexión de Postgres (Railway)."
                    )
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    _MIN_CONN,
                    _MAX_CONN,
                    DATABASE_URL,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                    # Keepalives TCP: sin esto, una conexión ociosa en el pool
                    # puede quedar muerta sin avisar tras pasar por el proxy, y
                    # el fallo aparecería recién al ejecutar la siguiente query.
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3,
                )
                logger.info("Pool de conexiones Postgres creado (%d-%d)", _MIN_CONN, _MAX_CONN)
    return _pool


def warmup(connections: int = 3) -> None:
    """
    Abre de antemano varias conexiones y las devuelve al pool.

    psycopg2 crea las conexiones bajo el lock interno del pool, así que si
    varios hilos piden conexión en frío a la vez sus handshakes se serializan
    (se midieron ~918 ms cada uno). Llamar a esto en segundo plano al arrancar
    hace que el kiosko encuentre el pool ya caliente.

    Es best-effort: si no hay red, se registra y se sigue — la app ya tolera
    fallos de BD en sus llamadas.
    """
    try:
        pool = _get_pool()
        held = [pool.getconn() for _ in range(max(1, min(connections, _MAX_CONN)))]
        for conn in held:
            conn.autocommit = True
            pool.putconn(conn)
        logger.info("Pool precalentado con %d conexiones", len(held))
    except Exception as exc:
        logger.warning("No se pudo precalentar el pool de conexiones: %s", exc)


def close_pool() -> None:
    """Cierra todas las conexiones. Se llama al apagar la aplicación."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.closeall()
            except Exception as exc:  # pragma: no cover - limpieza best-effort
                logger.debug("Error cerrando el pool: %s", exc)
            _pool = None


class _ConnWrapper:
    """Envuelve una conexión psycopg2 para que `conn.execute(sql, params)`
    siga funcionando como en sqlite3.Connection (que sí trae ese atajo).
    Devuelve el cursor real para poder encadenar .fetchone()/.fetchall().

    Los cursores se registran para cerrarlos al devolver la conexión al pool:
    antes se cerraban solos al cerrar la conexión, pero ahora la conexión
    sobrevive y los cursores se acumularían.
    """

    def __init__(self, conn) -> None:
        self._conn = conn
        self._cursors: list = []

    def execute(self, sql: str, params: tuple = ()):
        cur = self._conn.cursor()
        self._cursors.append(cur)
        cur.execute(sql, params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        """No cierra la conexión: pertenece al pool y db_session la devuelve.
        Se mantiene por compatibilidad con la API anterior."""
        self._release_cursors()

    def _release_cursors(self) -> None:
        for cur in self._cursors:
            try:
                cur.close()
            except Exception:
                pass
        self._cursors.clear()


@contextmanager
def _pooled(transactional: bool):
    """
    Toma una conexión del pool y la devuelve al terminar.

    `transactional=False` pone la conexión en autocommit, que para una
    sentencia suelta ahorra DOS viajes de red completos (~280 ms contra
    Railway): el COMMIT explícito, y el ROLLBACK que psycopg2 dispara al
    devolver al pool una conexión con transacción abierta. Con autocommit la
    conexión vuelve IDLE y ninguno de los dos ocurre.

    `transactional=True` es el modo clásico, necesario cuando varias
    sentencias deben confirmarse juntas o ninguna.
    """
    depth = getattr(_depth, "value", 0)
    acquired = False
    if depth == 0:
        _inflight.acquire()
        acquired = True
    _depth.value = depth + 1

    try:
        pool = _get_pool()
        conn = pool.getconn()
    except BaseException:
        _depth.value = depth
        if acquired:
            _inflight.release()
        raise

    wrapper = _ConnWrapper(conn)
    discard = False
    try:
        conn.autocommit = not transactional
        yield wrapper
        if transactional:
            conn.commit()
    except BaseException as exc:
        # Si la conexión murió no tiene sentido hacer rollback ni reciclarla.
        discard = isinstance(exc, _CONN_ERRORS)
        if transactional and not discard:
            try:
                conn.rollback()
            except Exception:
                discard = True
        raise
    finally:
        wrapper._release_cursors()
        if not discard:
            try:
                # Devolverla en autocommit deja el estado IDLE y evita que
                # putconn gaste otro viaje en un rollback de cortesía.
                conn.autocommit = True
            except Exception:
                discard = True
        try:
            pool.putconn(conn, close=discard)
        except Exception as exc:  # pragma: no cover
            logger.debug("Error devolviendo la conexión al pool: %s", exc)
        _depth.value = depth
        if acquired:
            _inflight.release()


@contextmanager
def db_session():
    """
    Context manager transaccional: todas las sentencias del bloque se
    confirman juntas al salir, o se revierten si algo falla.
    Uso:
        with db_session() as conn:
            conn.execute(...)
    """
    with _pooled(transactional=True) as conn:
        yield conn


def _run(sql: str, params: tuple, mode: str):
    """Ejecuta una sentencia suelta, reintentando una vez si la conexión que
    entregó el pool estaba muerta.

    El reintento es seguro porque aquí solo se ejecuta UNA sentencia: no hay
    trabajo previo en la transacción que pudiera repetirse. Por eso db_session()
    (multi-sentencia) no reintenta — repetir un bloque a medias sí sería
    peligroso.
    """
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            with _pooled(transactional=False) as conn:
                cur = conn.execute(sql, params)
                if mode == "all":
                    return [dict(r) for r in cur.fetchall()]
                if mode == "one":
                    row = cur.fetchone()
                    return dict(row) if row else None
                return cur.rowcount
        except _CONN_ERRORS as exc:
            last_exc = exc
            if attempt == 1:
                logger.warning("Conexión a la BD perdida (%s); reintentando", exc)
    raise last_exc  # type: ignore[misc]


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    """Ejecuta SELECT y devuelve lista de dicts."""
    return _run(sql, params, "all")


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    """Ejecuta SELECT y devuelve un dict o None."""
    return _run(sql, params, "one")


def execute(sql: str, params: tuple = ()) -> int:
    """Ejecuta INSERT / UPDATE / DELETE. Devuelve el número de filas afectadas."""
    return _run(sql, params, "rowcount")


def execute_returning(sql: str, params: tuple = ()) -> dict | None:
    """Ejecuta un INSERT/UPDATE con cláusula RETURNING y devuelve la primera fila."""
    return _run(sql, params, "one")
