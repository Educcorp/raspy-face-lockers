"""Operaciones de negocio sobre usuarios, incluida la biometría facial."""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

import numpy as np

from webapp.db import cursor, execute, execute_returning, fetch_all, fetch_one

logger = logging.getLogger(__name__)


def get_all_users() -> list[dict]:
    return fetch_all(
        """
        SELECT u.idusuario, u.nombre, u.appaterno, u.apmaterno,
               u.matricula, u.emailinst, u.tel, u.estado,
               u.permisoactivacion,
               t.nombretipousuario AS tipo,
               ua.nombreunidadacademica AS unidad,
               (SELECT COUNT(*) FROM encoding e
                 WHERE e.idusuario = u.idusuario AND e.estado = 'activo') AS n_encodings
        FROM usuarios u
        LEFT JOIN tipo_usuarios t ON t.idtipousuario = u.idtipousuario
        LEFT JOIN unidad_academica ua ON ua.idunidadacademica = u.idunidadacademica
        ORDER BY u.nombre, u.appaterno
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
             emailInst, tel, matricula, pin, permisoActivacion, creadoPor)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING idUsuario
        """,
        (
            data["nombre"], data["apPaterno"], data.get("apMaterno"),
            data["idTipoUsuario"], data["idUnidadAcademica"],
            data["emailInst"], data.get("tel"),
            data["matricula"], data["pin_hash"],
            data.get("permisoActivacion", "locker"), data["creadoPor"],
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
            estado=%s, permisoActivacion=%s, modificadoPor=%s
        WHERE idUsuario=%s
        """,
        (
            data["nombre"], data["apPaterno"], data.get("apMaterno"),
            data["matricula"], data["emailInst"], data.get("tel"),
            data["idTipoUsuario"], data["idUnidadAcademica"],
            data.get("estado", "activo"),
            data.get("permisoActivacion", "locker"), data["modificadoPor"],
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


# ── Biometría facial (captura desde el navegador) ─────────────────────────────

def get_active_face_encodings(exclude_user_id: Optional[int] = None) -> list[dict]:
    """
    Carga los encodings activos de usuarios activos, deserializando el vector
    BYTEA a numpy. Se usa para el chequeo de duplicados al registrar un rostro.
    """
    rows = fetch_all(
        """
        SELECT e.idUsuario, e.vector, e.dimension, e.vectorDtype, e.modelo,
               u.nombre, u.apPaterno, u.matricula
        FROM encoding e
        JOIN usuarios u ON u.idUsuario = e.idUsuario
        WHERE e.estado = 'activo' AND u.estado = 'activo'
        """
    )

    parsed: list[dict] = []
    for row in rows:
        if exclude_user_id is not None and row.get("idusuario") == exclude_user_id:
            continue
        raw = row.get("vector")
        if raw is None:
            continue
        dim = int(row.get("dimension") or 128)
        dtype = np.float64 if (row.get("vectordtype") or "float32").strip().lower() == "float64" else np.float32

        vector_np = np.frombuffer(bytes(raw), dtype=dtype)
        if vector_np.size != dim:
            logger.warning(
                "Encoding inválido usuario=%s esperado=%s real=%s",
                row.get("idusuario"), dim, vector_np.size,
            )
            continue
        if dtype != np.float32:
            vector_np = vector_np.astype(np.float32)

        row["vector_np"] = vector_np
        parsed.append(row)

    return parsed


def threshold_for_model(model_prefix: Optional[str]) -> float:
    """Umbral de distancia euclidiana según modelo de embedding."""
    if (model_prefix or "").startswith("fallback"):
        return 0.75
    return 0.44


def find_best_face_match(
    probe_embedding: np.ndarray,
    model_prefix: str,
    candidates: list[dict],
) -> tuple[dict | None, dict | None]:
    """
    Busca el mejor candidato facial aplicando umbral y filtro de margen
    (idéntica lógica a services/user_service.py del Pi, para mantener
    consistencia en el chequeo antifraude de rostros duplicados).
    """
    MIN_MARGIN = 0.10
    threshold = threshold_for_model(model_prefix)

    user_best: dict[int, dict] = {}
    for candidate in candidates:
        if not (candidate.get("modelo") or "").startswith(model_prefix):
            continue
        stored_vec = candidate.get("vector_np")
        if stored_vec is None:
            continue
        dist = float(np.linalg.norm(probe_embedding - stored_vec))
        uid = int(candidate["idusuario"])
        if uid not in user_best or dist < user_best[uid]["distance"]:
            user_best[uid] = {"candidate": candidate, "distance": dist}

    if not user_best:
        return None, None

    ranked = sorted(user_best.values(), key=lambda x: x["distance"])
    best_distance = ranked[0]["distance"]
    second_distance = ranked[1]["distance"] if len(ranked) > 1 else float("inf")
    closest = ranked[0]["candidate"]

    if best_distance > threshold:
        return None, closest

    if len(ranked) > 1 and (second_distance - best_distance) < MIN_MARGIN:
        return None, closest

    return closest, closest


def save_face_encodings(user_id: int, poses: list[dict]) -> None:
    """
    Reemplaza los encodings faciales de un usuario en una transacción.

    poses: lista de {"tipoParte": str, "embedding": np.ndarray, "modelo": str}
    """
    with cursor() as cur:
        cur.execute("DELETE FROM encoding WHERE idUsuario=%s", (user_id,))
        for pose in poses:
            vec = pose["embedding"].astype(np.float32, copy=False)
            vec_bytes = vec.tobytes()
            vec_hash = hashlib.sha256(
                vec_bytes + f"{user_id}_{pose['tipoParte']}".encode()
            ).hexdigest()
            cur.execute(
                """
                INSERT INTO encoding
                    (idUsuario, estado, vector, dimension, hashVector,
                     tipoParte, vectorDtype, modelo, modeloVersion)
                VALUES (%s, 'activo', %s, %s, %s, %s, 'float32', %s, '1.0')
                """,
                (
                    user_id, vec_bytes, int(len(vec)),
                    vec_hash, pose["tipoParte"], pose["modelo"],
                ),
            )
    logger.info("Encodings guardados para usuario id=%s (%d poses)", user_id, len(poses))
