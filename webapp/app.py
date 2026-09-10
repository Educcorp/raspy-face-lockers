from __future__ import annotations

import hashlib

import click
from flask import Flask, g, redirect, url_for

from webapp import config, db
from webapp.auth import load_logged_in_user


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    if test_config:
        app.config.update(test_config)

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(catalogs_bp)
    app.register_blueprint(lockers_bp)
    app.register_blueprint(history_bp)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))

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
