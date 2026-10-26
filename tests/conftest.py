import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app import create_app


@pytest.fixture
def app(tmp_path):
    ruta_db = tmp_path / "test_incidencias.db"
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(ruta_db),
            "SECRET_KEY": "test-secret",
        }
    )
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
