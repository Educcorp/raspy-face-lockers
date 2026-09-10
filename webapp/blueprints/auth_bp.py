from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from webapp.auth import ERROR_MESSAGES, authenticate_admin_user, login_user, logout_user

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        matricula = request.form.get("matricula", "")
        pin = request.form.get("pin", "")
        error, user = authenticate_admin_user(matricula, pin)
        if error:
            flash(ERROR_MESSAGES.get(error, "No se pudo iniciar sesión."), "danger")
        else:
            login_user(user)
            return redirect(url_for("dashboard.index"))

    return render_template("login.html")


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
