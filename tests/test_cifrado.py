import json

import pytest

from src.cifrado import (
    CifradoError,
    Keyring,
    cifrar_campo,
    descifrar_campo,
    indice_ciego,
    reenvolver_dek,
)

CTX = "vendedor:abc:dni"


def test_ida_y_vuelta(keyring):
    sobre = cifrar_campo(keyring, "12345678", CTX)
    assert descifrar_campo(keyring, sobre, CTX) == "12345678"


def test_mismo_texto_produce_cifrados_distintos(keyring):
    # Nonce y DEK nuevos en cada llamada: no se puede deducir que dos datos son iguales.
    assert cifrar_campo(keyring, "12345678", CTX) != cifrar_campo(keyring, "12345678", CTX)


def test_contexto_incorrecto_falla(keyring):
    # Copiar el cifrado de un vendedor a otro registro no sirve.
    sobre = cifrar_campo(keyring, "12345678", CTX)
    with pytest.raises(CifradoError):
        descifrar_campo(keyring, sobre, "vendedor:otro:dni")


def test_clave_incorrecta_falla(keyring):
    sobre = cifrar_campo(keyring, "12345678", CTX)
    otra = Keyring({"v1": b"\x07" * 32}, "v1", keyring.blind_key)
    with pytest.raises(CifradoError):
        descifrar_campo(otra, sobre, CTX)


def test_dato_alterado_se_detecta(keyring):
    sobre = json.loads(cifrar_campo(keyring, "12345678", CTX))
    ct = bytearray(__import__("base64").b64decode(sobre["ct"]))
    ct[0] ^= 1  # cambiamos un solo bit
    sobre["ct"] = __import__("base64").b64encode(bytes(ct)).decode()
    with pytest.raises(CifradoError):
        descifrar_campo(keyring, json.dumps(sobre), CTX)


def test_rotacion_conserva_dato_y_no_toca_el_cifrado(keyring):
    original = cifrar_campo(keyring, "12345678", CTX)
    rotado = reenvolver_dek(keyring, original, "v2")
    a, b = json.loads(original), json.loads(rotado)
    assert (a["kek"], b["kek"]) == ("v1", "v2")
    assert a["ct"] == b["ct"] and a["n"] == b["n"]  # el dato cifrado no cambio
    assert descifrar_campo(keyring, rotado, CTX) == "12345678"


def test_tras_rotar_ya_no_hace_falta_la_kek_vieja(keyring):
    rotado = reenvolver_dek(keyring, cifrar_campo(keyring, "12345678", CTX), "v2")
    solo_v2 = Keyring({"v2": keyring.keks["v2"]}, "v2", keyring.blind_key)
    assert descifrar_campo(solo_v2, rotado, CTX) == "12345678"


def test_indice_ciego_es_estable_y_normaliza(keyring):
    assert indice_ciego(keyring, "12345678") == indice_ciego(keyring, " 12345678 ")
    assert indice_ciego(keyring, "12345678") != indice_ciego(keyring, "12345679")


def test_indice_ciego_depende_de_la_clave(keyring):
    otra = Keyring(keyring.keks, "v1", b"\x05" * 32)
    assert indice_ciego(keyring, "12345678") != indice_ciego(otra, "12345678")


def test_clave_de_tamano_incorrecto_se_rechaza():
    with pytest.raises(CifradoError):
        Keyring({"v1": b"corta"}, "v1", b"\x00" * 32)
