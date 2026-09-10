from __future__ import annotations

import secrets

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from utils.validators import (
    MAX_APELLIDO, MAX_NOMBRE, validate_email, validate_matricula,
    validate_name, validate_tel,
)
from webapp.auth import (
    can_assign_privileged_user_types, can_edit_catalogs,
    filter_assignable_user_types, is_superadmin, login_required,
)
from webapp.services import catalog_service, user_service

bp = Blueprint("users", __name__, url_prefix="/usuarios")


@bp.route("/")
@login_required
def list_users():
    return render_template("users/list.html", users=user_service.get_all_users())


def _form_context(row: dict | None = None):
    tipos = filter_assignable_user_types(catalog_service.get_all_tipos_usuario())
    unidades = catalog_service.get_active_unidades()
    return {"row": row, "tipos": tipos, "unidades": unidades}


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def new_user():
    if not can_edit_catalogs():
        flash("No tienes permiso para crear usuarios.", "danger")
        return redirect(url_for("users.list_users"))

    if request.method == "POST":
        error = _validate_and_save(None)
        if error is None:
            flash("Usuario creado. Falta registrar su rostro en el dispositivo del locker.", "success")
            return redirect(url_for("users.list_users"))
        flash(error, "danger")

    return render_template("users/form.html", **_form_context())


@bp.route("/<int:user_id>/editar", methods=["GET", "POST"])
@login_required
def edit_user(user_id: int):
    row = user_service.get_user_by_id(user_id)
    if not row:
        flash("Usuario no encontrado.", "warning")
        return redirect(url_for("users.list_users"))

    if request.method == "POST":
        if not can_edit_catalogs():
            flash("No tienes permiso para editar usuarios.", "danger")
            return redirect(url_for("users.list_users"))
        error = _validate_and_save(user_id)
        if error is None:
            flash("Usuario actualizado.", "success")
            return redirect(url_for("users.list_users"))
        flash(error, "danger")
        row = user_service.get_user_by_id(user_id)

    pending = user_service.count_face_encodings(user_id) == 0
    return render_template("users/form.html", pending=pending, **_form_context(row))


def _validate_and_save(user_id: int | None) -> str | None:
    nombre = request.form.get("nombre", "").strip()
    ap_paterno = request.form.get("apPaterno", "").strip()
    ap_materno = request.form.get("apMaterno", "").strip() or None
    matricula = request.form.get("matricula", "").strip()
    email = request.form.get("emailInst", "").strip()
    tel = request.form.get("tel", "").strip() or None
    tipo_id = request.form.get("idTipoUsuario", type=int)
    unidad_id = request.form.get("idUnidadAcademica", type=int)
    estado = request.form.get("estado", "activo")

    for err in (
        validate_name(nombre, "Nombre", MAX_NOMBRE),
        validate_name(ap_paterno, "Apellido paterno", MAX_APELLIDO),
        validate_matricula(matricula),
        validate_email(email),
        validate_tel(tel or ""),
    ):
        if err:
            return err

    if not tipo_id or not unidad_id:
        return "Selecciona un tipo de usuario y una unidad académica."

    assignable_ids = {t["idtipousuario"] for t in filter_assignable_user_types(
        catalog_service.get_all_tipos_usuario()
    )}
    if user_id is None and tipo_id not in assignable_ids and not can_assign_privileged_user_types():
        return "No tienes permiso para asignar ese tipo de usuario."

    if user_service.email_exists(email, exclude_user_id=user_id):
        return f"Ya existe un usuario con el correo '{email}'."
    if user_service.matricula_exists(matricula, exclude_user_id=user_id):
        return f"Ya existe un usuario con la matrícula '{matricula}'."
    if user_service.nombre_completo_exists(nombre, ap_paterno, ap_materno, exclude_user_id=user_id):
        return "Ya existe un usuario con ese nombre completo."

    actor_id = g.user["idusuario"] if g.user.get("idusuario") else None

    if user_id is None:
        pin = request.form.get("pin", "").strip()
        if len(pin) < 4:
            return "El PIN inicial debe tener al menos 4 dígitos."
        import hashlib
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        user_service.create_user_pending_encoding({
            "nombre": nombre, "apPaterno": ap_paterno, "apMaterno": ap_materno,
            "idTipoUsuario": tipo_id, "idUnidadAcademica": unidad_id,
            "emailInst": email, "tel": tel, "matricula": int(matricula),
            "pin_hash": pin_hash, "creadoPor": actor_id or 1,
        })
    else:
        user_service.update_user(user_id, {
            "nombre": nombre, "apPaterno": ap_paterno, "apMaterno": ap_materno,
            "idTipoUsuario": tipo_id, "idUnidadAcademica": unidad_id,
            "emailInst": email, "tel": tel, "matricula": int(matricula),
            "estado": estado, "modificadoPor": actor_id or 1,
        })
    return None


@bp.route("/<int:user_id>/estado", methods=["POST"])
@login_required
def set_status(user_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("users.list_users"))
    estado = request.form.get("estado", "activo")
    actor_id = g.user["idusuario"] or 1
    user_service.set_user_status(user_id, estado, actor_id)
    flash("Estado actualizado.", "success")
    return redirect(url_for("users.list_users"))


@bp.route("/<int:user_id>/pin", methods=["POST"])
@login_required
def reset_pin(user_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("users.list_users"))
    new_pin = secrets.choice(range(1000, 9999))
    actor_id = g.user["idusuario"] or 1
    user_service.update_pin(user_id, str(new_pin), actor_id)
    flash(f"Nuevo PIN generado: {new_pin} (comunícalo al usuario de forma segura).", "success")
    return redirect(url_for("users.edit_user", user_id=user_id))


@bp.route("/<int:user_id>/eliminar", methods=["POST"])
@login_required
def delete_user(user_id: int):
    if not is_superadmin():
        flash("Solo un superadministrador puede eliminar usuarios permanentemente.", "danger")
        return redirect(url_for("users.list_users"))
    user_service.delete_user_permanent(user_id)
    flash("Usuario eliminado permanentemente.", "success")
    return redirect(url_for("users.list_users"))
