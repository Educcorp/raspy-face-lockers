from __future__ import annotations

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from webapp.auth import can_edit_catalogs, is_superadmin, login_required
from webapp.services import catalog_service, locker_service

bp = Blueprint("lockers", __name__, url_prefix="/lockers")


def _actor_id() -> int:
    return (g.user or {}).get("idusuario") or 1


@bp.route("/", methods=["GET", "POST"])
@login_required
def list_lockers():
    if request.method == "POST":
        if not can_edit_catalogs():
            flash("No tienes permiso para esta acción.", "danger")
            return redirect(url_for("lockers.list_lockers"))
        unidad_id = request.form.get("idUnidadAcademica", type=int)
        area_id = request.form.get("idArea", type=int)
        if not unidad_id or not area_id:
            flash("Selecciona unidad académica y área.", "danger")
        else:
            locker_service.create_locker(unidad_id, area_id, _actor_id())
            flash("Locker creado.", "success")
        return redirect(url_for("lockers.list_lockers"))

    return render_template(
        "lockers/list.html",
        lockers=locker_service.get_all_lockers(),
        unidades=catalog_service.get_active_unidades(),
        areas=catalog_service.get_active_areas(),
    )


@bp.route("/<int:locker_id>/estado", methods=["POST"])
@login_required
def set_status(locker_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("lockers.list_lockers"))
    estado = request.form.get("estado", "activo")
    locker_service.set_locker_status(locker_id, estado, _actor_id())
    flash("Estado del locker actualizado.", "success")
    return redirect(url_for("lockers.list_lockers"))


@bp.route("/<int:locker_id>/ubicacion", methods=["POST"])
@login_required
def set_location(locker_id: int):
    if not can_edit_catalogs():
        flash("No tienes permiso para esta acción.", "danger")
        return redirect(url_for("lockers.list_lockers"))
    unidad_id = request.form.get("idUnidadAcademica", type=int)
    area_id = request.form.get("idArea", type=int)
    if not unidad_id or not area_id:
        flash("Selecciona unidad académica y área.", "danger")
    else:
        locker_service.update_locker_location(locker_id, unidad_id, area_id, _actor_id())
        flash("Locker actualizado.", "success")
    return redirect(url_for("lockers.list_lockers"))


@bp.route("/<int:locker_id>/eliminar", methods=["POST"])
@login_required
def delete_locker(locker_id: int):
    if not is_superadmin():
        flash("Solo un superadministrador puede eliminar lockers.", "danger")
        return redirect(url_for("lockers.list_lockers"))
    if locker_id in locker_service.get_protected_locker_ids():
        flash("Este locker es uno de los 4 originales y no se puede eliminar.", "warning")
        return redirect(url_for("lockers.list_lockers"))
    if locker_service.has_active_assignment(locker_id):
        flash("Este locker tiene una asignación activa. Libéralo primero en Asignaciones.", "warning")
        return redirect(url_for("lockers.list_lockers"))
    try:
        locker_service.delete_locker(locker_id)
        flash("Locker eliminado junto con su historial.", "success")
    except Exception:
        flash("No se pudo eliminar el locker.", "danger")
    return redirect(url_for("lockers.list_lockers"))


@bp.route("/<int:locker_id>/abrir", methods=["POST"])
@login_required
def open_locker(locker_id: int):
    """Pide a la Raspberry que abra un locker (la web solo encola el comando)."""
    if not can_edit_catalogs():
        return jsonify(ok=False, error="No tienes permiso para esta acción."), 403
    ok, message = locker_service.request_open_locker(locker_id, _actor_id())
    return jsonify(ok=ok, message=message, error=None if ok else message), (200 if ok else 409)


@bp.route("/estado")
@login_required
def remote_status():
    """Estado en vivo (puertas + último comando) que consulta la página de asignaciones."""
    if not can_edit_catalogs():
        return jsonify(ok=False, error="No tienes permiso para esta acción."), 403
    return jsonify(ok=True, **locker_service.get_remote_status())


@bp.route("/asignaciones", methods=["GET", "POST"])
@login_required
def assignments():
    if request.method == "POST":
        if not can_edit_catalogs():
            flash("No tienes permiso para esta acción.", "danger")
            return redirect(url_for("lockers.assignments"))

        action = request.form.get("action")
        if action == "assign":
            user_id = request.form.get("idUsuario", type=int)
            locker_id = request.form.get("idLocker", type=int)
            try:
                locker_service.assign_locker(user_id, locker_id, _actor_id())
                flash(f"Locker {locker_id} asignado.", "success")
            except ValueError as exc:
                flash(str(exc), "danger")
        elif action == "release":
            assignment_id = request.form.get("idLockerAsignado", type=int)
            if locker_service.release_assignment(assignment_id):
                flash("Asignación liberada.", "success")
            else:
                flash("No se encontró la asignación.", "warning")
        return redirect(url_for("lockers.assignments"))

    return render_template(
        "lockers/assignments.html",
        assignments=locker_service.get_active_assignments(),
        available_lockers=locker_service.get_available_lockers(),
        users=locker_service.get_users_without_locker(),
        can_open=can_edit_catalogs(),
        open_lockers=[l for l in locker_service.get_all_lockers() if l["estado"] == "activo"]
        if can_edit_catalogs() else [],
    )
