"""
Captura de rostro desde la cámara del navegador (reemplaza la captura física
en el kiosco del Pi). La autenticación en el locker sigue usando la cámara
física del dispositivo — este flujo solo alimenta la base de datos remota
con los embeddings, que el Pi luego compara localmente.
"""

from __future__ import annotations

import base64
import logging

import numpy as np
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from webapp.auth import can_edit_catalogs, login_required
from webapp.face_processing import MODEL_NAME, decode_image, extract_embedding
from webapp.services import user_service

logger = logging.getLogger(__name__)

bp = Blueprint("face", __name__, url_prefix="/usuarios/<int:user_id>/rostro")

POSES = [
    {"tipoParte": "frontal", "label": "Mira directo a la cámara", "icon": "●"},
    {"tipoParte": "derecha", "label": "Gira tu cabeza hacia tu DERECHA", "icon": "→"},
    {"tipoParte": "izquierda", "label": "Gira tu cabeza hacia tu IZQUIERDA", "icon": "←"},
    {"tipoParte": "arriba", "label": "Levanta un poco la barbilla, mira hacia ARRIBA", "icon": "↑"},
]
POSE_ORDER = [p["tipoParte"] for p in POSES]

SESSION_KEY = "face_capture"


def _session_state(user_id: int) -> dict:
    state = session.get(SESSION_KEY)
    if not state or state.get("user_id") != user_id:
        state = {"user_id": user_id, "poses": {}}
        session[SESSION_KEY] = state
    return state


def _encode_vector(vec: np.ndarray) -> str:
    return base64.b64encode(vec.astype(np.float16).tobytes()).decode("ascii")


def _decode_vector(raw: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(raw), dtype=np.float16).astype(np.float32)


@bp.before_request
def _guard():
    if not can_edit_catalogs():
        flash("No tienes permiso para registrar rostros.", "danger")
        return redirect(url_for("users.list_users"))


@bp.route("/", methods=["GET"])
@login_required
def capture_page(user_id: int):
    row = user_service.get_user_by_id(user_id)
    if not row:
        flash("Usuario no encontrado.", "warning")
        return redirect(url_for("users.list_users"))

    state = _session_state(user_id)
    done = list(state["poses"].keys())
    next_pose = next((p for p in POSES if p["tipoParte"] not in done), None)

    return render_template(
        "users/face_capture.html",
        row=row,
        poses=POSES,
        done_count=len(done),
        total=len(POSES),
        next_pose=next_pose,
        all_done=next_pose is None,
    )


@bp.route("/captura", methods=["POST"])
@login_required
def capture_pose(user_id: int):
    tipo_parte = request.form.get("tipoParte", "")
    if tipo_parte not in POSE_ORDER:
        return jsonify(ok=False, reason="pose_invalida"), 400

    foto = request.files.get("foto")
    if not foto:
        return jsonify(ok=False, reason="sin_foto"), 400

    frame = decode_image(foto.read())
    if frame is None:
        return jsonify(ok=False, reason="imagen_invalida"), 400

    embedding, status = extract_embedding(frame)
    if status != "ok":
        return jsonify(ok=False, reason=status)

    candidates = user_service.get_active_face_encodings(exclude_user_id=user_id)
    if candidates:
        matched, _ = user_service.find_best_face_match(embedding, MODEL_NAME, candidates)
        if matched:
            nombre = f"{matched.get('nombre', '')} {matched.get('appaterno', '')}".strip()
            logger.warning("Rostro duplicado al registrar usuario=%s (coincide con %s)", user_id, nombre)
            return jsonify(ok=False, reason="rostro_duplicado", nombre=nombre), 409

    state = _session_state(user_id)
    state["poses"][tipo_parte] = _encode_vector(embedding)
    session[SESSION_KEY] = state
    session.modified = True

    done = list(state["poses"].keys())
    next_pose = next((p for p in POSES if p["tipoParte"] not in done), None)
    return jsonify(
        ok=True,
        done_count=len(done),
        total=len(POSES),
        next_pose=next_pose["tipoParte"] if next_pose else None,
        all_done=next_pose is None,
    )


@bp.route("/guardar", methods=["POST"])
@login_required
def save(user_id: int):
    state = _session_state(user_id)
    if len(state["poses"]) < len(POSES):
        flash("Faltan poses por capturar.", "danger")
        return redirect(url_for("face.capture_page", user_id=user_id))

    poses = [
        {"tipoParte": tp, "embedding": _decode_vector(raw), "modelo": MODEL_NAME}
        for tp, raw in state["poses"].items()
    ]
    user_service.save_face_encodings(user_id, poses)
    session.pop(SESSION_KEY, None)
    flash("Rostro registrado correctamente.", "success")
    return redirect(url_for("users.list_users"))


@bp.route("/cancelar", methods=["POST"])
@login_required
def cancel(user_id: int):
    session.pop(SESSION_KEY, None)
    return redirect(url_for("users.edit_user", user_id=user_id))
