"""Operaciones de negocio sobre usuarios (panel web — sin captura facial)."""

from __future__ import annotations

import hashlib

from webapp.db import execute, execute_returning, fetch_all, fetch_one


def get_all_users() -> list[dict]:
    return fetch_all(
        """
        SELECT u.idUsuario, u.nombre, u.apPaterno, u.apMaterno,
               u.matricula, u.emailInst, u.tel, u.estado,
               t.nombreTipoUsuario AS tipo,
               ua.nombreUnidadAcademica AS unidad,
               (SELECT COUNT(*) FROM encoding e
                 WHERE e.idUsuario = u.idUsuario AND e.estado = 'activo') AS n_encodings
        FROM usuarios u
        LEFT JOIN tipo_usuarios t ON t.idTipoUsuario = u.idTipoUsuario
        LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = u.idUnidadAcademica
        ORDER BY u.nombre, u.apPaterno
        """
    )


def get_user_by_id(user_id: int) -> dict | None:
    return fetch_one(
        """
        SELECT u.*, t.nombreTipoUsuario AS tipo,
               ua.nombreUnidadAcademica AS unidad
        FROM usuarios u
        LEFT JOIN tipo_usuarios t ON t.idTipoUsuario = u.idTipoUsuario
        LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = u.idUnidadAcademica
        WHERE u.idUsuario = %s
        """,
        (user_id,),
    )


def count_face_encodings(user_id: int) -> int:
    row = fetch_one(
        "SELECT COUNT(*) AS n FROM encoding WHERE idUsuario=%s AND estado='activo'",
        (user_id,),
    )
    return row["n"] if row else 0


def create_user_pending_encoding(data: dict) -> int:
    """
    Da de alta un usuario sin rostro registrado (esto último solo puede
    hacerse físicamente en el kiosco de la Raspberry Pi). El usuario queda
    visible ahí como 'pendiente de registro facial' hasta que un operador
    lo escanee en el dispositivo.
    """
    row = execute_returning(
        """
        INSERT INTO usuarios
            (nombre, apPaterno, apMaterno, idTipoUsuario, idUnidadAcademica,
             emailInst, tel, matricula, pin, creadoPor)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING idUsuario
        """,
        (
            data["nombre"], data["apPaterno"], data.get("apMaterno"),
            data["idTipoUsuario"], data["idUnidadAcademica"],
            data["emailInst"], data.get("tel"),
            data["matricula"], data["pin_hash"], data["creadoPor"],
        ),
    )
    return row["idusuario"]


def update_user(user_id: int, data: dict) -> None:
    execute(
        """
        UPDATE usuarios SET
            nombre=%s, apPaterno=%s, apMaterno=%s,
            matricula=%s, emailInst=%s, tel=%s,
            idTipoUsuario=%s, idUnidadAcademica=%s,
            estado=%s, modificadoPor=%s
        WHERE idUsuario=%s
        """,
        (
            data["nombre"], data["apPaterno"], data.get("apMaterno"),
            data["matricula"], data["emailInst"], data.get("tel"),
            data["idTipoUsuario"], data["idUnidadAcademica"],
            data.get("estado", "activo"), data["modificadoPor"],
            user_id,
        ),
    )


def update_pin(user_id: int, new_pin: str, modificado_por: int) -> None:
    hashed = hashlib.sha256(new_pin.strip().encode()).hexdigest()
    execute(
        "UPDATE usuarios SET pin=%s, modificadoPor=%s WHERE idUsuario=%s",
        (hashed, modificado_por, user_id),
    )


def set_user_status(user_id: int, estado: str, modificado_por: int) -> None:
    execute(
        "UPDATE usuarios SET estado=%s, modificadoPor=%s WHERE idUsuario=%s",
        (estado, modificado_por, user_id),
    )


def delete_user_permanent(user_id: int) -> None:
    execute("DELETE FROM asignacion_locker WHERE idUsuario=%s", (user_id,))
    execute("DELETE FROM encoding WHERE idUsuario=%s", (user_id,))
    execute("DELETE FROM usuarios WHERE idUsuario=%s", (user_id,))


def email_exists(email: str, exclude_user_id: int | None = None) -> bool:
    if exclude_user_id is not None:
        row = fetch_one(
            "SELECT 1 FROM usuarios WHERE emailInst=%s AND idUsuario!=%s LIMIT 1",
            (email.strip(), exclude_user_id),
        )
    else:
        row = fetch_one("SELECT 1 FROM usuarios WHERE emailInst=%s LIMIT 1", (email.strip(),))
    return row is not None


def matricula_exists(matricula: int | str, exclude_user_id: int | None = None) -> bool:
    if exclude_user_id is not None:
        row = fetch_one(
            "SELECT 1 FROM usuarios WHERE matricula=%s AND idUsuario!=%s LIMIT 1",
            (int(matricula), exclude_user_id),
        )
    else:
        row = fetch_one("SELECT 1 FROM usuarios WHERE matricula=%s LIMIT 1", (int(matricula),))
    return row is not None


def nombre_completo_exists(
    nombre: str,
    ap_paterno: str,
    ap_materno: str | None = None,
    exclude_user_id: int | None = None,
) -> bool:
    if ap_materno:
        sql = "SELECT 1 FROM usuarios WHERE nombre=%s AND apPaterno=%s AND apMaterno=%s"
        params: tuple = (nombre, ap_paterno, ap_materno)
    else:
        sql = (
            "SELECT 1 FROM usuarios WHERE nombre=%s AND apPaterno=%s "
            "AND (apMaterno IS NULL OR apMaterno='')"
        )
        params = (nombre, ap_paterno)

    if exclude_user_id is not None:
        sql += " AND idUsuario!=%s"
        params += (exclude_user_id,)
    sql += " LIMIT 1"
    return fetch_one(sql, params) is not None
