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

CATEGORIAS_INCIDENCIA = ("hardware", "software", "red", "cuenta", "revisar")
PRIORIDADES_INCIDENCIA = ("baja", "media", "alta")
ESTADOS_INCIDENCIA = ("abierta", "en curso", "resuelta")


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


def obtener_todas_incidencias(
    categoria: str | None = None,
    prioridad: str | None = None,
    estado: str | None = None,
) -> list[sqlite3.Row]:
    """Devuelve todas las incidencias para el panel del técnico, con filtros opcionales."""
    db = obtener_db()
    consulta = """
        SELECT i.id, i.fecha, i.usuario_id, u.username AS usuario,
               i.observacion, i.categoria, i.prioridad, i.resumen, i.estado
        FROM incidencias i
        JOIN usuarios u ON i.usuario_id = u.id
        WHERE 1=1
    """
    parametros: list[str] = []

    if categoria and categoria in CATEGORIAS_INCIDENCIA:
        consulta += " AND i.categoria = ?"
        parametros.append(categoria)
    if prioridad and prioridad in PRIORIDADES_INCIDENCIA:
        consulta += " AND i.prioridad = ?"
        parametros.append(prioridad)
    if estado and estado in ESTADOS_INCIDENCIA:
        consulta += " AND i.estado = ?"
        parametros.append(estado)

    consulta += " ORDER BY i.id DESC"
    return db.execute(consulta, parametros).fetchall()


def actualizar_incidencia(
    incidencia_id: int, categoria: str, prioridad: str, estado: str
) -> bool:
    """Actualiza la categoría, prioridad y estado de una incidencia."""
    if (
        categoria not in CATEGORIAS_INCIDENCIA
        or prioridad not in PRIORIDADES_INCIDENCIA
        or estado not in ESTADOS_INCIDENCIA
    ):
        return False

    db = obtener_db()
    cursor = db.execute(
        """
        UPDATE incidencias
        SET categoria = ?, prioridad = ?, estado = ?
        WHERE id = ?
        """,
        (categoria, prioridad, estado, incidencia_id),
    )
    db.commit()
    return cursor.rowcount > 0



