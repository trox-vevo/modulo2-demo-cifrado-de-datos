# Demo: cifrado de datos en Qhatu Marketplace

Mini-servicio que simula el registro de vendedores (del modulo **Vendedores**) protegiendo sus datos sensibles: **DNI** y **cuenta bancaria** (usada en liquidaciones del modulo **Pagos**).

## Que demuestra

| Tecnica                                               | Donde                               | Escenario Qhatu                                          |
| ----------------------------------------------------- | ----------------------------------- | -------------------------------------------------------- |
| Cifrado en reposo con **AES-256-GCM**                 | `src/cifrado.py`                    | Proteger DNI y cuenta bancaria si roban la base de datos |
| **Envelope encryption** (DEK por campo + KEK maestra) | `src/cifrado.py`                    | Rotar claves sin re-cifrar todos los datos               |
| Contexto autenticado (AAD)                            | `cifrar_campo(..., contexto)`       | Un cifrado copiado a otro registro no descifra           |
| **Indice ciego** (HMAC)                               | `indice_ciego()`                    | VEN-05: detectar un DNI ya registrado sin descifrar      |
| Control de acceso por rol al descifrar                | `src/main.py`                       | Solo `verificador` ve el DNI, solo `pagos` ve la cuenta  |
| Deteccion de alteracion                               | AES-GCM (etiqueta de autenticacion) | Un dato modificado en la base no se acepta               |
| Rotacion de claves                                    | `src/rotar_claves.py`               | Cambiar la clave maestra si se compromete                |

Lo que **no** se cifra en Qhatu, y por que: las contrasenas llevan _hash_ (Argon2/bcrypt), no cifrado, porque nunca deben poder recuperarse; y los datos de tarjeta no pasan por Qhatu (PAG-05), solo se guarda un token de la pasarela.

## Instalacion

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -r requirements.txt
python -m src.generar_claves      # crea .env con claves aleatorias (NO se sube a GitHub)
```

## Uso

```bash
python ui_demo.py                   # DEMO VISUAL en el navegador
python demo.py                      # recorrido guiado de 6 pasos en consola (con pausas)
python demo.py --auto               # el mismo recorrido sin pausas
python -m pytest                    # 22 pruebas automaticas
python -m uvicorn src.main:app      # API en http://127.0.0.1:8000/docs (Swagger)
python -m src.rotar_claves --a v2   # rotar la clave maestra de v1 a v2
```

En Swagger, los endpoints de lectura piden el header `X-Rol` (`verificador`, `pagos`, `admin` o cualquier otro para ver el 403).

## Demo visual

`python ui_demo.py` abre `http://127.0.0.1:8000/` en el navegador. La pagina recorre los mismos 6 pasos que `demo.py`, pero mostrando lado a lado la aplicacion, el servidor y la base de datos:

| Paso                     | Que se ve                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------- |
| 1. Registro              | El cifrado real paso a paso: dato en claro, DEK, nonce, AES-256-GCM, DEK envuelta con la KEK |
| 2. Robo de la base       | Las filas tal como estan en disco y un buscador: el DNI no aparece en ninguna parte          |
| 3. Roles                 | Llamadas reales a la API con 200 / 403 segun el rol                                          |
| 4. Suplantacion (VEN-05) | Dos indices ciegos iguales: DNI duplicado detectado sin descifrar                            |
| 5. Alteracion            | Un bit cambiado en la base; la API responde 500 y se niega a devolver el dato                |
| 6. Rotacion              | Tabla antes/despues: `kek` y `wdek` cambian, `ct` queda IGUAL; la clave vieja ya no descifra |

Controles: botones del paso, o `←` `→` para cambiar de paso y `Enter` para ejecutarlo. "Reiniciar demo" deja todo limpio.
Los valores del paso 1 (DEK recortada, nonce, etiqueta) son los reales de ese registro. Los endpoints `/ui/...` solo existen si `QHATU_DEMO_UI=1`, que es lo que activa `ui_demo.py`; la API normal no los expone.

## Estructura

```
src/cifrado.py         <- modulo reutilizable: es lo que se integra al proyecto final
src/main.py            <- API de ejemplo (FastAPI)
src/vendedores.py      <- registro de vendedores (compartido por la API y la demo visual)
src/ui.py              <- endpoints de apoyo de la demo visual (solo con QHATU_DEMO_UI=1)
static/index.html      <- pagina de la demo visual
ui_demo.py             <- lanzador de la demo visual
src/db.py              <- SQLite minimo
src/rotar_claves.py    <- rotacion de la clave maestra
src/generar_claves.py  <- crea .env
tests/                 <- pruebas de cifrado y de API
demo.py                <- recorrido para el video
```

## Como integrarlo al proyecto Qhatu

1. Copiar `src/cifrado.py` al modulo que lo necesite (Vendedores, Pagos).
2. En cada escritura: `cifrar_campo(keyring, valor, f"<entidad>:<id>:<campo>")` y guardar el resultado en una columna de texto. Si se necesita buscar por ese campo, guardar tambien `indice_ciego(keyring, valor)` con indice unico.
3. En cada lectura: verificar el rol **antes** de llamar a `descifrar_campo`.
4. En produccion, las claves no van en un `.env`: se piden a un gestor de secretos o KMS del proveedor cloud (AWS KMS, Azure Key Vault, GCP KMS). Solo cambia `Keyring.desde_entorno()`; el resto del codigo no.

## Errores comunes que este codigo evita

- **Reutilizar el nonce** con la misma clave: aqui cada cifrado usa un nonce aleatorio nuevo y su propia DEK.
- **Modo ECB o cifrado sin autenticacion**: GCM detecta cualquier alteracion.
- **Claves en el repositorio**: `.env` esta en `.gitignore`; solo se sube el codigo.
- **Usar la misma clave para cifrar y para el indice**: el indice ciego usa una clave propia.

## Limitaciones

- El rol se simula con el header `X-Rol`. En el proyecto real debe salir de un token firmado (JWT) validado.
- El indice ciego revela cuales registros tienen el mismo valor (es su funcion). Para datos de pocos valores posibles conviene limitarlo a campos donde ese dato sea aceptable, como aqui el DNI.
- Las claves de la demo viven en variables de entorno; un KMS ofrece auditoria y custodia que este ejemplo no tiene.
- Cifrar en la aplicacion protege ante robo de la base de datos, pero no ante un atacante que ya controle el servidor de aplicaciones con acceso a las claves.
