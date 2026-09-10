"""
Capa de acceso a la base de datos remota (PostgreSQL) del panel web.

Misma base de datos que usa el dispositivo Raspberry Pi (que sigue
ejecutando reconocimiento facial y GPIO de forma local); este módulo
solo la consulta y administra vía red.
"""

from __future__ import annotations

from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from flask import current_app, g

from webapp.config import DATABASE_URL


def get_connection():
    if "db_conn" not in g:
        g.db_conn = psycopg2.connect(
            current_app.config.get("DATABASE_URL", DATABASE_URL),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return g.db_conn


def close_connection(_exc=None) -> None:
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


@contextmanager
def cursor():
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return dict(row) if row else None


def execute(sql: str, params: tuple = ()) -> int:
    """Ejecuta INSERT/UPDATE/DELETE. Devuelve el número de filas afectadas."""
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def execute_returning(sql: str, params: tuple = ()):
    """Ejecuta un INSERT/UPDATE con cláusula RETURNING y devuelve la primera fila."""
    with cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return dict(row) if row else None


def init_app(app) -> None:
    app.teardown_appcontext(close_connection)
