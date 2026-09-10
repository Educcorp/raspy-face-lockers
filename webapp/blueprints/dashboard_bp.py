from flask import Blueprint, render_template

from webapp.auth import login_required
from webapp.db import fetch_one

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    stats = {
        "usuarios": fetch_one("SELECT COUNT(*) AS n FROM usuarios WHERE estado='activo'")["n"],
        "pendientes": fetch_one(
            """
            SELECT COUNT(*) AS n FROM usuarios u
            WHERE u.estado='activo' AND NOT EXISTS (
                SELECT 1 FROM encoding e WHERE e.idUsuario=u.idUsuario AND e.estado='activo'
            )
            """
        )["n"],
        "lockers": fetch_one("SELECT COUNT(*) AS n FROM lockers WHERE estado='activo'")["n"],
        "asignaciones": fetch_one(
            "SELECT COUNT(*) AS n FROM asignacion_locker WHERE estado='activo'"
        )["n"],
        "accesos_hoy": fetch_one(
            "SELECT COUNT(*) AS n FROM historial_accesos WHERE fechaHoraAcceso::date = now()::date"
        )["n"],
    }
    return render_template("dashboard.html", stats=stats)
