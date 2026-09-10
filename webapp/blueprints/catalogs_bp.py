from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from utils.validators import validate_area_nombre, validate_tipo_nombre, validate_unidad_nombre
from webapp.auth import is_superadmin, superadmin_required
from webapp.services import catalog_service

bp = Blueprint("catalogs", __name__, url_prefix="/catalogos")


def _actor_id() -> int:
    return (g.user or {}).get("idusuario") or 1


# ── Tipos de usuario ─────────────────────────────────────────────────────────

@bp.route("/tipos-usuario", methods=["GET", "POST"])
@superadmin_required
def tipos_usuario():
    if request.method == "POST":
        nombre = request.form.get("nombreTipoUsuario", "").strip()
        edit_id = request.form.get("idTipoUsuario", type=int)
        estado = request.form.get("estado", "activo")

        err = validate_tipo_nombre(nombre)
        if err:
            flash(err, "danger")
        elif catalog_service.tipo_usuario_nombre_exists(nombre, exclude_id=edit_id):
            flash(f"Ya existe un tipo de usuario llamado '{nombre}'.", "danger")
        elif edit_id:
            catalog_service.update_tipo_usuario(edit_id, nombre, estado, _actor_id())
            flash("Tipo de usuario actualizado.", "success")
        else:
            catalog_service.create_tipo_usuario(nombre, _actor_id())
            flash("Tipo de usuario creado.", "success")
        return redirect(url_for("catalogs.tipos_usuario"))

    return render_template("catalogs/tipos.html", tipos=catalog_service.get_all_tipos_usuario())


# ── Unidades académicas ──────────────────────────────────────────────────────

@bp.route("/unidades", methods=["GET", "POST"])
@superadmin_required
def unidades():
    if request.method == "POST":
        nombre = request.form.get("nombreUnidadAcademica", "").strip()
        zona = request.form.get("zona", "").strip() or None
        edit_id = request.form.get("idUnidadAcademica", type=int)
        estado = request.form.get("estado", "activo")

        err = validate_unidad_nombre(nombre)
        if err:
            flash(err, "danger")
        elif catalog_service.unidad_nombre_exists(nombre, exclude_id=edit_id):
            flash(f"Ya existe una unidad llamada '{nombre}'.", "danger")
        elif edit_id:
            catalog_service.update_unidad(edit_id, nombre, zona, estado, _actor_id())
            flash("Unidad académica actualizada.", "success")
        else:
            catalog_service.create_unidad(nombre, zona, _actor_id())
            flash("Unidad académica creada.", "success")
        return redirect(url_for("catalogs.unidades"))

    return render_template("catalogs/unidades.html", unidades=catalog_service.get_all_unidades())


@bp.route("/unidades/<int:unidad_id>/eliminar", methods=["POST"])
@superadmin_required
def delete_unidad(unidad_id: int):
    n = catalog_service.count_usuarios_by_unidad(unidad_id)
    if n > 0:
        flash(f"Esta unidad tiene {n} usuario(s) activos. Reasígnalos antes de eliminar.", "danger")
    else:
        try:
            catalog_service.delete_unidad(unidad_id)
            flash("Unidad eliminada.", "success")
        except Exception:
            flash("No se pudo eliminar la unidad. Puede tener dependencias (lockers).", "danger")
    return redirect(url_for("catalogs.unidades"))


# ── Áreas de lockers ──────────────────────────────────────────────────────────

@bp.route("/areas", methods=["GET", "POST"])
@superadmin_required
def areas():
    if request.method == "POST":
        nombre = request.form.get("nombreArea", "").strip()
        unidad_id = request.form.get("idUnidadAcademica", type=int) or None
        edit_id = request.form.get("idArea", type=int)
        estado = request.form.get("estado", "activo")

        err = validate_area_nombre(nombre)
        if err:
            flash(err, "danger")
        elif catalog_service.area_nombre_exists(nombre, exclude_id=edit_id):
            flash(f"Ya existe un área llamada '{nombre}'.", "danger")
        elif edit_id:
            catalog_service.update_area(edit_id, nombre, unidad_id, estado, _actor_id())
            flash("Área actualizada.", "success")
        else:
            catalog_service.create_area(nombre, unidad_id, _actor_id())
            flash("Área creada.", "success")
        return redirect(url_for("catalogs.areas"))

    return render_template(
        "catalogs/areas.html",
        areas=catalog_service.get_all_areas(),
        unidades=catalog_service.get_active_unidades(),
    )


@bp.route("/areas/<int:area_id>/eliminar", methods=["POST"])
@superadmin_required
def delete_area(area_id: int):
    n = catalog_service.count_lockers_by_area(area_id)
    if n > 0:
        flash(f"Esta área tiene {n} locker(s) asignado(s). Reasígnalos antes de eliminar.", "danger")
    else:
        try:
            catalog_service.delete_area(area_id)
            flash("Área eliminada.", "success")
        except Exception:
            flash("No se pudo eliminar el área. Puede tener dependencias.", "danger")
    return redirect(url_for("catalogs.areas"))
