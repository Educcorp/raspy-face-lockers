"""
Recursos compartidos: catálogo + usuarios autorizados a activarlos.

Dos páginas separadas a propósito, para que no choquen en la misma interfaz:
  - /recursos/catalogo        → alta/edición/activar-desactivar del recurso en sí
                                 (Admin y Superadmin; eliminar sigue siendo solo
                                 Superadmin) — mismo reparto que lockers_bp.py.
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
from webapp.auth import can_edit_catalogs, is_superadmin, login_required
from webapp.pagination import paginate_list
from webapp.services import catalog_service, resource_service

bp = Blueprint("resources", __name__, url_prefix="/recursos")


def _actor_id() -> int:
    return (g.user or {}).get("idusuario") or 1


@bp.route("/")
@login_required
def index():
    return redirect(url_for("resources.authorizations"))


# ── Catálogo de recursos (Admin y Superadmin; eliminar solo Superadmin) ───────
# Mismo reparto que lockers_bp.py: crear/editar/estado los puede hacer cualquier
# admin logueado en el panel (can_edit_catalogs ya es siempre True para una
# sesión web, porque solo Admin/Superadmin pueden iniciar sesión aquí); eliminar
# queda reservado a Superadmin.

@bp.route("/catalogo")
@login_required
def catalog():
    recursos, page = paginate_list(
        resource_service.get_all_recursos(),
        request.args.get("pagina", default=1, type=int),
    )
    return render_template(
        "resources/catalog.html",
        recursos=recursos,
        unidades=catalog_service.get_active_unidades(),
        areas=catalog_service.get_active_areas(),
        **page,
    )


def _validate_unidad_area(unidad_id: int | None, area_id: int | None) -> str | None:
    """Misma validación que lockers_bp.py: el área elegida debe pertenecer de
    verdad a la unidad académica elegida (catalog_service.area_belongs_to_unidad)."""
    if not unidad_id or not area_id:
        return "Selecciona unidad académica y área."
    if not catalog_service.area_belongs_to_unidad(area_id, unidad_id):
        return "Esa área no pertenece a la unidad académica seleccionada."
    return None


@bp.route("/nuevo", methods=["POST"])
@login_required
def new_recurso():
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("resources.catalog"))

    nombre = request.form.get("nombre", "").strip()
    descripcion = request.form.get("descripcion", "").strip() or None
    unidad_id = request.form.get("idUnidadAcademica", type=int)
    area_id = request.form.get("idArea", type=int)

    err = (
        validate_recurso_nombre(nombre)
        or validate_recurso_descripcion(descripcion or "")
        or _validate_unidad_area(unidad_id, area_id)
    )
    if err:
        flash(err, "danger")
    elif resource_service.recurso_nombre_exists(nombre):
        flash(f"Ya existe un recurso llamado '{nombre}'.", "danger")
    else:
        resource_service.create_recurso(nombre, descripcion, unidad_id, area_id, _actor_id())
        flash("Recurso creado.", "success")
    return redirect(url_for("resources.catalog"))


@bp.route("/<int:recurso_id>/editar", methods=["POST"])
@login_required
def edit_recurso(recurso_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("resources.catalog"))

    nombre = request.form.get("nombre", "").strip()
    descripcion = request.form.get("descripcion", "").strip() or None
    unidad_id = request.form.get("idUnidadAcademica", type=int)
    area_id = request.form.get("idArea", type=int)

    err = (
        validate_recurso_nombre(nombre)
        or validate_recurso_descripcion(descripcion or "")
        or _validate_unidad_area(unidad_id, area_id)
    )
    if err:
        flash(err, "danger")
    elif resource_service.recurso_nombre_exists(nombre, exclude_id=recurso_id):
        flash(f"Ya existe un recurso llamado '{nombre}'.", "danger")
    else:
        resource_service.update_recurso(recurso_id, nombre, descripcion, unidad_id, area_id, _actor_id())
        flash("Recurso actualizado.", "success")
    return redirect(url_for("resources.catalog"))


@bp.route("/<int:recurso_id>/estado", methods=["POST"])
@login_required
def set_recurso_estado(recurso_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("resources.catalog"))

    estado = request.form.get("estado", "activo")
    resource_service.set_recurso_estado(recurso_id, estado, _actor_id())
    flash("Estado del recurso actualizado.", "success")
    return redirect(url_for("resources.catalog"))


@bp.route("/<int:recurso_id>/eliminar", methods=["POST"])
@login_required
def delete_recurso(recurso_id: int):
    if not is_superadmin():
        flash("Solo un superadministrador puede eliminar recursos.", "danger")
        return redirect(url_for("resources.catalog"))

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
