"""Logica de registro de vendedores, compartida por la API (main.py) y la interfaz visual (ui.py)."""
import sqlite3
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .cifrado import cifrar_campo, indice_ciego, obtener_keyring
from .db import conexion


class VendedorIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    dni: str = Field(pattern=r"^\d{8}$")
    cuenta_bancaria: str = Field(pattern=r"^[0-9-]{10,30}$")


class DniDuplicado(Exception):
    """VEN-05: el DNI ya pertenece a otro vendedor. Lleva el indice ciego que lo delato."""

    def __init__(self, bidx: str):
        super().__init__("DNI duplicado")
        self.bidx = bidx


def enmascarar(valor: str) -> str:
    return "*" * (len(valor) - 4) + valor[-4:]


def insertar_vendedor(v: VendedorIn, traza: dict | None = None) -> dict:
    """Cifra y guarda al vendedor. Si `traza` es un dict, se llena con los pasos del cifrado (demo)."""
    kr = obtener_keyring()
    vid = uuid.uuid4().hex
    bidx = indice_ciego(kr, v.dni)
    t_dni: dict | None = {} if traza is not None else None
    t_cuenta: dict | None = {} if traza is not None else None
    try:
        with conexion() as con:
            con.execute(
                "INSERT INTO vendedores (id, nombre, dni_cifrado, dni_bidx, cuenta_cifrada, creado_en) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    vid,
                    v.nombre,
                    cifrar_campo(kr, v.dni, f"vendedor:{vid}:dni", t_dni),
                    bidx,
                    cifrar_campo(kr, v.cuenta_bancaria, f"vendedor:{vid}:cuenta", t_cuenta),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    except sqlite3.IntegrityError:
        raise DniDuplicado(bidx) from None
    if traza is not None:
        traza.update(dni=t_dni, cuenta=t_cuenta, bidx=bidx)
    return {
        "id": vid,
        "nombre": v.nombre,
        "estado": "pendiente_verificacion",
        "dni": enmascarar(v.dni),
        "cuenta_bancaria": enmascarar(v.cuenta_bancaria),
    }
