from __future__ import annotations

import secrets

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from utils.validators import (
    MAX_APELLIDO, MAX_NOMBRE, validate_email, validate_matricula,
    validate_name, validate_tel,
)
from webapp.auth import (
    ROLE_SUPERADMIN, ROLE_USER, can_assign_privileged_user_types, can_edit_catalogs,
    filter_assignable_user_types, is_superadmin, login_required, normalize_role,
)
from webapp.services import catalog_service, user_service

bp = Blueprint("users", __name__, url_prefix="/usuarios")


def _is_privileged(row: dict) -> bool:
    """True si el usuario es Admin o Superadmin (no un usuario 'universal')."""
    return normalize_role(row.get("tipo")) != ROLE_USER


def _can_manage(row: dict) -> bool:
    """Puede ver/editar `row` si es superadmin, si es su propio perfil
    (botón "Mi perfil" — cualquier admin puede editarse a sí mismo, cambiar
    su PIN o su rostro), o si el objetivo no es un usuario privilegiado."""
    if is_superadmin():
        return True
    own_id = (g.user or {}).get("idusuario")
    if own_id is not None and row.get("idusuario") == own_id:
        return True
    return not _is_privileged(row)


@bp.route("/")
@login_required
def list_users():
    page = request.args.get("pagina", default=1, type=int)
    search = request.args.get("buscar", default="", type=str).strip()
    search_field = request.args.get(
        "campo",
        default="todos",
        type=str,
    ).strip().lower()

    per_page = 15

    if page < 1:
        page = 1

    allowed_fields = {"todos", "nombre", "matricula", "unidad"}

    if search_field not in allowed_fields:
        search_field = "todos"

    users, total = user_service.get_users_paginated(
        page=page,
        per_page=per_page,
        search=search,
        search_field=search_field,
    )

    # Un admin solo puede ver usuarios normales.
    if not is_superadmin():
        users = [u for u in users if not _is_privileged(u)]

    total_paginas = max(1, (total + per_page - 1) // per_page)

    if page > total_paginas:
        page = total_paginas

        users, total = user_service.get_users_paginated(
            page=page,
            per_page=per_page,
            search=search,
            search_field=search_field,
        )

        if not is_superadmin():
            users = [u for u in users if not _is_privileged(u)]

    inicio = ((page - 1) * per_page) + 1 if total > 0 else 0
    fin = min(page * per_page, total)

    return render_template(
        "users/list.html",
        users=users,
        pagina=page,
        per_page=per_page,
        total=total,
        total_paginas=total_paginas,
        inicio=inicio,
        fin=fin,
        buscar=search,
        campo=search_field,
    )


def _form_context(row: dict | None = None):
    tipos = filter_assignable_user_types(catalog_service.get_all_tipos_usuario())
    unidades = catalog_service.get_active_unidades()
    own_id = (g.user or {}).get("idusuario")
    return {
        "row": row, "tipos": tipos, "unidades": unidades,
        # "Mi perfil": el usuario en sesión se edita a sí mismo
        "is_own": bool(row and own_id is not None and row.get("idusuario") == own_id),
        # El rol de un superadmin no se cambia desde este formulario (ver _validate_and_save)
        "target_is_superadmin": bool(row and normalize_role(row.get("tipo")) == ROLE_SUPERADMIN),
    }


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

    if not _can_manage(row):
        flash("No tienes permiso para ver ni editar este usuario.", "danger")
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
    permiso_activacion = request.form.get("permisoactivacion", "").strip()

    for err in (
        validate_name(nombre, "Nombre", MAX_NOMBRE),
        validate_name(ap_paterno, "Apellido paterno", MAX_APELLIDO),
        validate_matricula(matricula),
        validate_email(email),
        validate_tel(tel or ""),
    ):
        if err:
            return err

    if user_id is not None:
        current = user_service.get_user_by_id(user_id)
        if current and normalize_role(current.get("tipo")) == ROLE_SUPERADMIN:
            # "Superadmin" no está entre los tipos asignables, así que el <select> no lo
            # ofrece y el navegador enviaba el primero (Admin): guardar tu propio perfil
            # te degradaba. El rol de un superadmin no se toca desde este formulario.
            tipo_id = current["idtipousuario"]

    assignable = filter_assignable_user_types(catalog_service.get_all_tipos_usuario())
    assignable_ids = {t["idtipousuario"] for t in assignable}

    if not tipo_id and not is_superadmin():
        # El campo "Tipo de usuario" está oculto para admin (solo tiene sentido para superadmin).
        if user_id is not None:
            # Editando: se conserva el tipo actual del usuario, un admin no puede cambiarlo.
            current = user_service.get_user_by_id(user_id)
            tipo_id = current["idtipousuario"] if current else None
        elif len(assignable) == 1:
            # Alta nueva: único tipo permitido para admin, se asigna automático.
            tipo_id = assignable[0]["idtipousuario"]

    if not tipo_id or not unidad_id:
        return "Selecciona un tipo de usuario y una unidad académica."
    
    if permiso_activacion not in ("recurso_compartido", "locker", "ambos"):
        return "Selecciona permisos de activación válidos."

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
        if len(set(pin)) == 1:
            return "El PIN no puede tener todos los dígitos iguales (ej: 1111, 2222)."
        import hashlib
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        user_service.create_user_pending_encoding({
            "nombre": nombre, "apPaterno": ap_paterno, "apMaterno": ap_materno,
            "idTipoUsuario": tipo_id, "idUnidadAcademica": unidad_id,
            "emailInst": email, "tel": tel, "matricula": int(matricula),
            "pin_hash": pin_hash, "creadoPor": actor_id or 1,
            "permisoActivacion": permiso_activacion,
        })
    else:
        user_service.update_user(user_id, {
            "nombre": nombre, "apPaterno": ap_paterno, "apMaterno": ap_materno,
            "idTipoUsuario": tipo_id, "idUnidadAcademica": unidad_id,
            "emailInst": email, "tel": tel, "matricula": int(matricula),
            "estado": estado, "permisoActivacion": permiso_activacion,
            "modificadoPor": actor_id or 1,
        })
    return None


@bp.route("/<int:user_id>/estado", methods=["POST"])
@login_required
def set_status(user_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("users.list_users"))
    target = user_service.get_user_by_id(user_id)
    if target and not _can_manage(target):
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
    target = user_service.get_user_by_id(user_id)
    if target and not _can_manage(target):
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("users.list_users"))
    
    # Generar un PIN válido (sin todos los dígitos iguales)
    while True:
        new_pin = secrets.choice(range(1000, 9999))
        if len(set(str(new_pin))) > 1:  # Si no todos los dígitos son iguales
            break
    
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
