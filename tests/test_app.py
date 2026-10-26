import sqlite3


def test_usuarios_iniciales_y_hash(app):
    """Verifica que los usuarios de prueba se crean al arrancar y sus contraseñas no están en claro."""
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    usuarios = conn.execute("SELECT username, password_hash, rol FROM usuarios").fetchall()
    conn.close()

    por_nombre = {u["username"]: u for u in usuarios}
    assert "usuario" in por_nombre
    assert "tecnico" in por_nombre
    assert por_nombre["usuario"]["rol"] == "usuario"
    assert por_nombre["tecnico"]["rol"] == "tecnico"
    assert por_nombre["usuario"]["password_hash"] != "usuario123"
    assert por_nombre["tecnico"]["password_hash"] != "tecnico123"


def test_redireccion_sin_login(client):
    """Sin iniciar sesión, la raíz y las rutas protegidas redirigen a /login."""
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]

    resp_inc = client.get("/incidencias")
    assert resp_inc.status_code == 302
    assert "/login" in resp_inc.headers["Location"]


def test_login_usuario_y_acceso_restringido_a_tecnico(client):
    """Un usuario normal puede iniciar sesión pero no puede entrar al panel del técnico."""
    resp = client.post(
        "/login",
        data={"username": "usuario", "password": "usuario123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "usuario".encode("utf-8") in resp.data

    # Criterio de aceptación 4: Un usuario sin rol técnico no puede entrar en el panel del técnico
    resp_tecnico = client.get("/tecnico")
    assert resp_tecnico.status_code == 403


def test_login_tecnico(client):
    """Un usuario con rol técnico es redirigido al panel del técnico y puede acceder."""
    resp = client.post(
        "/login",
        data={"username": "tecnico", "password": "tecnico123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Panel del técnico".encode("utf-8") in resp.data


def test_login_credenciales_invalidas(client):
    """Un login con contraseña incorrecta devuelve 401."""
    resp = client.post(
        "/login",
        data={"username": "usuario", "password": "malpassword"},
    )
    assert resp.status_code == 401

