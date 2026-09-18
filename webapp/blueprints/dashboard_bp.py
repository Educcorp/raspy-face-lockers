from flask import Blueprint, render_template

from webapp.auth import login_required
from webapp.db import fetch_all, fetch_one

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    physical_lockers = fetch_all(
        """
        SELECT l.idLocker, l.estado AS locker_estado,
               al.fechaHoraReg AS asignacion_fecha,
               u.nombre, u.apPaterno, u.apMaterno
        FROM lockers l
        LEFT JOIN asignacion_locker al
          ON al.idLocker = l.idLocker AND al.estado = 'activo'
        LEFT JOIN usuarios u ON u.idUsuario = al.idUsuario
        ORDER BY l.idLocker
        LIMIT 4
        """
    )
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
        "lockers_fisicos": physical_lockers,
    }
    return render_template("dashboard.html", stats=stats)
