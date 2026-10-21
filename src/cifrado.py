"""
Servicio de cifrado de campos para Qhatu (envelope encryption).

Este es el modulo que se integrara despues a Vendedores y Pagos.
No depende de FastAPI ni de la base de datos: solo recibe texto y devuelve texto.

Esquema:
  - Cada campo se cifra con su propia clave de datos (DEK, 256 bits) usando AES-256-GCM.
  - La DEK se "envuelve" (se cifra) con una clave maestra (KEK) y se guarda junto al dato.
  - Rotar la KEK solo obliga a re-envolver las DEK, no a re-cifrar todos los datos.
  - El contexto (AAD) ata el cifrado a un registro y campo concretos: si alguien copia
    el cifrado de un vendedor a otro, el descifrado falla.
"""
import base64
import hashlib
import hmac
import json
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

_PREFIJO_KEK = "QHATU_KEK_"
_TAM_NONCE = 12  # 96 bits, tamano recomendado para GCM


class CifradoError(Exception):
    """No se pudo cifrar o descifrar (clave incorrecta, dato alterado, formato invalido)."""


def _b64e(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def _b64d(texto: str) -> bytes:
    return base64.b64decode(texto.encode("ascii"))


class Keyring:
    """Conjunto de claves maestras (KEK) y la clave del indice ciego."""

    def __init__(self, keks: dict[str, bytes], activa: str, blind_key: bytes):
        if activa not in keks:
            raise CifradoError(f"La KEK activa '{activa}' no esta configurada")
        for id_, clave in {**keks, "blind": blind_key}.items():
            if len(clave) != 32:
                raise CifradoError(f"La clave '{id_}' debe tener 32 bytes (256 bits)")
        self.keks = keks
        self.activa = activa
        self.blind_key = blind_key

    @classmethod
    def desde_entorno(cls) -> "Keyring":
        load_dotenv()  # lee .env si existe; no pisa variables ya definidas
        keks = {
            nombre.removeprefix(_PREFIJO_KEK).lower(): _b64d(valor)
            for nombre, valor in os.environ.items()
            if nombre.startswith(_PREFIJO_KEK)
        }
        try:
            activa = os.environ["QHATU_ACTIVE_KEK_ID"].lower()
            blind = _b64d(os.environ["QHATU_BLIND_INDEX_KEY"])
        except KeyError as e:
            raise CifradoError(
                f"Falta la variable {e}. Ejecuta: python -m src.generar_claves"
            ) from e
        return cls(keks, activa, blind)


@lru_cache(maxsize=1)
def obtener_keyring() -> Keyring:
    return Keyring.desde_entorno()


def _envolver(kek: bytes, dek: bytes, kek_id: str) -> str:
    nonce = os.urandom(_TAM_NONCE)
    envuelta = AESGCM(kek).encrypt(nonce, dek, kek_id.encode())
    return _b64e(nonce + envuelta)


def _desenvolver(kek: bytes, dek_envuelta: str, kek_id: str) -> bytes:
    crudo = _b64d(dek_envuelta)
    return AESGCM(kek).decrypt(crudo[:_TAM_NONCE], crudo[_TAM_NONCE:], kek_id.encode())


def cifrar_campo(keyring: Keyring, texto: str, contexto: str, traza: dict | None = None) -> str:
    """
    Cifra un texto. `contexto` identifica registro y campo, ej. 'vendedor:<id>:dni'.

    `traza` es opcional y solo sirve para la demo visual: si se pasa un dict, se llena con los
    pasos intermedios (la clave de datos se entrega TRUNCADA; la real nunca sale de esta funcion).
    """
    dek = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(_TAM_NONCE)  # nunca se reutiliza con la misma clave
    ct = AESGCM(dek).encrypt(nonce, texto.encode("utf-8"), contexto.encode("utf-8"))
    wdek = _envolver(keyring.keks[keyring.activa], dek, keyring.activa)
    sobre = {
        "v": 1,
        "kek": keyring.activa,
        "wdek": wdek,
        "n": _b64e(nonce),
        "ct": _b64e(ct),
    }
    if traza is not None:
        traza.update(
            texto=texto,
            contexto=contexto,
            dek_vista=dek.hex()[:16] + "...",
            nonce_hex=nonce.hex(),
            cifrado_hex=ct[:-16].hex(),
            tag_hex=ct[-16:].hex(),  # GCM agrega 16 bytes de etiqueta de autenticacion al final
            kek=keyring.activa,
            wdek_vista=wdek[:24] + "...",
        )
    return json.dumps(sobre, separators=(",", ":"))


def descifrar_campo(keyring: Keyring, sobre_json: str, contexto: str) -> str:
    try:
        sobre = json.loads(sobre_json)
        kek_id = sobre["kek"]
        dek = _desenvolver(keyring.keks[kek_id], sobre["wdek"], kek_id)
        texto = AESGCM(dek).decrypt(
            _b64d(sobre["n"]), _b64d(sobre["ct"]), contexto.encode("utf-8")
        )
        return texto.decode("utf-8")
    except (KeyError, ValueError, InvalidTag) as e:
        # No revelamos el motivo exacto: da lo mismo clave mala, dato alterado o contexto distinto.
        raise CifradoError("No se pudo descifrar: clave incorrecta o dato alterado") from e


def reenvolver_dek(keyring: Keyring, sobre_json: str, nueva_kek_id: str) -> str:
    """Rotacion de KEK: cambia solo la DEK envuelta. El dato cifrado (ct) queda intacto."""
    if nueva_kek_id not in keyring.keks:
        raise CifradoError(f"La KEK '{nueva_kek_id}' no esta configurada")
    try:
        sobre = json.loads(sobre_json)
        viejo_id = sobre["kek"]
        dek = _desenvolver(keyring.keks[viejo_id], sobre["wdek"], viejo_id)
    except (KeyError, ValueError, InvalidTag) as e:
        raise CifradoError("No se pudo re-envolver la clave de datos") from e
    sobre["kek"] = nueva_kek_id
    sobre["wdek"] = _envolver(keyring.keks[nueva_kek_id], dek, nueva_kek_id)
    return json.dumps(sobre, separators=(",", ":"))


def indice_ciego(keyring: Keyring, valor: str) -> str:
    """
    HMAC-SHA256 del valor normalizado. Permite buscar o detectar duplicados (ej. mismo DNI)
    sin descifrar. Usa una clave distinta a las de cifrado.
    """
    normalizado = valor.strip().upper()
    return hmac.new(keyring.blind_key, normalizado.encode("utf-8"), hashlib.sha256).hexdigest()
