"""
Recursos compartidos: catálogo + usuarios autorizados a activarlos.

Dos páginas separadas a propósito, para que no choquen en la misma interfaz:
  - /recursos/catalogo        → alta/edición/baja del recurso en sí (Superadmin,
                                 igual que Áreas/Unidades/Tipos en catalogs_bp.py).
  - /recursos/autorizaciones  → relación recurso↔usuario (Admin y Superadmin,
                                 igual que la asignación de lockers).

A diferencia de los lockers (una asignación 1-a-1 por locker), un recurso puede
tener varios usuarios autorizados y un usuario puede estar autorizado en varios
recursos — ver webapp/services/resource_service.py y
webapp/migrations/add_recursos.sql.

Solo se puede autorizar a usuarios cuyo permisoActivacion sea 'recurso_compartido'
o 'ambos' (ver webapp/blueprints/users_bp.py): ese campo ya decide quién está
inscrito para usar recursos compartidos, así que el selector de autorización
filtra por él en vez de ofrecer a cualquier usuario activo.

El switch "Activar/Desactivar" sigue siendo una demo de solo-frontend (el estado
vive en localStorage del navegador, ver templates/resources/authorizations.html):
activar el hardware real queda pendiente para cuando exista esa integración.
"""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from utils.validators import validate_recurso_descripcion, validate_recurso_nombre
from webapp.auth import can_edit_catalogs, login_required, superadmin_required
from webapp.services import resource_service

bp = Blueprint("resources", __name__, url_prefix="/recursos")


def _actor_id() -> int:
    return (g.user or {}).get("idusuario") or 1


@bp.route("/")
@login_required
def index():
    return redirect(url_for("resources.authorizations"))


# ── Catálogo de recursos (solo Superadmin, igual que Áreas/Unidades/Tipos) ────

@bp.route("/catalogo")
@superadmin_required
def catalog():
    return render_template("resources/catalog.html", recursos=resource_service.get_all_recursos())


@bp.route("/nuevo", methods=["POST"])
@superadmin_required
def new_recurso():
    nombre = request.form.get("nombre", "").strip()
    descripcion = request.form.get("descripcion", "").strip() or None

    err = validate_recurso_nombre(nombre) or validate_recurso_descripcion(descripcion or "")
    if err:
        flash(err, "danger")
    elif resource_service.recurso_nombre_exists(nombre):
        flash(f"Ya existe un recurso llamado '{nombre}'.", "danger")
    else:
        resource_service.create_recurso(nombre, descripcion, _actor_id())
        flash("Recurso creado.", "success")
    return redirect(url_for("resources.catalog"))


@bp.route("/<int:recurso_id>/editar", methods=["POST"])
@superadmin_required
def edit_recurso(recurso_id: int):
    nombre = request.form.get("nombre", "").strip()
    descripcion = request.form.get("descripcion", "").strip() or None

    err = validate_recurso_nombre(nombre) or validate_recurso_descripcion(descripcion or "")
    if err:
        flash(err, "danger")
    elif resource_service.recurso_nombre_exists(nombre, exclude_id=recurso_id):
        flash(f"Ya existe un recurso llamado '{nombre}'.", "danger")
    else:
        resource_service.update_recurso(recurso_id, nombre, descripcion, _actor_id())
        flash("Recurso actualizado.", "success")
    return redirect(url_for("resources.catalog"))


@bp.route("/<int:recurso_id>/estado", methods=["POST"])
@superadmin_required
def set_recurso_estado(recurso_id: int):
    estado = request.form.get("estado", "activo")
    resource_service.set_recurso_estado(recurso_id, estado, _actor_id())
    flash("Estado del recurso actualizado.", "success")
    return redirect(url_for("resources.catalog"))


@bp.route("/<int:recurso_id>/eliminar", methods=["POST"])
@superadmin_required
def delete_recurso(recurso_id: int):
    resource_service.delete_recurso(recurso_id)
    flash("Recurso eliminado junto con sus autorizaciones.", "success")
    return redirect(url_for("resources.catalog"))


# ── Autorizaciones (Admin y Superadmin, igual que la asignación de lockers) ───

@bp.route("/autorizaciones")
@login_required
def authorizations():
    recursos = resource_service.get_active_recursos()

    selected_id = request.args.get("recurso", type=int)
    selected = None
    if selected_id is not None:
        selected = next((r for r in recursos if r["idrecurso"] == selected_id), None)
    if selected is None and recursos:
        selected = recursos[0]

    authorized_users = resource_service.get_authorized_users(selected["idrecurso"]) if selected else []
    authorizable_users = resource_service.get_authorizable_users(selected["idrecurso"]) if selected else []

    return render_template(
        "resources/authorizations.html",
        recursos=recursos,
        selected=selected,
        authorized_users=authorized_users,
        authorizable_users=authorizable_users,
    )


@bp.route("/<int:recurso_id>/autorizar", methods=["POST"])
@login_required
def authorize_user(recurso_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("resources.authorizations", recurso=recurso_id))

    user_id = request.form.get("idUsuario", type=int)
    if not user_id:
        flash("Selecciona un usuario para autorizar.", "danger")
    else:
        resource_service.authorize_user(recurso_id, user_id, _actor_id())
        flash("Usuario autorizado.", "success")
    return redirect(url_for("resources.authorizations", recurso=recurso_id))


@bp.route("/<int:recurso_id>/autorizados/<int:auth_id>/quitar", methods=["POST"])
@login_required
def revoke_authorization(recurso_id: int, auth_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("resources.authorizations", recurso=recurso_id))

    resource_service.revoke_authorization(auth_id, _actor_id())
    flash("Autorización retirada.", "success")
    return redirect(url_for("resources.authorizations", recurso=recurso_id))
