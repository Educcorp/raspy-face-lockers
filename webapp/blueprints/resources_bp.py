"""Recursos compartidos (solo front por ahora).

Muestra los recursos de uso compartido (de ejemplo: Recurso 1 y Recurso 2) con su
estado activo/inactivo.

Permisos: al panel web solo entran Admin y Superadmin, y ellos siempre tienen
permiso de activación "ambos" (ver users_bp._validate_and_save), así que
cualquier usuario con sesión puede activar los recursos.

Pendiente para cuando exista el backend:
  * Tabla de recursos en la BD (hoy la lista está fija en SHARED_RESOURCES).
  * Guardar el estado y activar el hardware; hoy el estado vive solo en el
    navegador (ver templates/resources/list.html).
"""

from flask import Blueprint, render_template

from webapp.auth import login_required

bp = Blueprint("resources", __name__, url_prefix="/recursos")

# Recursos de ejemplo mientras no exista la tabla en la BD. El nombre se arma
# con la clave "res.name" de webapp/i18n.py ("Recurso {n}" / "Resource {n}").
SHARED_RESOURCES = [
    {"id": "recurso1", "numero": 1},
    {"id": "recurso2", "numero": 2},
]


@bp.route("/")
@login_required
def list_resources():
    return render_template("resources/list.html", resources=SHARED_RESOURCES)
