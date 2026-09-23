from __future__ import annotations

import hashlib
from zoneinfo import ZoneInfo

from urllib.parse import urlparse

import click
from flask import Flask, g, redirect, request, url_for

from webapp import config, db, i18n
from webapp.auth import load_logged_in_user

LOCAL_TZ = ZoneInfo("America/Mexico_City")


def format_local_dt(value, fmt: str = "%d/%m/%Y %H:%M") -> str:
    """Convierte un datetime con timezone (guardado en UTC en la BD) a la
    hora local antes de mostrarlo — sin esto, todas las fechas se ven
    corridas varias horas hacia adelante."""
    if not value:
        return "—"
    if value.tzinfo is not None:
        value = value.astimezone(LOCAL_TZ)
    return value.strftime(fmt)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    if test_config:
        app.config.update(test_config)

    app.jinja_env.filters["local_dt"] = format_local_dt
    i18n.init_app(app)

    db.init_app(app)

    @app.before_request
    def _load_user():
        load_logged_in_user()

    from webapp.blueprints.auth_bp import bp as auth_bp
    from webapp.blueprints.dashboard_bp import bp as dashboard_bp
    from webapp.blueprints.users_bp import bp as users_bp
    from webapp.blueprints.catalogs_bp import bp as catalogs_bp
    from webapp.blueprints.lockers_bp import bp as lockers_bp
    from webapp.blueprints.history_bp import bp as history_bp
    from webapp.blueprints.face_bp import bp as face_bp
    from webapp.blueprints.resources_bp import bp as resources_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(catalogs_bp)
    app.register_blueprint(lockers_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(face_bp)
    app.register_blueprint(resources_bp)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))

    @app.route("/lang/<code>")
    def set_lang(code: str):
        """Botón de idioma del nav: guarda la cookie y regresa a la misma
        página. Solo se regresa a URLs del mismo host (evita open redirect)."""
        target = url_for("index")
        ref = request.referrer
        if ref:
            parsed = urlparse(ref)
            if parsed.netloc == request.host:
                target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        resp = redirect(target)
        if code in i18n.LANGS:
            resp.set_cookie(
                i18n.COOKIE_NAME, code,
                max_age=60 * 60 * 24 * 365, samesite="Lax",
            )
        return resp

    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)

    return app


@click.command("init-db")
def init_db_command():
    """Crea el esquema en la base de datos remota (webapp/schema.sql)."""
    from pathlib import Path

    app = create_app()
    schema_path = Path(__file__).parent / "schema.sql"
    with app.app_context():
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    click.echo("Esquema aplicado correctamente.")


@click.command("create-admin")
@click.option("--nombre", prompt=True)
@click.option("--apellido", prompt="Apellido paterno")
@click.option("--matricula", prompt=True)
@click.option("--email", prompt="Correo institucional")
@click.option("--pin", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--rol", type=click.Choice(["Superadmin", "Admin"]), default="Superadmin")
def create_admin_command(nombre, apellido, matricula, email, pin, rol):
    """Crea el primer usuario administrador del panel web."""
    app = create_app()
    with app.app_context():
        tipo = db.fetch_one(
            "SELECT idTipoUsuario FROM tipo_usuarios WHERE nombreTipoUsuario=%s", (rol,)
        )
        if not tipo:
            click.echo(f"No existe el tipo de usuario '{rol}'. Corre 'flask init-db' primero.")
            return
        pin_hash = hashlib.sha256(pin.strip().encode()).hexdigest()
        row = db.execute_returning(
            """
            INSERT INTO usuarios
                (nombre, apPaterno, idTipoUsuario, idUnidadAcademica, emailInst, matricula, pin, creadoPor)
            VALUES (%s, %s, %s, 1, %s, %s, %s, 1)
            RETURNING idUsuario
            """,
            (nombre, apellido, tipo["idtipousuario"], email, int(matricula), pin_hash),
        )
        click.echo(f"Usuario administrador creado con idUsuario={row['idusuario']}.")
