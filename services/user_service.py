"""
Operaciones de negocio sobre usuarios y autenticación facial.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

import numpy as np

from database.connection import db_session, execute, fetch_all, fetch_one

logger = logging.getLogger(__name__)


# ── Consultas de usuarios ──────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    """Lista todos los usuarios con tipo y unidad académica."""
    return fetch_all("""
        SELECT u.idUsuario, u.nombre, u.apPaterno, u.apMaterno,
               u.matricula, u.emailInst, u.tel, u.estado,
               t.nombreTipoUsuario AS tipo,
               ua.nombreUnidadAcademica AS unidad
        FROM usuarios u
        LEFT JOIN tipo_usuarios t  ON t.idTipoUsuario = u.idTipoUsuario
        LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = u.idUnidadAcademica
        ORDER BY u.nombre, u.apPaterno
    """)


def get_user_by_id(user_id: int) -> dict | None:
    """Devuelve un usuario con tipo y unidad por su ID."""
    return fetch_one("""
        SELECT u.*, t.nombreTipoUsuario AS tipo,
               ua.nombreUnidadAcademica AS unidad
        FROM usuarios u
        LEFT JOIN tipo_usuarios t  ON t.idTipoUsuario = u.idTipoUsuario
        LEFT JOIN unidad_academica ua ON ua.idUnidadAcademica = u.idUnidadAcademica
        WHERE u.idUsuario = ?
    """, (user_id,))


def count_face_encodings(user_id: int) -> int:
    """Número de encodings faciales activos de un usuario."""
    row = fetch_one(
        "SELECT COUNT(*) AS n FROM encoding WHERE idUsuario=? AND estado='activo'",
        (user_id,),
    )
    return row["n"] if row else 0


def update_user(user_id: int, data: dict) -> None:
    """
    Actualiza los datos de un usuario existente.

    data debe contener: nombre, apPaterno, apMaterno, matricula,
    emailInst, tel, idTipoUsuario, idUnidadAcademica, estado.
    """
    execute("""
        UPDATE usuarios SET
            nombre=?, apPaterno=?, apMaterno=?,
            matricula=?, emailInst=?, tel=?,
            idTipoUsuario=?, idUnidadAcademica=?,
            estado=?,
            fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'),
            modificadoPor=1
        WHERE idUsuario=?
    """, (
        data["nombre"], data["apPaterno"], data.get("apMaterno"),
        data["matricula"], data["emailInst"], data.get("tel"),
        data["idTipoUsuario"], data["idUnidadAcademica"],
        data.get("estado", "activo"),
        user_id,
    ))


def set_user_status(user_id: int, estado: str) -> None:
    """Cambia el estado de un usuario: 'activo', 'inactivo' o 'suspendido'."""
    execute(
        "UPDATE usuarios SET estado=?, "
        "fechaHoraAct=strftime('%Y-%m-%dT%H:%M:%S','now','localtime'), "
        "modificadoPor=1 WHERE idUsuario=?",
        (estado, user_id),
    )


def create_user_with_encodings(data: dict, poses: list[dict]) -> int:
    """
    Inserta un nuevo usuario junto con sus encodings faciales multi-pose.

    data: nombre, apPaterno, apMaterno, idTipoUsuario, idUnidadAcademica,
          emailInst, tel, matricula, pin_hash
    poses: lista de {"tipoParte": str, "embedding": np.ndarray, "modelo": str}

    Retorna el idUsuario del nuevo registro.
    """
    with db_session() as conn:
        cur = conn.execute("""
            INSERT INTO usuarios
                (nombre, apPaterno, apMaterno, idTipoUsuario, idUnidadAcademica,
                 emailInst, tel, matricula, pin, creadoPor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            data["nombre"], data["apPaterno"], data.get("apMaterno"),
            data["idTipoUsuario"], data["idUnidadAcademica"],
            data["emailInst"], data.get("tel"),
            data["matricula"], data["pin_hash"],
        ))
        user_id = cur.lastrowid

        for pose in poses:
            vec = pose["embedding"].astype(np.float32, copy=False)
            vec_bytes = vec.tobytes()
            vec_hash = hashlib.sha256(
                vec_bytes + f"{user_id}_{pose['tipoParte']}".encode()
            ).hexdigest()
            conn.execute("""
                INSERT INTO encoding
                    (idUsuario, estado, vector, dimension, hashVector,
                     tipoParte, vectorDtype, modelo, modeloVersion)
                VALUES (?, 'activo', ?, ?, ?, ?, 'float32', ?, '1.0')
            """, (
                user_id, vec_bytes, int(len(vec)),
                vec_hash, pose["tipoParte"], pose["modelo"],
            ))

    logger.info("✓ Usuario id=%s + %d encodings guardados", user_id, len(poses))
    return user_id


