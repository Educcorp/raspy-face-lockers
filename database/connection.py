"""
database/connection.py – Conexión ligera al SQLite existente.

El archivo de base de datos se encuentra en:
    database/migrations/raspi-face-lockers.db

Se usa sqlite3 directamente (sin ORM) para mantener simple la capa de datos
y facilitar el CRUD desde el panel de administración 480×800 px.
"""

import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager

# ── Ruta absoluta al archivo DB ───────────────────────────────────────────────
_HERE = Path(__file__).parent
DB_PATH = str(_HERE / "migrations" / "raspi-face-lockers.db")


def get_connection() -> sqlite3.Connection:
    """Devuelve una conexión SQLite con row_factory para acceso por nombre."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    """
    Context manager que abre conexión, confirma y cierra.
    Uso:
        with db_session() as conn:
            conn.execute(...)
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
    """
    Ejecuta INSERT / UPDATE / DELETE.
    Devuelve lastrowid para INSERT, rows_affected para otros.
    """
    with db_session() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid or cur.rowcount
