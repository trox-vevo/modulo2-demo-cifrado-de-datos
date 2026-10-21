"""
Endpoints de apoyo para la interfaz visual de la demo (static/index.html).

SOLO PARA DEMO: incluye operaciones como "alterar un dato en la base", que no deben existir
en una API real. Por eso main.py solo carga este router si QHATU_DEMO_UI=1 (ver ui_demo.py).
La pagina usa los endpoints reales de la API (/vendedores/...) para leer datos descifrados;
aqui solo hay lo necesario para mostrar la base "por dentro".
"""
import base64
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .cifrado import CifradoError, Keyring, descifrar_campo, obtener_keyring
from .db import conexion
from .rotar_claves import rotar
from .vendedores import DniDuplicado, VendedorIn, insertar_vendedor

router = APIRouter()
_ESTATICO = Path(__file__).resolve().parent.parent / "static"
_ORIGINALES: dict[str, str] = {}  # dni_cifrado original de cada registro alterado, para restaurarlo


def _sobre(texto: str):
    try:
        return json.loads(texto)
    except ValueError:
        return None


def _fila(vid: str):
    with conexion() as con:
        f = con.execute("SELECT * FROM vendedores WHERE id = ?", (vid,)).fetchone()
    if f is None:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")
    return f


@router.get("/", include_in_schema=False)
def pagina():
    return FileResponse(_ESTATICO / "index.html")


@router.get("/ui/estado")
def estado():
    kr = obtener_keyring()
    with conexion() as con:
        total = con.execute("SELECT COUNT(*) FROM vendedores").fetchone()[0]
    return {"kek_activa": kr.activa, "keks": sorted(kr.keks), "total": total}


@router.get("/ui/db")
def ver_base():
    """Las filas tal como estan guardadas: lo que veria quien robe el archivo de la base."""
    with conexion() as con:
        filas = con.execute("SELECT * FROM vendedores ORDER BY creado_en").fetchall()
    return [
        {
            "id": f["id"],
            "nombre": f["nombre"],
            "estado": f["estado"],
            "dni_bidx": f["dni_bidx"],
            "dni_cifrado": _sobre(f["dni_cifrado"]),
            "cuenta_cifrada": _sobre(f["cuenta_cifrada"]),
            "alterado": f["id"] in _ORIGINALES,
        }
        for f in filas
    ]


@router.post("/ui/registrar")
def registrar(v: VendedorIn):
    traza: dict = {}
    try:
        vendedor = insertar_vendedor(v, traza)
    except DniDuplicado as e:
        return JSONResponse(
            status_code=409,
            content={"detail": "Ya existe un vendedor con ese DNI. La solicitud pasa a revision manual (VEN-05).",
                     "bidx": e.bidx},
        )
    return {"vendedor": vendedor, "traza": traza}


@router.post("/ui/alterar/{vid}")
def alterar(vid: str):
    """Simula a alguien con acceso a la base que cambia un solo bit del DNI cifrado."""
    f = _fila(vid)
    sobre = json.loads(f["dni_cifrado"])
    if vid not in _ORIGINALES:
        _ORIGINALES[vid] = f["dni_cifrado"]
    ct = bytearray(base64.b64decode(sobre["ct"]))
    ct[0] ^= 0x01
    sobre["ct"] = base64.b64encode(bytes(ct)).decode()
    with conexion() as con:
        con.execute("UPDATE vendedores SET dni_cifrado = ? WHERE id = ?", (json.dumps(sobre, separators=(",", ":")), vid))
    return {"ok": True}


@router.post("/ui/restaurar/{vid}")
def restaurar(vid: str):
    original = _ORIGINALES.pop(vid, None)
    if original is None:
        raise HTTPException(status_code=404, detail="Ese registro no fue alterado")
    with conexion() as con:
        con.execute("UPDATE vendedores SET dni_cifrado = ? WHERE id = ?", (original, vid))
    return {"ok": True}


class RotarIn(BaseModel):
    destino: str


@router.post("/ui/rotar")
def rotar_clave(r: RotarIn):
    kr = obtener_keyring()
    destino = r.destino.lower()
    try:
        migrados = rotar(kr, destino)
    except CifradoError as e:
        raise HTTPException(status_code=400, detail=str(e))
    kr.activa = destino  # equivale a cambiar QHATU_ACTIVE_KEK_ID: los registros nuevos usan la KEK nueva
    return {"migrados": migrados, "kek_activa": kr.activa}


@router.get("/ui/probar-claves/{vid}")
def probar_claves(vid: str):
    """Intenta descifrar el DNI con un llavero que solo tiene UNA clave maestra a la vez."""
    kr = obtener_keyring()
    f = _fila(vid)
    ctx = f"vendedor:{vid}:dni"
    resultado = {}
    for kek_id in sorted(kr.keks):
        solo = Keyring({kek_id: kr.keks[kek_id]}, kek_id, kr.blind_key)
        try:
            resultado[kek_id] = {"ok": True, "dni": descifrar_campo(solo, f["dni_cifrado"], ctx)}
        except CifradoError:
            resultado[kek_id] = {"ok": False}
    return resultado


@router.post("/ui/reset")
def reiniciar():
    kr = obtener_keyring()
    with conexion() as con:
        con.execute("DELETE FROM vendedores")
    _ORIGINALES.clear()
    kr.activa = "v1" if "v1" in kr.keks else sorted(kr.keks)[0]
    return {"ok": True, "kek_activa": kr.activa}
