"""CRUD de catálogos: tipos de usuario, unidades académicas y áreas de lockers."""

from __future__ import annotations

from webapp.db import execute, execute_returning, fetch_all, fetch_one


# ── Tipos de usuario ─────────────────────────────────────────────────────────

def get_all_tipos_usuario() -> list[dict]:
    return fetch_all("SELECT * FROM tipo_usuarios ORDER BY nombreTipoUsuario")


def create_tipo_usuario(nombre: str, creado_por: int) -> int:
    row = execute_returning(
        "INSERT INTO tipo_usuarios (nombreTipoUsuario, creadoPor) VALUES (%s, %s) "
        "RETURNING idTipoUsuario",
        (nombre, creado_por),
    )
    return row["idtipousuario"]


def update_tipo_usuario(tipo_id: int, nombre: str, estado: str, modificado_por: int) -> None:
    execute(
        "UPDATE tipo_usuarios SET nombreTipoUsuario=%s, estado=%s, modificadoPor=%s "
        "WHERE idTipoUsuario=%s",
        (nombre, estado, modificado_por, tipo_id),
    )


def tipo_usuario_nombre_exists(nombre: str, exclude_id: int | None = None) -> bool:
    if exclude_id is not None:
        row = fetch_one(
            "SELECT 1 FROM tipo_usuarios WHERE nombreTipoUsuario=%s AND idTipoUsuario!=%s LIMIT 1",
            (nombre, exclude_id),
        )
    else:
        row = fetch_one(
            "SELECT 1 FROM tipo_usuarios WHERE nombreTipoUsuario=%s LIMIT 1", (nombre,)
        )
    return row is not None


def count_usuarios_by_tipo(tipo_id: int) -> int:
    row = fetch_one(
        "SELECT COUNT(*) AS n FROM usuarios WHERE idTipoUsuario=%s", (tipo_id,)
    )
    return row["n"] if row else 0


# ── Unidades académicas ──────────────────────────────────────────────────────

def get_all_unidades() -> list[dict]:
    return fetch_all("SELECT * FROM unidad_academica ORDER BY nombreUnidadAcademica")


def get_active_unidades() -> list[dict]:
    return fetch_all(
        "SELECT * FROM unidad_academica WHERE estado='activo' ORDER BY nombreUnidadAcademica"
    )


def create_unidad(nombre: str, zona: str | None, creado_por: int) -> int:
    row = execute_returning(
        "INSERT INTO unidad_academica (nombreUnidadAcademica, zona, creadoPor) "
        "VALUES (%s, %s, %s) RETURNING idUnidadAcademica",
        (nombre, zona, creado_por),
    )
    return row["idunidadacademica"]


def update_unidad(unidad_id: int, nombre: str, zona: str | None, estado: str, modificado_por: int) -> None:
    execute(
        "UPDATE unidad_academica SET nombreUnidadAcademica=%s, zona=%s, estado=%s, "
        "modificadoPor=%s WHERE idUnidadAcademica=%s",
        (nombre, zona, estado, modificado_por, unidad_id),
    )


def unidad_nombre_exists(nombre: str, exclude_id: int | None = None) -> bool:
    if exclude_id is not None:
        row = fetch_one(
            "SELECT 1 FROM unidad_academica WHERE nombreUnidadAcademica=%s "
            "AND idUnidadAcademica!=%s LIMIT 1",
            (nombre, exclude_id),
        )
    else:
        row = fetch_one(
            "SELECT 1 FROM unidad_academica WHERE nombreUnidadAcademica=%s LIMIT 1", (nombre,)
        )
    return row is not None


def count_usuarios_by_unidad(unidad_id: int) -> int:
    row = fetch_one(
        "SELECT COUNT(*) AS n FROM usuarios WHERE idUnidadAcademica=%s AND estado != 'eliminado'",
        (unidad_id,),
    )
    return row["n"] if row else 0


def delete_unidad(unidad_id: int) -> None:
    execute("DELETE FROM unidad_academica WHERE idUnidadAcademica=%s", (unidad_id,))


# ── Áreas de lockers ──────────────────────────────────────────────────────────

def get_all_areas() -> list[dict]:
    return fetch_all(
        """
        SELECT a.*, ua.nombreUnidadAcademica AS nombreUnidad
        FROM area_lockers a
        LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = a.idUnidadAcademica
        ORDER BY a.nombreArea
        """
    )


def get_active_areas() -> list[dict]:
    return fetch_all("SELECT * FROM area_lockers WHERE estado='activo' ORDER BY nombreArea")


def create_area(nombre: str, unidad_id: int | None, creado_por: int) -> int:
    row = execute_returning(
        "INSERT INTO area_lockers (nombreArea, idUnidadAcademica, creadoPor) "
        "VALUES (%s, %s, %s) RETURNING idArea",
        (nombre, unidad_id, creado_por),
    )
    return row["idarea"]


def update_area(area_id: int, nombre: str, unidad_id: int | None, estado: str, modificado_por: int) -> None:
    execute(
        "UPDATE area_lockers SET nombreArea=%s, idUnidadAcademica=%s, estado=%s, "
        "modificadoPor=%s WHERE idArea=%s",
        (nombre, unidad_id, estado, modificado_por, area_id),
    )


def area_nombre_exists(nombre: str, exclude_id: int | None = None) -> bool:
    if exclude_id is not None:
        row = fetch_one(
            "SELECT 1 FROM area_lockers WHERE nombreArea=%s AND idArea!=%s LIMIT 1",
            (nombre, exclude_id),
        )
    else:
        row = fetch_one("SELECT 1 FROM area_lockers WHERE nombreArea=%s LIMIT 1", (nombre,))
    return row is not None


def count_lockers_by_area(area_id: int) -> int:
    row = fetch_one("SELECT COUNT(*) AS n FROM lockers WHERE idArea=%s", (area_id,))
    return row["n"] if row else 0


def delete_area(area_id: int) -> None:
    execute("DELETE FROM area_lockers WHERE idArea=%s", (area_id,))
