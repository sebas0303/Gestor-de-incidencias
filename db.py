import sqlite3
from pathlib import Path
from flask import current_app, g
from werkzeug.security import generate_password_hash, check_password_hash

ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK(rol IN ('usuario', 'tecnico'))
);

CREATE TABLE IF NOT EXISTS incidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    usuario_id INTEGER NOT NULL,
    observacion TEXT NOT NULL,
    categoria TEXT NOT NULL CHECK(categoria IN ('hardware', 'software', 'red', 'cuenta', 'revisar')),
    prioridad TEXT NOT NULL CHECK(prioridad IN ('baja', 'media', 'alta')),
    resumen TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierta' CHECK(estado IN ('abierta', 'en curso', 'resuelta')),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
"""

USUARIOS_PRUEBA = [
    ("usuario", "usuario123", "usuario"),
    ("maria", "maria123", "usuario"),
    ("tecnico", "tecnico123", "tecnico"),
]


def obtener_db() -> sqlite3.Connection:
    """Devuelve la conexión SQLite asociada a la petición actual."""
    if "db" not in g:
        ruta_db = current_app.config["DATABASE"]
        conn = sqlite3.connect(ruta_db)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def cerrar_db(e=None) -> None:
    """Cierra la conexión SQLite al finalizar la petición."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def inicializar_db(ruta_db: str | Path) -> None:
    """Crea las tablas si no existen e inserta los usuarios de prueba con contraseña con hash."""
    conn = sqlite3.connect(ruta_db)
    try:
        conn.executescript(ESQUEMA_SQL)
        for username, password, rol in USUARIOS_PRUEBA:
            cursor = conn.execute(
                "SELECT id FROM usuarios WHERE username = ?", (username,)
            )
            if cursor.fetchone() is None:
                conn.execute(
                    "INSERT INTO usuarios (username, password_hash, rol) VALUES (?, ?, ?)",
                    (username, generate_password_hash(password), rol),
                )
        conn.commit()
    finally:
        conn.close()


def autenticar_usuario(username: str, password: str) -> sqlite3.Row | None:
    """Verifica las credenciales del usuario y devuelve su fila si son válidas."""
    db = obtener_db()
    usuario = db.execute(
        "SELECT id, username, password_hash, rol FROM usuarios WHERE username = ?",
        (username,),
    ).fetchone()
    if usuario is not None and check_password_hash(usuario["password_hash"], password):
        return usuario
    return None

