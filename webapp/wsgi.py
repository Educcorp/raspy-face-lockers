"""Punto de entrada WSGI para servidores de producción (gunicorn, etc.).

Ejemplo:
    gunicorn -w 2 -b 0.0.0.0:8000 webapp.wsgi:app
"""

from webapp.app import create_app

app = create_app()
