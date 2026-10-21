import base64
import json

from src.db import conexion

VENDEDOR = {"nombre": "Textiles Andinos", "dni": "12345678", "cuenta_bancaria": "002-193-0012345678"}


def _registrar(client, **cambios):
    return client.post("/vendedores", json={**VENDEDOR, **cambios})


def test_registro_devuelve_datos_enmascarados(client):
    r = _registrar(client)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["dni"] == "****5678"
    assert "12345678" not in json.dumps(cuerpo)


def test_la_base_de_datos_no_guarda_texto_plano(client):
    vid = _registrar(client).json()["id"]
    with conexion() as con:
        fila = con.execute("SELECT * FROM vendedores WHERE id = ?", (vid,)).fetchone()
    assert VENDEDOR["cuenta_bancaria"] not in fila["cuenta_cifrada"]
    assert b"12345678" not in base64.b64decode(json.loads(fila["dni_cifrado"])["ct"])
    assert fila["dni_cifrado"] != "12345678"


def test_dni_duplicado_se_detecta_sin_descifrar(client):
    assert _registrar(client).status_code == 201
    r = _registrar(client, nombre="Otra Persona", cuenta_bancaria="999-888-7776665554")
    assert r.status_code == 409
    assert "revision manual" in r.json()["detail"]


def test_lectura_autorizada_y_prohibida(client):
    vid = _registrar(client).json()["id"]
    ok = client.get(f"/vendedores/{vid}/dni", headers={"X-Rol": "verificador"})
    assert ok.status_code == 200 and ok.json()["dni"] == "12345678"
    assert client.get(f"/vendedores/{vid}/dni", headers={"X-Rol": "soporte"}).status_code == 403
    assert client.get(f"/vendedores/{vid}/dni").status_code == 403


def test_cada_campo_tiene_su_propio_rol(client):
    vid = _registrar(client).json()["id"]
    assert client.get(f"/vendedores/{vid}/cuenta", headers={"X-Rol": "verificador"}).status_code == 403
    r = client.get(f"/vendedores/{vid}/cuenta", headers={"X-Rol": "pagos"})
    assert r.json()["cuenta_bancaria"] == VENDEDOR["cuenta_bancaria"]


def test_dato_alterado_en_la_base_devuelve_error(client):
    vid = _registrar(client).json()["id"]
    with conexion() as con:
        sobre = json.loads(con.execute("SELECT dni_cifrado FROM vendedores").fetchone()[0])
        sobre["ct"] = base64.b64encode(b"\x00" * 24).decode()
        con.execute("UPDATE vendedores SET dni_cifrado = ?", (json.dumps(sobre),))
    r = client.get(f"/vendedores/{vid}/dni", headers={"X-Rol": "admin"})
    assert r.status_code == 500


def test_validacion_de_entrada(client):
    assert _registrar(client, dni="123").status_code == 422
    assert _registrar(client, cuenta_bancaria="abc").status_code == 422
    assert client.get("/vendedores/no-existe").status_code == 404
