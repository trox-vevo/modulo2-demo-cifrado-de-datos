"""API de demo: registro de vendedores con datos sensibles cifrados (Qhatu, modulo Vendedores)."""
import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .cifrado import CifradoError, descifrar_campo, obtener_keyring
from .db import conexion, init_db
from .vendedores import DniDuplicado, VendedorIn, insertar_vendedor

# En el proyecto real el rol saldra del token (JWT). Aqui se simula con el header X-Rol.
ROLES_DNI = {"verificador", "admin"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    obtener_keyring()  # falla al arrancar si faltan claves, no en la primera peticion
    yield


app = FastAPI(title="Qhatu - Demo de cifrado de datos", lifespan=lifespan)


@app.exception_handler(CifradoError)
async def manejar_error_cifrado(_: Request, exc: CifradoError):
    return JSONResponse(status_code=500, content={"detail": f"Integridad del dato comprometida. {exc}"})


@app.post("/vendedores", status_code=201)
def registrar_vendedor(v: VendedorIn):
    try:
        return insertar_vendedor(v)
    except DniDuplicado:
        # VEN-05: el DNI ya pertenece a otro vendedor -> no se registra, pasa a revision manual.
        raise HTTPException(
            status_code=409,
            detail="Ya existe un vendedor con ese DNI. La solicitud pasa a revision manual (VEN-05).",
        )


def _fila(vid: str) -> sqlite3.Row:
    with conexion() as con:
        fila = con.execute("SELECT * FROM vendedores WHERE id = ?", (vid,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")
    return fila


def _exigir_rol(x_rol: str | None, permitidos: set[str]) -> None:
    if x_rol not in permitidos:
        raise HTTPException(status_code=403, detail="Rol sin permiso para ver este dato")


@app.get("/vendedores/{vid}")
def ver_vendedor(vid: str):
    f = _fila(vid)
    return {"id": f["id"], "nombre": f["nombre"], "estado": f["estado"]}


@app.get("/vendedores/{vid}/dni")
def ver_dni(vid: str, x_rol: str | None = Header(default=None)):
    _exigir_rol(x_rol, ROLES_DNI)
    f = _fila(vid)
    return {"dni": descifrar_campo(obtener_keyring(), f["dni_cifrado"], f"vendedor:{vid}:dni")}


# Interfaz visual de la demo: solo se activa si se pide expresamente (ver ui_demo.py).
# Incluye operaciones como "alterar un dato", que NO deben existir en una API real.
if os.environ.get("QHATU_DEMO_UI") == "1":
    from .ui import router as ui_router

    app.include_router(ui_router)