# ── Autenticación facial ───────────────────────────────────────────────────────

def get_active_face_encodings() -> list[dict]:
    """
    Carga todos los encodings activos de usuarios activos.
    Deserializa los vectores numpy desde BLOB y los adjunta como 'vector_np'.
    """
    rows = fetch_all("""
        SELECT
            e.idUsuario,
            e.vector,
            e.dimension,
            e.vectorDtype,
            e.modelo,
            u.nombre,
            u.apPaterno,
            u.apMaterno,
            u.matricula,
            a.idLockerAsignado,
            l.idLocker
        FROM encoding e
        JOIN usuarios u
            ON u.idUsuario = e.idUsuario
        LEFT JOIN asignacion_locker a
            ON a.idUsuario = u.idUsuario AND a.estado = 'activo'
        LEFT JOIN lockers l
            ON l.idLocker = a.idLocker
        WHERE e.estado = 'activo'
          AND u.estado = 'activo'
    """)

    parsed: list[dict] = []
    for row in rows:
        raw = row.get("vector")
        dim = int(row.get("dimension") or 128)
        dtype_name = (row.get("vectorDtype") or "float32").strip().lower()
        dtype = np.float64 if dtype_name == "float64" else np.float32

        if raw is None:
            continue

        vector_np = np.frombuffer(raw, dtype=dtype)
        if vector_np.size != dim:
            logger.warning(
                "Encoding inválido usuario=%s esperado=%s real=%s",
                row.get("idUsuario"), dim, vector_np.size,
            )
            continue

        if dtype != np.float32:
            vector_np = vector_np.astype(np.float32)

        row["vector_np"] = vector_np
        parsed.append(row)

    return parsed


def authenticate_user_by_pin(matricula: str, pin: str) -> dict | None:
    """
    Autentica cualquier usuario activo por matrícula + PIN.
    Retorna dict con datos + locker asignado, o None si las credenciales no son válidas.
    """
    row = fetch_one("""
        SELECT u.idUsuario, u.nombre, u.apPaterno, u.apMaterno,
               u.matricula, u.estado, u.pin,
               a.idLockerAsignado,
               l.idLocker
        FROM usuarios u
        LEFT JOIN asignacion_locker a
            ON a.idUsuario = u.idUsuario AND a.estado = 'activo'
        LEFT JOIN lockers l
            ON l.idLocker = a.idLocker
        WHERE CAST(u.matricula AS TEXT) = ?
        LIMIT 1
    """, (str(matricula).strip(),))

    if not row:
        return None
    if (row.get("estado") or "").strip().lower() != "activo":
        return None

    pin_stored = row.get("pin") or ""
    pin_hashed = hashlib.sha256(pin.strip().encode()).hexdigest()
    if not (hmac.compare_digest(pin_stored, pin_hashed)
            or hmac.compare_digest(pin_stored, pin.strip())):
        return None

    return row


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
    Busca el mejor candidato facial aplicando umbral y filtro de margen.

    Agrupa por usuario (mejor pose entre frontal/derecha/izquierda), luego:
      1. Rechaza si distancia > umbral absoluto.
      2. Rechaza si el margen entre 1er y 2do candidato < 0.10 (ambigüedad).

    Returns:
        (matched, closest)
        - matched  : candidato que pasó todos los filtros, o None si fue rechazado.
        - closest  : candidato más cercano en cualquier caso (útil para loguear rechazos).
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
        uid = int(candidate["idUsuario"])
        if uid not in user_best or dist < user_best[uid]["distance"]:
            user_best[uid] = {"candidate": candidate, "distance": dist}

    if not user_best:
        logger.warning("Sin candidatos compatibles con modelo '%s'", model_prefix)
        return None, None

    ranked = sorted(user_best.values(), key=lambda x: x["distance"])
    best_distance = ranked[0]["distance"]
    second_distance = ranked[1]["distance"] if len(ranked) > 1 else float("inf")
    closest = ranked[0]["candidate"]

    logger.info(
        "Auth facial: usuario=%s dist=%.4f umbral=%.4f 2do=%.4f modelo=%s",
        closest.get("idUsuario"), best_distance, threshold,
        second_distance, closest.get("modelo"),
    )

    if best_distance > threshold:
        logger.info("Rechazado — dist %.4f > umbral %.4f", best_distance, threshold)
        return None, closest

    if len(ranked) > 1 and (second_distance - best_distance) < MIN_MARGIN:
        logger.info(
            "Rechazado — margen %.4f < %.4f (ambigüedad entre usuarios)",
            second_distance - best_distance, MIN_MARGIN,
        )
        return None, closest

    return closest, closest
