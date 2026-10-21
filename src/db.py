"""Acceso minimo a SQLite para la demo."""
import os
import sqlite3
from contextlib import contextmanager

ESQUEMA = """
CREATE TABLE IF NOT EXISTS vendedores (
    id             TEXT PRIMARY KEY,
    nombre         TEXT NOT NULL,
    dni_cifrado    TEXT NOT NULL,
    dni_bidx       TEXT NOT NULL UNIQUE,   -- indice ciego: detecta DNI duplicado sin descifrar
    cuenta_cifrada TEXT NOT NULL,
    estado         TEXT NOT NULL DEFAULT 'pendiente_verificacion',
    creado_en      TEXT NOT NULL
);
"""


def ruta_db() -> str:
    return os.environ.get("QHATU_DB_PATH", "qhatu_demo.db")


@contextmanager
def conexion():
    con = sqlite3.connect(ruta_db())
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with conexion() as con:
        con.executescript(ESQUEMA)
