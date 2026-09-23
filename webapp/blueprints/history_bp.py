from flask import Blueprint, render_template, request

from webapp.auth import login_required
from webapp.services import access_log_service


bp = Blueprint("history", __name__, url_prefix="/historial")


@bp.route("/")
@login_required
def list_history():

    # -----------------------------
    # Parámetros de búsqueda
    # -----------------------------
    page = request.args.get("pagina", default=1, type=int)

    search = request.args.get(
        "buscar",
        default="",
        type=str
    ).strip()

    resultado = request.args.get(
        "resultado",
        default="",
        type=str
    ).strip()

    # Siempre 15 registros por página
    per_page = 15

    if page < 1:
        page = 1

    # -----------------------------
    # Obtener registros
    # -----------------------------
    rows, total = access_log_service.get_access_history(
        page=page,
        per_page=per_page,
        search=search,
        resultado=resultado,
    )

    # -----------------------------
    # Calcular paginación
    # -----------------------------
    total_paginas = max(
        1,
        (total + per_page - 1) // per_page
    )

    # Si alguien pone una página mayor
    # a la existente, volver a la última.
    if page > total_paginas:
        page = total_paginas

        rows, total = access_log_service.get_access_history(
            page=page,
            per_page=per_page,
            search=search,
            resultado=resultado,
        )

    inicio = ((page - 1) * per_page) + 1 if total > 0 else 0
    fin = min(page * per_page, total)

    return render_template(
        "history/list.html",
        rows=rows,
        labels=access_log_service.MOTIVO_LABELS,

        # Paginación
        pagina=page,
        per_page=per_page,
        total=total,
        total_paginas=total_paginas,
        inicio=inicio,
        fin=fin,

        # Filtros
        buscar=search,
        resultado=resultado,
    )