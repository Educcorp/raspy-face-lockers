"""Paginación compartida de los listados del panel (Usuarios, Lockers,
Recursos, Historial): todos muestran PER_PAGE registros por página."""

from __future__ import annotations

PER_PAGE = 10


def page_info(page: int, total: int, per_page: int = PER_PAGE) -> dict:
    """Normaliza la página pedida (1..total_paginas) y calcula el rango mostrado."""
    total_paginas = max(1, (total + per_page - 1) // per_page)
    page = min(max(page, 1), total_paginas)
    return {
        "pagina": page,
        "per_page": per_page,
        "total": total,
        "total_paginas": total_paginas,
        "inicio": (page - 1) * per_page + 1 if total > 0 else 0,
        "fin": min(page * per_page, total),
    }


def paginate_list(items: list, page: int, per_page: int = PER_PAGE) -> tuple[list, dict]:
    """Pagina en memoria una lista ya cargada (catálogos chicos: lockers, recursos)."""
    info = page_info(page, len(items), per_page)
    start = info["inicio"] - 1 if info["total"] else 0
    return items[start:start + per_page], info
