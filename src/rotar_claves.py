"""Rota la clave maestra: python -m src.rotar_claves --a v2"""
import argparse

from .cifrado import CifradoError, Keyring, obtener_keyring, reenvolver_dek
from .db import conexion


def rotar(keyring: Keyring, destino: str) -> int:
    """Re-envuelve la DEK de cada campo con la KEK destino. Devuelve cuantos vendedores se actualizaron."""
    if destino not in keyring.keks:
        raise CifradoError(f"La KEK '{destino}' no esta configurada")
    total = 0
    with conexion() as con:  # una sola transaccion: o se rota todo o nada
        filas = con.execute("SELECT id, dni_cifrado, cuenta_cifrada FROM vendedores").fetchall()
        for f in filas:
            con.execute(
                "UPDATE vendedores SET dni_cifrado = ?, cuenta_cifrada = ? WHERE id = ?",
                (
                    reenvolver_dek(keyring, f["dni_cifrado"], destino),
                    reenvolver_dek(keyring, f["cuenta_cifrada"], destino),
                    f["id"],
                ),
            )
            total += 1
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="Rotacion de clave maestra (KEK)")
    p.add_argument("--a", required=True, help="id de la KEK destino, ej. v2")
    args = p.parse_args()
    n = rotar(obtener_keyring(), args.a.lower())
    print(f"{n} vendedor(es) migrados a la KEK '{args.a}'.")
    print(f"Ahora cambia QHATU_ACTIVE_KEK_ID={args.a} en .env para que los nuevos registros la usen.")


if __name__ == "__main__":
    main()
