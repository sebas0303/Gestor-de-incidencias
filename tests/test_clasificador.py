import json
from types import SimpleNamespace
import clasificador


def _crear_respuesta_mock(contenido: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=contenido))]
    )


class ClienteSimulado:
    """Modelo simulado compatible con la interfaz client.chat.completions.create de OpenAI."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.llamadas.append(kwargs)
        siguiente = self.respuestas.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return _crear_respuesta_mock(siguiente)


def test_clasificar_portatil_no_arranca_como_hardware(monkeypatch):
    """Criterio 2 y 5: 'No arranca el portátil, no enciende ni el led' se clasifica como hardware con modelo simulado."""
    respuesta_json = json.dumps(
        {
            "categoria": "hardware",
            "prioridad": "alta",
            "resumen": "El portátil no arranca ni enciende el indicador LED.",
        }
    )
    mock_cliente = ClienteSimulado([respuesta_json])
    monkeypatch.setattr(clasificador, "obtener_cliente", lambda: mock_cliente)

    resultado = clasificador.clasificar("No arranca el portátil, no enciende ni el led")

    assert resultado["categoria"] == "hardware"
    assert resultado["prioridad"] == "alta"
    assert len(resultado["resumen"].split()) <= 15
    assert len(mock_cliente.llamadas) == 1
    assert mock_cliente.llamadas[0]["temperature"] == 0
    assert mock_cliente.llamadas[0]["response_format"]["type"] == "json_schema"


def test_reintenta_una_vez_si_respuesta_invalida(monkeypatch):
    """Si la primera respuesta no es válida, reintenta una vez y devuelve la segunda si es válida."""
    respuesta_invalida = json.dumps(
        {
            "categoria": "desconocida",
            "prioridad": "media",
            "resumen": "Categoría fuera del esquema.",
        }
    )
    respuesta_valida = json.dumps(
        {
            "categoria": "red",
            "prioridad": "media",
            "resumen": "Sin conexión a la red WiFi de la oficina.",
        }
    )
    mock_cliente = ClienteSimulado([respuesta_invalida, respuesta_valida])
    monkeypatch.setattr(clasificador, "obtener_cliente", lambda: mock_cliente)

    resultado = clasificador.clasificar("No funciona el WiFi en la planta 2")

    assert len(mock_cliente.llamadas) == 2
    assert resultado["categoria"] == "red"
    assert resultado["prioridad"] == "media"


def test_doble_fallo_validacion_guarda_como_revisar(monkeypatch):
    """Si tras el reintento la respuesta sigue siendo inválida (ej. > 15 palabras), devuelve 'revisar'."""
    resumen_largo = " ".join(["palabra"] * 20)
    respuesta_invalida = json.dumps(
        {
            "categoria": "software",
            "prioridad": "baja",
            "resumen": resumen_largo,
        }
    )
    mock_cliente = ClienteSimulado(["no es json", respuesta_invalida])
    monkeypatch.setattr(clasificador, "obtener_cliente", lambda: mock_cliente)

    resultado = clasificador.clasificar("Error al abrir la hoja de cálculo")

    assert len(mock_cliente.llamadas) == 2
    assert resultado["categoria"] == "revisar"
    assert len(resultado["resumen"].split()) <= 15


def test_lmstudio_apagado_devuelve_revisar(monkeypatch):
    """Si LM Studio no responde (excepción de conexión), devuelve categoria 'revisar' sin lanzar error."""
    mock_cliente = ClienteSimulado([ConnectionError("LM Studio no disponible")])
    monkeypatch.setattr(clasificador, "obtener_cliente", lambda: mock_cliente)

    resultado = clasificador.clasificar("No puedo iniciar sesión en el correo")

    assert resultado["categoria"] == "revisar"
    assert resultado["prioridad"] == "media"
    assert len(resultado["resumen"].split()) <= 15


def test_variables_entorno_lmstudio(monkeypatch):
    """Verifica valores por defecto y lectura de LMSTUDIO_URL y LMSTUDIO_MODEL."""
    monkeypatch.delenv("LMSTUDIO_URL", raising=False)
    monkeypatch.delenv("LMSTUDIO_MODEL", raising=False)
    url, modelo = clasificador.obtener_configuracion()
    assert url == "http://localhost:1234/v1"
    assert modelo == "local-model"

    monkeypatch.setenv("LMSTUDIO_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LMSTUDIO_MODEL", "qwen2.5-7b-instruct")
    url2, modelo2 = clasificador.obtener_configuracion()
    assert url2 == "http://localhost:1234/v1"
    assert modelo2 == "qwen2.5-7b-instruct"
