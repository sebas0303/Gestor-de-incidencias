from datetime import datetime
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


def resumir_por_defecto(observacion: str) -> str:
    """Genera un resumen provisional de máximo 15 palabras a partir de la observación."""
    palabras = observacion.strip().split()
    return " ".join(palabras[:15]) if palabras else "Sin observación"


def crear_incidencia(
    usuario_id: int,
    observacion: str,
    categoria: str = "revisar",
    prioridad: str = "media",
    resumen: str | None = None,
    estado: str = "abierta",
) -> int:
    """Inserta una nueva incidencia en la base de datos y devuelve su ID."""
    db = obtener_db()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resumen_final = (resumen or "").strip() or resumir_por_defecto(observacion)
    cursor = db.execute(
        """
        INSERT INTO incidencias (fecha, usuario_id, observacion, categoria, prioridad, resumen, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (fecha, usuario_id, observacion.strip(), categoria, prioridad, resumen_final, estado),
    )
    db.commit()
    return cursor.lastrowid


def obtener_incidencias_usuario(usuario_id: int) -> list[sqlite3.Row]:
    """Devuelve únicamente las incidencias registradas por el usuario indicado."""
    db = obtener_db()
    return db.execute(
        """
        SELECT id, fecha, usuario_id, observacion, categoria, prioridad, resumen, estado
        FROM incidencias
        WHERE usuario_id = ?
        ORDER BY id DESC
        """,
        (usuario_id,),
    ).fetchall()


