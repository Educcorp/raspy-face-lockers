from flask import Blueprint, render_template, request

from webapp.auth import login_required
from webapp.services import access_log_service

bp = Blueprint("history", __name__, url_prefix="/historial")


@bp.route("/")
@login_required
def list_history():
    limit = request.args.get("limit", default=200, type=int)
    rows = access_log_service.get_access_history(limit=limit)
    return render_template(
        "history/list.html", rows=rows, labels=access_log_service.MOTIVO_LABELS, limit=limit
    )
