"""Claves de PRUEBA fijas. Se definen antes de importar la app para no depender de tu .env."""
import base64
import os

import pytest
from fastapi.testclient import TestClient


def _k(byte: int) -> str:
    return base64.b64encode(bytes([byte]) * 32).decode()


os.environ["QHATU_ACTIVE_KEK_ID"] = "v1"
os.environ["QHATU_KEK_V1"] = _k(1)
os.environ["QHATU_KEK_V2"] = _k(2)
os.environ["QHATU_BLIND_INDEX_KEY"] = _k(9)

from src.cifrado import Keyring  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture
def keyring():
    return Keyring.desde_entorno()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("QHATU_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c
