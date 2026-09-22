"""
database/connection.py – Conexión a la base de datos Postgres remota (Railway).

Misma base de datos que usa el panel web (webapp/db.py): el esquema vive en
webapp/schema.sql y ya está aplicado en Railway, así que este módulo NO
intenta crear ni migrar tablas — solo se conecta y ejecuta SQL.

API pública (sin cambios de firma respecto a la versión SQLite anterior,
para que services/*.py y ui/admin/*.py no necesiten tocar sus imports):
    db_session()               – context manager: conexión nueva por llamada
    fetch_all(sql, params)     – list[dict]
    fetch_one(sql, params)     – dict | None
    execute(sql, params)       – rowcount
    execute_returning(sql, params) – dict | None (para INSERT ... RETURNING)
"""

from __future__ import annotations

from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import DATABASE_URL


class _ConnWrapper:
    """Envuelve una conexión psycopg2 para que `conn.execute(sql, params)`
    siga funcionando como en sqlite3.Connection (que sí trae ese atajo).
    Devuelve el cursor real para poder encadenar .fetchone()/.fetchall()."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def _connect():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL no está configurada. Copia .env.example a .env "
            "y coloca la cadena de conexión de Postgres (Railway)."
        )
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


@contextmanager
def db_session():
    """
    Context manager que abre una conexión nueva, confirma y cierra.
    Uso:
        with db_session() as conn:
            conn.execute(...)
    """
    conn = _connect()
    wrapper = _ConnWrapper(conn)
    try:
        yield wrapper
        wrapper.commit()
    except Exception:
        wrapper.rollback()
        raise
    finally:
        wrapper.close()


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    """Ejecuta SELECT y devuelve lista de dicts."""
    with db_session() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    """Ejecuta SELECT y devuelve un dict o None."""
    with db_session() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def execute(sql: str, params: tuple = ()) -> int:
    """Ejecuta INSERT / UPDATE / DELETE. Devuelve el número de filas afectadas."""
    with db_session() as conn:
        cur = conn.execute(sql, params)
        return cur.rowcount


def execute_returning(sql: str, params: tuple = ()) -> dict | None:
    """Ejecuta un INSERT/UPDATE con cláusula RETURNING y devuelve la primera fila."""
    with db_session() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None
