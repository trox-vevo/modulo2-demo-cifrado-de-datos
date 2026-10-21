"""
Demo visual: python ui_demo.py
Abre http://127.0.0.1:8000/ en el navegador. Parte siempre de una base limpia.
Necesita un .env con claves: python -m src.generar_claves
"""
import os
import threading
import webbrowser
from pathlib import Path

os.environ["QHATU_DEMO_UI"] = "1"  # activa los endpoints de apoyo de la pagina (solo demo)

import uvicorn  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src.db import ruta_db  # noqa: E402

URL = "http://127.0.0.1:8000/"


def main() -> None:
    load_dotenv()
    Path(ruta_db()).unlink(missing_ok=True)
    threading.Timer(1.5, lambda: webbrowser.open(URL)).start()
    print(f"Demo visual en {URL}  (Ctrl+C para cerrar)")
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
