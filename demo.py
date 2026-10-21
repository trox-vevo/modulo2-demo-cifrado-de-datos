"""
Demo guiada para el video: python demo.py          (con pausas, ideal para grabar)
                           python demo.py --auto   (sin pausas)
Necesita un .env con claves: python -m src.generar_claves
"""
import json
import sqlite3
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from src.cifrado import CifradoError, Keyring, descifrar_campo, obtener_keyring  # noqa: E402
from src.db import ruta_db  # noqa: E402
from src.main import app  # noqa: E402
from src.rotar_claves import rotar  # noqa: E402

AUTO = "--auto" in sys.argv


def titulo(n: int, texto: str) -> None:
    print(f"\n{'=' * 72}\nPASO {n}: {texto}\n{'=' * 72}")


def pausa() -> None:
    if not AUTO:
        input("\n[Enter para continuar] ")


def mostrar(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def fila_cruda(vid: str) -> sqlite3.Row:
    con = sqlite3.connect(ruta_db())
    con.row_factory = sqlite3.Row
    try:
        return con.execute("SELECT * FROM vendedores WHERE id = ?", (vid,)).fetchone()
    finally:
        con.close()


def resumir(sobre_json: str) -> dict:
    s = json.loads(sobre_json)
    return {**s, "wdek": s["wdek"][:24] + "...", "ct": s["ct"][:24] + "..."}


def main() -> None:
    Path(ruta_db()).unlink(missing_ok=True)  # la demo parte siempre de una base limpia
    kr = obtener_keyring()
    datos = {"nombre": "Textiles Andinos SAC", "dni": "12345678", "cuenta_bancaria": "00219300123456789012"}

    with TestClient(app) as api:
        titulo(1, "Un vendedor se registra en el marketplace (datos en claro por HTTPS)")
        print("POST /vendedores"); mostrar(datos)
        r = api.post("/vendedores", json=datos)
        print(f"\nRespuesta {r.status_code} (la API devuelve los datos enmascarados):"); mostrar(r.json())
        vid = r.json()["id"]
        pausa()

        titulo(2, "Lo que un atacante veria si roba la base de datos")
        fila = fila_cruda(vid)
        print("dni_cifrado    ->"); mostrar(resumir(fila["dni_cifrado"]))
        print("\ncuenta_cifrada ->", fila["cuenta_cifrada"][:70] + "...")
        print("\nDNI y cuenta bancaria no aparecen en ninguna parte: solo texto ilegible.")
        print("Cada campo tiene su propia clave de datos (wdek) protegida por la clave maestra (kek).")
        pausa()

        titulo(3, "Lectura autorizada: solo los roles con permiso ven el dato")
        for rol in ("verificador", "soporte"):
            r = api.get(f"/vendedores/{vid}/dni", headers={"X-Rol": rol})
            print(f"GET /dni con rol '{rol}': {r.status_code} -> {r.json()}")
        r = api.get(f"/vendedores/{vid}/cuenta", headers={"X-Rol": "pagos"})
        print(f"GET /cuenta con rol 'pagos': {r.status_code} -> {r.json()}")
        pausa()

        titulo(4, "VEN-05: DNI de otra persona, detectado SIN descifrar (indice ciego)")
        suplantador = {"nombre": "Falso Vendedor", "dni": "12345678", "cuenta_bancaria": "99988877766655544433"}
        r = api.post("/vendedores", json=suplantador)
        print(f"POST con el mismo DNI: {r.status_code} -> {r.json()['detail']}")
        print(f"\nIndice ciego guardado (HMAC del DNI): {fila['dni_bidx'][:40]}...")
        pausa()

        titulo(5, "Integridad: si alguien altera el dato en la base, se detecta")
        original = fila["dni_cifrado"]
        sobre = json.loads(original)
        sobre["ct"] = sobre["ct"][:-4] + "AAAA"
        con = sqlite3.connect(ruta_db())
        con.execute("UPDATE vendedores SET dni_cifrado = ? WHERE id = ?", (json.dumps(sobre), vid))
        con.commit()
        r = api.get(f"/vendedores/{vid}/dni", headers={"X-Rol": "admin"})
        print(f"Tras alterar el dato, GET /dni: {r.status_code} -> {r.json()['detail']}")
        con.execute("UPDATE vendedores SET dni_cifrado = ? WHERE id = ?", (original, vid))
        con.commit()
        con.close()
        print("(dato restaurado para continuar)")
        pausa()

        titulo(6, "Rotacion de claves: v1 -> v2 sin re-cifrar los datos")
        antes = json.loads(fila_cruda(vid)["dni_cifrado"])
        n = rotar(kr, "v2")
        despues = json.loads(fila_cruda(vid)["dni_cifrado"])
        print(f"Vendedores migrados: {n}")
        print(f"kek:  {antes['kek']} -> {despues['kek']}")
        print(f"ct identico (el dato cifrado no se toco): {antes['ct'] == despues['ct']}")
        print(f"wdek distinta (solo cambio la clave envuelta): {antes['wdek'] != despues['wdek']}")

        r = api.get(f"/vendedores/{vid}/dni", headers={"X-Rol": "verificador"})
        print(f"\nLa API sigue funcionando: {r.status_code} -> {r.json()}")

        solo_v2 = Keyring({"v2": kr.keks["v2"]}, "v2", kr.blind_key)
        ctx = f"vendedor:{vid}:dni"
        print("Retiramos la clave v1 del sistema y descifrado con solo v2:",
              descifrar_campo(solo_v2, fila_cruda(vid)["dni_cifrado"], ctx))
        solo_v1 = Keyring({"v1": kr.keks["v1"]}, "v1", kr.blind_key)
        try:
            descifrar_campo(solo_v1, fila_cruda(vid)["dni_cifrado"], ctx)
        except CifradoError:
            print("Con la clave v1 vieja ya NO se puede descifrar: la clave comprometida quedo inutil.")

    print("\nFin de la demo.")


if __name__ == "__main__":
    main()
