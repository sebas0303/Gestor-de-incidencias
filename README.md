# Gestor de Incidencias con Clasificación IA (LM Studio)

Aplicación web en Python (Flask + SQLite) para registrar y gestionar incidencias informáticas. El usuario solo escribe la observación del problema y la aplicación la clasifica automáticamente (categoría, prioridad y resumen) mediante un modelo local ejecutado en **LM Studio**.

---

## Características principales

- **Autenticación y roles**:
  - Dos roles diferenciados: `usuario` y `tecnico`.
  - Contraseñas almacenadas de forma segura mediante hash (`werkzeug.security`).
  - Usuarios de prueba creados automáticamente al iniciar la aplicación.
- **Registro y consulta de incidencias (rol `usuario`)**:
  - Formulario sencillo con un único campo: **Observación**.
  - Clasificación automática con IA al registrar la incidencia.
  - Cada usuario visualiza únicamente sus propias incidencias y su estado actual.
- **Clasificación inteligente y tolerante a fallos (`clasificador.py`)**:
  - Conexión al servidor local de LM Studio (`http://localhost:1234/v1`) usando el cliente oficial `openai`.
  - Salida estructurada mediante `response_format` (`json_schema`) y `temperature=0`.
  - Categorías: `hardware` | `software` | `red` | `cuenta`.
  - Prioridades: `baja` | `media` | `alta`.
  - Resumen automático de máximo 15 palabras.
  - Reintento único si la respuesta del modelo no es válida; si vuelve a fallar o LM Studio está apagado, la incidencia nunca se pierde y se guarda con categoría `revisar`.
- **Panel de gestión (rol `tecnico`)**:
  - Vista global de todas las incidencias registradas.
  - Filtros combinables por **categoría**, **prioridad** y **estado**.
  - Edición directa para corregir categoría o prioridad y cambiar el estado (`abierta`, `en curso`, `resuelta`).

---

## Estructura del proyecto

```text
Agente/
├── .vscode/
│   ├── launch.json             # Configuración para ejecutar y depurar con F5 en VS Code
│   └── settings.json           # Configuración de pytest en el panel Testing
├── static/
│   └── estilos.css             # Hoja de estilos de la interfaz
├── templates/
│   ├── base.html               # Plantilla base y barra de navegación
│   ├── login.html              # Inicio de sesión
│   ├── usuario.html            # Formulario y listado de incidencias del usuario
│   └── tecnico.html            # Panel del técnico con filtros y edición
├── tests/
│   ├── conftest.py             # Fixtures de pruebas (base de datos temporal)
│   ├── test_app.py             # Tests de integración (login, roles, aislamiento, panel técnico)
│   └── test_clasificador.py    # Tests unitarios del clasificador con modelo simulado
├── app.py                      # Aplicación Flask y rutas
├── clasificador.py             # Único módulo de conexión al servidor local de LM Studio
├── db.py                       # Gestión de SQLite (incidencias.db) y semilla de usuarios
├── requirements.txt            # Dependencias del proyecto
├── AGENTS.md                   # Reglas y convenciones del proyecto
└── especificacion.md           # Especificación funcional y criterios de aceptación
```

---

## Requisitos e instalación

1. **Python 3.10 o superior**.
2. Crear y activar el entorno virtual `.venv` (si no existe) e instalar las dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Configuración de LM Studio

La aplicación lee la configuración del servidor local desde variables de entorno (con valores por defecto listos para usar):

| Variable | Valor por defecto | Descripción |
| :--- | :--- | :--- |
| `LMSTUDIO_URL` | `http://localhost:1234/v1` | URL del servidor local de LM Studio |
| `LMSTUDIO_MODEL` | `local-model` | Identificador del modelo cargado en LM Studio |

---

## Cómo ejecutar la aplicación

### Opción 1: Desde Visual Studio Code (F5)
1. Abre la carpeta del proyecto en **Visual Studio Code**.
2. Pulsa **F5** (usa la configuración `Python: Flask (Gestor de Incidencias)` definida en `.vscode/launch.json`).
3. Abre en el navegador: http://127.0.0.1:5000

### Opción 2: Desde la terminal
```powershell
.\.venv\Scripts\python.exe -m flask --app app run
```

---

## Usuarios de prueba

Al arrancar la aplicación por primera vez se crea automáticamente `incidencias.db` con los siguientes usuarios de prueba:

| Usuario | Contraseña | Rol |
| :--- | :--- | :--- |
| `usuario` | `usuario123` | `usuario` |
| `maria` | `maria123` | `usuario` |
| `tecnico` | `tecnico123` | `tecnico` |

---

## Ejecución de tests

Los tests usan una base de datos temporal y un modelo simulado para las pruebas de IA (no requieren que LM Studio esté encendido):

```powershell
.\.venv\Scripts\python.exe -m pytest
```
