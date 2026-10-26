import json
import sqlite3
from types import SimpleNamespace
import clasificador


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


def test_registrar_incidencia_con_lmstudio_parado_no_da_500(client, monkeypatch):
    """Criterio 1: Con LM Studio parado, registrar una incidencia no da error 500 y se guarda con categoria 'revisar'."""
    def _cliente_caido():
        raise ConnectionError("LM Studio parado")

    monkeypatch.setattr(clasificador, "obtener_cliente", _cliente_caido)
    client.post("/login", data={"username": "usuario", "password": "usuario123"})

    observacion = "No puedo acceder a la carpeta compartida del departamento"
    resp = client.post(
        "/incidencias",
        data={"observacion": observacion},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    texto = resp.data.decode("utf-8")
    assert observacion in texto
    assert "revisar" in texto
    assert "abierta" in texto


def test_registrar_incidencia_clasifica_automaticamente(client, monkeypatch):
    """Al registrar una incidencia con LM Studio activo (simulado), se guarda su categoría, prioridad y resumen."""
    respuesta_ia = json.dumps(
        {
            "categoria": "hardware",
            "prioridad": "alta",
            "resumen": "El portátil no arranca ni enciende el LED.",
        }
    )
    mock_cliente = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=respuesta_ia))]
                )
            )
        )
    )
    monkeypatch.setattr(clasificador, "obtener_cliente", lambda: mock_cliente)

    client.post("/login", data={"username": "usuario", "password": "usuario123"})
    observacion = "No arranca el portátil, no enciende ni el led"
    resp = client.post(
        "/incidencias",
        data={"observacion": observacion},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    texto = resp.data.decode("utf-8")
    assert observacion in texto
    assert "hardware" in texto
    assert "alta" in texto
    assert "El portátil no arranca ni enciende el LED." in texto


def test_aislamiento_incidencias_entre_usuarios(client, monkeypatch):
    """Criterio 3: Un usuario no puede ver las incidencias de otro usuario."""
    monkeypatch.setattr(
        clasificador,
        "obtener_cliente",
        lambda: (_ for _ in ()).throw(ConnectionError("Sin IA en test de aislamiento")),
    )
    # 'usuario' registra una incidencia privada
    client.post("/login", data={"username": "usuario", "password": "usuario123"})
    secreto = "Incidencia exclusiva del primer usuario"
    client.post("/incidencias", data={"observacion": secreto}, follow_redirects=True)
    client.get("/logout")

    # 'maria' inicia sesión y consulta su listado de incidencias
    client.post("/login", data={"username": "maria", "password": "maria123"})
    resp = client.get("/incidencias")
    assert resp.status_code == 200
    texto_maria = resp.data.decode("utf-8")
    assert secreto not in texto_maria


def test_panel_tecnico_filtros_y_actualizacion(client, monkeypatch):
    """El técnico puede filtrar todas las incidencias y corregir categoría, prioridad y estado."""
    monkeypatch.setattr(
        clasificador,
        "obtener_cliente",
        lambda: (_ for _ in ()).throw(ConnectionError("Sin IA")),
    )

    # Dos usuarios registran incidencias
    client.post("/login", data={"username": "usuario", "password": "usuario123"})
    client.post("/incidencias", data={"observacion": "Fallo en monitor externo"})
    client.get("/logout")

    client.post("/login", data={"username": "maria", "password": "maria123"})
    client.post("/incidencias", data={"observacion": "Cuenta de correo bloqueada"})

    # Un usuario sin rol técnico tampoco puede modificar incidencias por POST
    resp_prohibido = client.post(
        "/tecnico/incidencias/1",
        data={"categoria": "hardware", "prioridad": "alta", "estado": "en curso"},
    )
    assert resp_prohibido.status_code == 403
    client.get("/logout")

    # Inicia sesión el técnico y ve ambas incidencias
    client.post("/login", data={"username": "tecnico", "password": "tecnico123"})
    resp_todas = client.get("/tecnico")
    texto_todas = resp_todas.data.decode("utf-8")
    assert "Fallo en monitor externo" in texto_todas
    assert "Cuenta de correo bloqueada" in texto_todas

    # El técnico corrige la incidencia #1: categoria=hardware, prioridad=alta, estado='en curso'
    resp_edit = client.post(
        "/tecnico/incidencias/1",
        data={"categoria": "hardware", "prioridad": "alta", "estado": "en curso"},
        follow_redirects=True,
    )
    assert resp_edit.status_code == 200
    assert "Incidencia #1 actualizada" in resp_edit.data.decode("utf-8")

    # Filtrar por categoria=hardware y estado='en curso' muestra solo la incidencia #1
    resp_filtro = client.get(
        "/tecnico?categoria=hardware&prioridad=alta&estado=en+curso"
    )
    texto_filtro = resp_filtro.data.decode("utf-8")
    assert "Fallo en monitor externo" in texto_filtro
    assert "Cuenta de correo bloqueada" not in texto_filtro

    # Cambiar a 'resuelta' y comprobar que el usuario ve el nuevo estado
    client.post(
        "/tecnico/incidencias/1",
        data={"categoria": "hardware", "prioridad": "alta", "estado": "resuelta"},
        follow_redirects=True,
    )
    client.get("/logout")

    client.post("/login", data={"username": "usuario", "password": "usuario123"})
    resp_usuario = client.get("/incidencias")
    texto_usuario = resp_usuario.data.decode("utf-8")
    assert "resuelta" in texto_usuario
    assert "hardware" in texto_usuario



