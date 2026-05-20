"""
database/connection.py – Conexión ligera al SQLite existente.

El archivo de base de datos se encuentra en:
    database/migrations/raspi-face-lockers.db

Se usa sqlite3 directamente (sin ORM) para mantener simple la capa de datos
y facilitar el CRUD desde el panel de administración 480×800 px.
"""

import sqlite3
import shutil
from pathlib import Path
from contextlib import contextmanager

# ── Rutas de DB y schema ──────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_MIGRATIONS_DIR = _HERE / "migrations"
_PRIMARY_DB_PATH = _MIGRATIONS_DIR / "raspi-face-lockers.db"
_LEGACY_DB_PATH = _MIGRATIONS_DIR / "raspi-face-lockers .db"  # typo historico
_INIT_SQL_PATH = _MIGRATIONS_DIR / "init_db.sql"

DB_PATH = str(_PRIMARY_DB_PATH)
_DB_READY = False


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _has_minimum_schema(conn: sqlite3.Connection) -> bool:
    return _table_exists(conn, "usuarios") and _table_exists(conn, "tipo_usuarios")


def _adopt_legacy_db_if_needed() -> None:
    """Migra automaticamente la DB legacy mal nombrada al nombre canonico."""
    if not _LEGACY_DB_PATH.exists():
        return

    legacy_has_data = _LEGACY_DB_PATH.stat().st_size > 0
    primary_missing_or_empty = (not _PRIMARY_DB_PATH.exists()) or (_PRIMARY_DB_PATH.stat().st_size == 0)

    if legacy_has_data and primary_missing_or_empty:
        shutil.copy2(_LEGACY_DB_PATH, _PRIMARY_DB_PATH)


def _run_init_script(conn: sqlite3.Connection) -> None:
    if not _INIT_SQL_PATH.exists():
        raise RuntimeError(f"No existe schema SQL: {_INIT_SQL_PATH}")

    script = _INIT_SQL_PATH.read_text(encoding="utf-8").strip()
    if not script:
        raise RuntimeError(
            "El archivo init_db.sql esta vacio. Restaura database/migrations/init_db.sql."
        )

    conn.executescript(script)
    conn.commit()


def _apply_incremental_migrations(conn: sqlite3.Connection) -> None:
    """Aplica cambios de esquema incrementales que no están en init_db.sql."""
    try:
        conn.execute(
            "ALTER TABLE area_lockers ADD COLUMN idUnidadAcademica INTEGER "
            "REFERENCES unidad_academica(idUnidadAcademica)"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # la columna ya existe


def _ensure_database_ready() -> None:
    global _DB_READY
    if _DB_READY:
        return

    _MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    _adopt_legacy_db_if_needed()

    conn = sqlite3.connect(str(_PRIMARY_DB_PATH))
    try:
        if not _has_minimum_schema(conn):
            _run_init_script(conn)
        _apply_incremental_migrations(conn)
    finally:
        conn.close()

    _DB_READY = True


def get_connection() -> sqlite3.Connection:
    """Devuelve una conexión SQLite con row_factory para acceso por nombre."""
    _ensure_database_ready()
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
