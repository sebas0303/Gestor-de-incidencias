import json
import os
from openai import OpenAI

DEFAULT_LMSTUDIO_URL = "http://localhost:1234/v1"
DEFAULT_LMSTUDIO_MODEL = "local-model"

CATEGORIAS_VALIDAS = {"hardware", "software", "red", "cuenta"}
PRIORIDADES_VALIDAS = {"baja", "media", "alta"}

ESQUEMA_CLASIFICACION = {
    "type": "json_schema",
    "json_schema": {
        "name": "clasificacion_incidencia",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "enum": ["hardware", "software", "red", "cuenta"],
                },
                "prioridad": {
                    "type": "string",
                    "enum": ["baja", "media", "alta"],
                },
                "resumen": {
                    "type": "string",
                    "description": "Resumen conciso de la incidencia en máximo 15 palabras.",
                },
            },
            "required": ["categoria", "prioridad", "resumen"],
            "additionalProperties": False,
        },
    },
}

PROMPT_SISTEMA = (
    "Eres un asistente técnico que clasifica incidencias informáticas. "
    "Devuelve únicamente un objeto JSON válido según el esquema indicado con:\n"
    "- categoria: 'hardware' (fallos físicos, encendido, pantalla, periféricos), "
    "'software' (aplicaciones, sistema operativo, errores de programas), "
    "'red' (conectividad, wifi, VPN, carpetas en red, internet) o "
    "'cuenta' (contraseñas, accesos, permisos, correo).\n"
    "- prioridad: 'baja', 'media' o 'alta'.\n"
    "- resumen: resumen claro de la incidencia con un máximo de 15 palabras."
)


def obtener_configuracion() -> tuple[str, str]:
    """Lee la URL y el modelo de LM Studio desde variables de entorno con valores por defecto."""
    url = os.environ.get("LMSTUDIO_URL", DEFAULT_LMSTUDIO_URL)
    modelo = os.environ.get("LMSTUDIO_MODEL", DEFAULT_LMSTUDIO_MODEL)
    return url, modelo


def obtener_cliente() -> OpenAI:
    """Crea el cliente OpenAI apuntando siempre al servidor local de LM Studio."""
    url, _ = obtener_configuracion()
    return OpenAI(base_url=url, api_key="lm-studio")


def _resumen_fallback(observacion: str) -> str:
    palabras = observacion.strip().split()
    return " ".join(palabras[:15]) if palabras else "Incidencia pendiente de revisar"


def _resultado_fallback(observacion: str) -> dict[str, str]:
    return {
        "categoria": "revisar",
        "prioridad": "media",
        "resumen": _resumen_fallback(observacion),
    }


def _validar_respuesta(contenido: str | None) -> dict[str, str] | None:
    """Valida que la respuesta sea JSON válido y cumpla categoría, prioridad y máximo 15 palabras."""
    if not contenido:
        return None
    try:
        datos = json.loads(contenido)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(datos, dict):
        return None

    categoria = datos.get("categoria")
    prioridad = datos.get("prioridad")
    resumen = datos.get("resumen")

    if categoria not in CATEGORIAS_VALIDAS:
        return None
    if prioridad not in PRIORIDADES_VALIDAS:
        return None
    if not isinstance(resumen, str):
        return None

    palabras = resumen.strip().split()
    if not (1 <= len(palabras) <= 15):
        return None

    return {
        "categoria": categoria,
        "prioridad": prioridad,
        "resumen": resumen.strip(),
    }


def clasificar(observacion: str, cliente: OpenAI | None = None) -> dict[str, str]:
    """
    Clasifica una observación utilizando el modelo local de LM Studio.
    Si la respuesta no es válida, reintenta una vez.
    Si vuelve a fallar o LM Studio no responde, devuelve categoria 'revisar'.
    """
    _, modelo = obtener_configuracion()
    try:
        cliente_ia = cliente if cliente is not None else obtener_cliente()
    except Exception:
        return _resultado_fallback(observacion)

    for _intento in range(2):
        try:
            respuesta = cliente_ia.chat.completions.create(
                model=modelo,
                temperature=0,
                response_format=ESQUEMA_CLASIFICACION,
                messages=[
                    {"role": "system", "content": PROMPT_SISTEMA},
                    {"role": "user", "content": observacion},
                ],
            )
            contenido = respuesta.choices[0].message.content
        except Exception:
            return _resultado_fallback(observacion)

        validado = _validar_respuesta(contenido)
        if validado is not None:
            return validado

    return _resultado_fallback(observacion)
