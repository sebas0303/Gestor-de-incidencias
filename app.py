from functools import wraps
from pathlib import Path
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from clasificador import clasificar
from db import (
    CATEGORIAS_INCIDENCIA,
    ESTADOS_INCIDENCIA,
    PRIORIDADES_INCIDENCIA,
    actualizar_incidencia,
    autenticar_usuario,
    cerrar_db,
    crear_incidencia,
    inicializar_db,
    obtener_incidencias_usuario,
    obtener_todas_incidencias,
)

RUTA_BASE = Path(__file__).resolve().parent


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="clave-desarrollo-gestor-incidencias",
        DATABASE=str(RUTA_BASE / "incidencias.db"),
    )

    if test_config is not None:
        app.config.update(test_config)

    app.teardown_appcontext(cerrar_db)
    inicializar_db(app.config["DATABASE"])

    def login_requerido(vista):
        @wraps(vista)
        def vista_envuelta(**kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("login"))
            return vista(**kwargs)

        return vista_envuelta

    def rol_requerido(rol_esperado: str):
        def decorador(vista):
            @wraps(vista)
            def vista_envuelta(**kwargs):
                if "usuario_id" not in session:
                    return redirect(url_for("login"))
                if session.get("rol") != rol_esperado:
                    abort(403)
                return vista(**kwargs)

            return vista_envuelta

        return decorador

    @app.route("/")
    def index():
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        if session.get("rol") == "tecnico":
            return redirect(url_for("panel_tecnico"))
        return redirect(url_for("mis_incidencias"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            usuario = autenticar_usuario(username, password)

            if usuario is None:
                flash("Usuario o contraseña incorrectos.", "error")
                return render_template("login.html"), 401

            session.clear()
            session["usuario_id"] = usuario["id"]
            session["username"] = usuario["username"]
            session["rol"] = usuario["rol"]

            if usuario["rol"] == "tecnico":
                return redirect(url_for("panel_tecnico"))
            return redirect(url_for("mis_incidencias"))

        return render_template("login.html")

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/incidencias", methods=["GET", "POST"])
    @login_requerido
    def mis_incidencias():
        if request.method == "POST":
            observacion = request.form.get("observacion", "").strip()
            if not observacion:
                flash("La observación no puede estar vacía.", "error")
            else:
                resultado = clasificar(observacion)
                crear_incidencia(
                    usuario_id=session["usuario_id"],
                    observacion=observacion,
                    categoria=resultado["categoria"],
                    prioridad=resultado["prioridad"],
                    resumen=resultado["resumen"],
                )
                flash("Incidencia registrada correctamente.", "exito")
                return redirect(url_for("mis_incidencias"))

        incidencias = obtener_incidencias_usuario(session["usuario_id"])
        return render_template("usuario.html", incidencias=incidencias)

    @app.route("/tecnico")
    @rol_requerido("tecnico")
    def panel_tecnico():
        filtro_categoria = request.args.get("categoria", "").strip()
        filtro_prioridad = request.args.get("prioridad", "").strip()
        filtro_estado = request.args.get("estado", "").strip()

        incidencias = obtener_todas_incidencias(
            categoria=filtro_categoria or None,
            prioridad=filtro_prioridad or None,
            estado=filtro_estado or None,
        )
        return render_template(
            "tecnico.html",
            incidencias=incidencias,
            categorias=CATEGORIAS_INCIDENCIA,
            prioridades=PRIORIDADES_INCIDENCIA,
            estados=ESTADOS_INCIDENCIA,
            filtro_categoria=filtro_categoria,
            filtro_prioridad=filtro_prioridad,
            filtro_estado=filtro_estado,
        )

    @app.route("/tecnico/incidencias/<int:incidencia_id>", methods=["POST"])
    @rol_requerido("tecnico")
    def editar_incidencia(incidencia_id: int):
        categoria = request.form.get("categoria", "").strip()
        prioridad = request.form.get("prioridad", "").strip()
        estado = request.form.get("estado", "").strip()

        if actualizar_incidencia(incidencia_id, categoria, prioridad, estado):
            flash(f"Incidencia #{incidencia_id} actualizada correctamente.", "exito")
        else:
            flash("Datos no válidos para actualizar la incidencia.", "error")

        return redirect(url_for("panel_tecnico"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

