"""Crea un archivo .env con claves aleatorias para la demo: python -m src.generar_claves"""
import base64
import os
import sys
from pathlib import Path


def _clave() -> str:
    return base64.b64encode(os.urandom(32)).decode("ascii")


def main() -> None:
    destino = Path(".env")
    if destino.exists():
        print(".env ya existe, no se sobrescribe. Borralo si quieres generar claves nuevas.")
        sys.exit(1)
    lineas = [
        "# Claves de DEMO. Este archivo NO debe subirse a GitHub (.gitignore ya lo excluye).",
        "QHATU_ACTIVE_KEK_ID=v1",
        f"QHATU_KEK_V1={_clave()}",
        f"QHATU_KEK_V2={_clave()}",
        f"QHATU_BLIND_INDEX_KEY={_clave()}",
        "QHATU_DB_PATH=qhatu_demo.db",
    ]
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("Listo: se creo .env con claves nuevas (v1, v2 e indice ciego).")


if __name__ == "__main__":
    main()
