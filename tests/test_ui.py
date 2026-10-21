"""Pruebas de los endpoints de apoyo de la interfaz visual (solo demo)."""
import pytest

from src.main import app
from src.ui import router

if not any(getattr(r, "path", None) == "/ui/db" for r in app.routes):  # evita duplicar si ya estaba
    app.include_router(router)

DATOS = {"nombre": "Textiles Andinos SAC", "dni": "12345678", "cuenta_bancaria": "00219300123456789012"}


@pytest.fixture
def ui(client):
    yield client
    client.post("/ui/reset")  # deja la clave activa en v1 para no afectar a otras pruebas


def test_registrar_devuelve_traza_real(ui):
    r = ui.post("/ui/registrar", json=DATOS)
    assert r.status_code == 200
    t = r.json()["traza"]["dni"]
    assert t["texto"] == "12345678" and len(t["nonce_hex"]) == 24 and len(t["tag_hex"]) == 32
    assert t["dek_vista"].endswith("...")  # la clave de datos real no sale completa
    assert "12345678" not in str(ui.get("/ui/db").json()[0]["dni_cifrado"])


def test_dni_duplicado_devuelve_409_con_indice_ciego(ui):
    ui.post("/ui/registrar", json=DATOS)
    r = ui.post("/ui/registrar", json={**DATOS, "nombre": "Falso Vendedor"})
    assert r.status_code == 409
    assert r.json()["bidx"] == ui.get("/ui/db").json()[0]["dni_bidx"]


def test_alterar_se_detecta_y_restaurar_lo_arregla(ui):
    vid = ui.post("/ui/registrar", json=DATOS).json()["vendedor"]["id"]
    ui.post(f"/ui/alterar/{vid}")
    assert ui.get("/ui/db").json()[0]["alterado"] is True
    assert ui.get(f"/vendedores/{vid}/dni", headers={"X-Rol": "admin"}).status_code == 500
    ui.post(f"/ui/restaurar/{vid}")
    assert ui.get(f"/vendedores/{vid}/dni", headers={"X-Rol": "admin"}).json() == {"dni": "12345678"}


def test_rotar_deja_inutil_la_clave_vieja(ui):
    vid = ui.post("/ui/registrar", json=DATOS).json()["vendedor"]["id"]
    antes = ui.get("/ui/db").json()[0]["dni_cifrado"]
    assert ui.post("/ui/rotar", json={"destino": "v2"}).json()["migrados"] == 1
    despues = ui.get("/ui/db").json()[0]["dni_cifrado"]
    assert (antes["kek"], despues["kek"]) == ("v1", "v2")
    assert antes["ct"] == despues["ct"] and antes["wdek"] != despues["wdek"]
    pruebas = ui.get(f"/ui/probar-claves/{vid}").json()
    assert pruebas["v1"]["ok"] is False and pruebas["v2"]["dni"] == "12345678"


def test_rotar_a_clave_inexistente_da_400(ui):
    assert ui.post("/ui/rotar", json={"destino": "v9"}).status_code == 400
