# Demo: cifrado de datos en Qhatu Marketplace

Mini-servicio que simula el registro de vendedores (módulo **Vendedores, Reputación y Disputas**) protegiendo sus datos sensibles: **DNI** y **cuenta bancaria** (esta última se usa en las liquidaciones del módulo **Pagos**). Incluye una **demo visual** en el navegador que muestra paso a paso cómo se cifran los datos, qué ve un atacante que roba la base y qué pasa al rotar las claves.

Proyecto del curso Arquitectura de Software (Universidad de Lima, 2026-2). Tema individual: _Cifrado de datos_.

## Contenido

1. [Qué demuestra](#qué-demuestra)
2. [Requisitos](#requisitos)
3. [Instalación](#instalación)
4. [Cómo usarlo](#cómo-usarlo)
   - [A. Demo visual en el navegador (recomendada)](#a-demo-visual-en-el-navegador-recomendada)
   - [B. Demo en consola](#b-demo-en-consola)
   - [C. API con Swagger](#c-api-con-swagger)
   - [D. Pruebas automáticas](#d-pruebas-automáticas)
   - [E. Rotar la clave maestra a mano](#e-rotar-la-clave-maestra-a-mano)
5. [Cómo funciona el cifrado](#cómo-funciona-el-cifrado)
6. [Variables de entorno](#variables-de-entorno)
7. [Estructura del proyecto](#estructura-del-proyecto)
8. [Cómo integrarlo al proyecto de Qhatu](#cómo-integrarlo-al-proyecto-de-qhatu)
9. [Problemas frecuentes](#problemas-frecuentes)
10. [Decisiones de diseño y limitaciones](#decisiones-de-diseño-y-limitaciones)

## Qué demuestra

| Técnica                                                                | Dónde                                | Escenario Qhatu                                                              |
| ---------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------- |
| Cifrado en reposo con **AES-256-GCM**                                  | `src/cifrado.py`                     | Proteger DNI y cuenta bancaria si roban la base de datos (RES-01, Ley 29733) |
| **Envelope encryption** (una clave de datos por campo + clave maestra) | `src/cifrado.py`                     | Rotar claves sin re-cifrar todos los datos                                   |
| Contexto autenticado (AAD)                                             | `cifrar_campo(..., contexto)`        | Un cifrado copiado a otro registro no descifra                               |
| **Índice ciego** (HMAC-SHA256)                                         | `indice_ciego()`                     | ESC-VEN-05: detectar un DNI ya registrado sin descifrar                      |
| Control de acceso por rol al descifrar                                 | `src/main.py`                        | Solo `verificador` ve el DNI, solo `pagos` ve la cuenta                      |
| Detección de alteración                                                | Etiqueta de autenticación de AES-GCM | Un dato modificado en la base no se acepta                                   |
| Rotación de claves                                                     | `src/rotar_claves.py`                | Cambiar la clave maestra si se compromete                                    |

**Lo que no se cifra en Qhatu, y por qué:** las contraseñas llevan _hash_ (Argon2/bcrypt), no cifrado, porque nunca deben poder recuperarse. Los datos de tarjeta no pasan por Qhatu (solo se guarda un token de la pasarela de pagos).

## Requisitos

- **Python 3.10 o superior** (`python --version`).
- **pip** (viene con Python).
- Un navegador moderno (Chrome, Edge, Firefox) para la demo visual.
- No necesita Docker, base de datos externa ni conexión a internet después de instalar las dependencias. Usa SQLite, que ya viene con Python.

Dependencias (se instalan con `requirements.txt`): `fastapi`, `uvicorn`, `cryptography`, `python-dotenv`, `httpx` y `pytest`.

## Instalación

Todos los comandos se ejecutan **dentro de la carpeta del proyecto** (`qhatu-cifrado-demo`).

```bash
# 1. Crear el entorno virtual
python -m venv .venv
```

Activarlo según tu sistema:

| Sistema              | Comando                      |
| -------------------- | ---------------------------- |
| Windows (CMD)        | `.venv\Scripts\activate.bat` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| macOS / Linux        | `source .venv/bin/activate`  |

> En PowerShell, si aparece un error de "ejecución de scripts deshabilitada", usa CMD o ejecuta `Set-ExecutionPolicy -Scope Process RemoteSigned` en esa misma ventana.

```bash
# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Generar las claves de la demo (crea el archivo .env)
python -m src.generar_claves
```

El paso 3 crea un `.env` con claves aleatorias (dos claves maestras `v1` y `v2` y la clave del índice ciego). **Ese archivo nunca debe subirse al repositorio**: ya está en `.gitignore`. Cada persona que clone el repo genera el suyo con ese comando.

Si el `.env` ya existe, el comando no lo sobrescribe. Para generar claves nuevas, borra el `.env` y vuelve a ejecutarlo.

## Cómo usarlo

### A. Demo visual en el navegador (recomendada)

```bash
python ui_demo.py
```

Se abre `http://127.0.0.1:8000/` en tu navegador (si no se abre sola, copia esa dirección). Siempre parte con una base de datos limpia. Para cerrar la demo, presiona `Ctrl+C` en la terminal.

La pantalla tiene tres zonas:

- **Arriba:** la guía de pasos. Cada paso tiene un título, una frase de "Qué decir" y el botón que lo ejecuta.
- **Izquierda, la aplicación:** el formulario de registro, la respuesta de la API y el probador de roles.
- **Derecha, el servidor y la base:** el cifrado animado y las filas tal como están guardadas en disco.

**Controles:** botones del paso, o `←` `→` para cambiar de paso y `Enter` para ejecutarlo. **Reiniciar demo** (arriba a la derecha) deja todo limpio para volver a empezar.

#### Recorrido de los 6 pasos

| Paso                   | Qué hacer                                     | Qué se ve                                                                                                                                                                                                                                                                | Qué concepto muestra                                    |
| ---------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| **1. Registro**        | Pulsa **Registrar vendedor de ejemplo**       | El DNI y la cuenta pasan por 6 etapas: dato en claro, clave de datos (DEK), nonce, AES-256-GCM, DEK envuelta con la clave maestra, guardado. La API responde `201` con los datos enmascarados (`****5678`). Cambia entre **DNI** y **Cuenta bancaria** con las pestañas. | Cifrado en reposo y envelope encryption                 |
| **2. Robo de la base** | Pulsa **Buscar el DNI en la base robada**     | La tabla muestra solo texto ilegible. La búsqueda de `12345678` da **0 coincidencias**. El nombre sí aparece porque es público y no se cifra.                                                                                                                            | Qué obtiene un atacante con una copia de la base        |
| **3. Roles**           | Pulsa **Probar verificador, soporte y pagos** | `verificador` ve el DNI (`200`), `soporte` recibe `403`, `pagos` ve la cuenta (`200`). Son llamadas reales a la API.                                                                                                                                                     | Control de acceso antes de descifrar                    |
| **4. Suplantación**    | Pulsa **Registrar un suplantador**            | La API responde `409`. Se muestran dos índices ciegos **idénticos**: el DNI duplicado se detectó sin descifrar nada.                                                                                                                                                     | Índice ciego, escenario ESC-VEN-05                      |
| **5. Alteración**      | Pulsa **Alterar un bit y leer**               | La fila se marca como **DATO ALTERADO** y al leerla la API responde `500`: se niega a devolver un dato que no es el original. Pulsa **Restaurar el dato** para dejarlo bien.                                                                                             | Integridad: la etiqueta de GCM detecta cualquier cambio |
| **6. Rotación**        | Pulsa **Rotar la clave maestra**              | Una tabla antes/después: `kek` y `wdek` **cambian**, `ct` queda **IGUAL** (el dato no se volvió a cifrar). Con solo la clave v1 ya no se descifra; con solo v2 sí.                                                                                                       | Rotación de claves sin re-cifrar los datos              |

También puedes usar la página libremente: escribe otros datos en el formulario (DNI de 8 dígitos), registra más vendedores, o prueba los botones de roles en cualquier momento.

> Los valores del paso 1 (clave de datos recortada, nonce, etiqueta de integridad) son los reales de ese registro. La clave de datos se muestra truncada a propósito: la completa nunca sale del servidor.

### B. Demo en consola

```bash
python demo.py          # con pausas: presiona Enter para avanzar cada paso
python demo.py --auto   # el mismo recorrido sin pausas
```

Hace lo mismo que la demo visual, pero imprimiendo en la terminal. Es útil como respaldo o para grabar un video.

### C. API con Swagger

```bash
python -m uvicorn src.main:app
```

Abre `http://127.0.0.1:8000/docs`. Esta forma arranca solo la API (sin la página de la demo) y conserva los datos entre ejecuciones en `qhatu_demo.db`.

| Método y ruta                 | Qué hace                                                                                  | Permiso (header `X-Rol`) |
| ----------------------------- | ----------------------------------------------------------------------------------------- | ------------------------ |
| `POST /vendedores`            | Registra un vendedor (nombre, `dni` de 8 dígitos, `cuenta_bancaria`) y cifra DNI y cuenta | Ninguno                  |
| `GET /vendedores/{id}`        | Datos públicos (id, nombre, estado)                                                       | Ninguno                  |
| `GET /vendedores/{id}/dni`    | Devuelve el DNI descifrado                                                                | `verificador` o `admin`  |
| `GET /vendedores/{id}/cuenta` | Devuelve la cuenta descifrada                                                             | `pagos` o `admin`        |

En Swagger, abre un endpoint, pulsa **Try it out**, escribe el header `X-Rol` (por ejemplo `verificador`) y pulsa **Execute**. Con cualquier otro valor (por ejemplo `soporte`) verás el `403`.

Respuestas posibles: `201` creado · `403` rol sin permiso · `404` vendedor no encontrado · `409` DNI ya registrado (pasa a revisión manual) · `422` datos inválidos · `500` dato alterado o clave incorrecta.

### D. Pruebas automáticas

```bash
python -m pytest
```

Ejecuta 22 pruebas (cifrado, API y endpoints de la demo visual). Usan claves de prueba propias y una base temporal: no tocan tu `.env` ni tus datos.

### E. Rotar la clave maestra a mano

Sirve para la API del punto C (la demo visual ya trae el botón del paso 6):

```bash
python -m src.rotar_claves --a v2
```

Esto vuelve a envolver las claves de datos de todos los vendedores con la clave `v2`, en una sola transacción. Después **cambia `QHATU_ACTIVE_KEK_ID=v2` en tu `.env`** para que los registros nuevos usen la clave nueva, y reinicia la API.

## Cómo funciona el cifrado

```
Dato en claro  ──AES-256-GCM(DEK, nonce, contexto)──▶  dato cifrado + etiqueta
                         ▲
        DEK (clave de datos, aleatoria, una por campo)
                         │
        se guarda ENVUELTA con la KEK (clave maestra, fuera de la base)

Lo que se guarda en la base:  { kek, wdek, n, ct }
   kek  = qué clave maestra envolvió la DEK (v1, v2…)
   wdek = la DEK, cifrada con la KEK
   n    = nonce (aleatorio, nunca se repite)
   ct   = dato cifrado + etiqueta de integridad
```

- **Una DEK distinta por campo:** si una clave se filtra, solo compromete ese dato.
- **Contexto (AAD):** el cifrado queda atado a `vendedor:<id>:<campo>`. Si alguien copia el cifrado del DNI de un vendedor a otro, no descifra.
- **Etiqueta de integridad:** AES-GCM detecta cualquier modificación del dato cifrado.
- **Rotación:** al cambiar la clave maestra solo se re-envuelve la DEK; el dato cifrado (`ct`) no se toca, por eso rotar es rápido aunque haya millones de registros.
- **Índice ciego:** para detectar un DNI repetido sin descifrar, se guarda un HMAC-SHA256 del DNI con una clave propia (distinta a las de cifrado). Dos DNI iguales dan el mismo índice, y el índice no permite recuperar el DNI.

## Variables de entorno

Se leen del archivo `.env` (lo crea `python -m src.generar_claves`).

| Variable                       | Qué es                                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------------------------ |
| `QHATU_ACTIVE_KEK_ID`          | Clave maestra que usan los registros nuevos (`v1` o `v2`)                                        |
| `QHATU_KEK_V1`, `QHATU_KEK_V2` | Claves maestras de 256 bits en base64. Se pueden agregar más (`QHATU_KEK_V3`…)                   |
| `QHATU_BLIND_INDEX_KEY`        | Clave del índice ciego (256 bits en base64)                                                      |
| `QHATU_DB_PATH`                | Ruta del archivo SQLite (por defecto `qhatu_demo.db`)                                            |
| `QHATU_DEMO_UI`                | `1` activa los endpoints de la demo visual. Lo pone `ui_demo.py`; no hace falta definirla a mano |

## Estructura del proyecto

```
qhatu-cifrado-demo/
├── ui_demo.py             <- lanzador de la demo visual
├── demo.py                <- recorrido de 6 pasos en consola
├── requirements.txt       <- dependencias
├── pytest.ini             <- configuración de las pruebas
├── static/
│   └── index.html         <- página de la demo visual
├── src/
│   ├── cifrado.py         <- módulo reutilizable: es lo que se integra al proyecto final
│   ├── vendedores.py      <- registro de vendedores (lo usan la API y la demo visual)
│   ├── main.py            <- API de ejemplo (FastAPI)
│   ├── db.py              <- acceso mínimo a SQLite
│   ├── rotar_claves.py    <- rotación de la clave maestra
│   ├── generar_claves.py  <- crea el .env con claves aleatorias
│   └── ui.py              <- endpoints de apoyo de la demo visual (solo con QHATU_DEMO_UI=1)
└── tests/                 <- pruebas de cifrado, API y demo visual
```

Los endpoints de `src/ui.py` incluyen operaciones como "alterar un dato en la base", que **no deben existir en una API real**. Por eso solo se cargan cuando se arranca con `ui_demo.py`; `uvicorn src.main:app` no los expone.

## Cómo integrarlo al proyecto de Qhatu

1. Copiar `src/cifrado.py` al módulo que lo necesite (Vendedores, Pagos). No depende de FastAPI ni de la base de datos.
2. En cada escritura: `cifrar_campo(keyring, valor, f"<entidad>:<id>:<campo>")` y guardar el resultado en una columna de texto. Si se necesita buscar o detectar duplicados por ese campo, guardar también `indice_ciego(keyring, valor)` con índice único.
3. En cada lectura: verificar el rol **antes** de llamar a `descifrar_campo`.
4. En producción, las claves no van en un `.env`. Hay dos caminos: (a) leerlas de un gestor de secretos del proveedor cloud al iniciar, y entonces solo cambia `Keyring.desde_entorno()`; o (b) dejar la clave maestra dentro de un KMS (AWS KMS, Azure Key Vault, GCP KMS), y entonces cambian `Keyring.desde_entorno()` y las funciones `_envolver` / `_desenvolver`, que pasan a llamar al KMS. En ambos casos el resto del código no cambia.

## Problemas frecuentes

| Problema                                                                      | Causa y solución                                                                                                                                                |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Falta la variable ... Ejecuta: python -m src.generar_claves`                 | No existe el `.env`. Ejecuta `python -m src.generar_claves`                                                                                                     |
| `.env ya existe, no se sobrescribe`                                           | Es lo esperado. Para claves nuevas, borra el `.env` y vuelve a ejecutar el comando                                                                              |
| `ModuleNotFoundError: No module named 'src'`                                  | Estás fuera de la carpeta del proyecto. Entra a `qhatu-cifrado-demo` y vuelve a ejecutar                                                                        |
| `ModuleNotFoundError: fastapi` (u otro paquete)                               | El entorno virtual no está activado o faltan dependencias. Actívalo y ejecuta `pip install -r requirements.txt`                                                 |
| `Address already in use` / el puerto 8000 está ocupado                        | Hay otra demo o servidor abierto. Ciérralo (`Ctrl+C`) o cierra la otra terminal                                                                                 |
| `python` no se reconoce (Windows)                                             | Prueba con `py` en lugar de `python`, o reinstala Python marcando "Add to PATH"                                                                                 |
| Error `500` "clave incorrecta o dato alterado" en la API al leer datos viejos | Cambiaste las claves del `.env` y la base `qhatu_demo.db` tiene datos cifrados con las anteriores. Borra `qhatu_demo.db` (o usa `ui_demo.py`, que parte limpia) |
| La página abre pero los botones no responden                                  | Abriste el HTML directo desde el explorador de archivos. Debe abrirse desde `http://127.0.0.1:8000/` con `ui_demo.py` corriendo                                 |

## Decisiones de diseño y limitaciones

**Errores comunes que este código evita**

- **Reutilizar el nonce** con la misma clave: aquí cada cifrado usa un nonce aleatorio nuevo y su propia DEK.
- **Cifrado sin autenticación** (por ejemplo el modo ECB): GCM detecta cualquier alteración.
- **Claves en el repositorio:** `.env` está en `.gitignore`; solo se sube el código.
- **Usar la misma clave para cifrar y para el índice:** el índice ciego usa una clave propia.

**Limitaciones**

- El rol se simula con el header `X-Rol`. En el proyecto real debe salir de un token firmado (JWT) validado.
- El índice ciego revela cuáles registros tienen el mismo valor (es su función). Conviene usarlo solo en campos donde eso sea aceptable, como el DNI aquí.
- Las claves de la demo viven en variables de entorno; un KMS ofrece auditoría y custodia que este ejemplo no tiene.
- Cifrar en la aplicación protege ante el robo de la base de datos, pero no ante un atacante que ya controle el servidor de aplicaciones con acceso a las claves.
- La verificación del titular contra RENIEC/SUNAT (escenario ESC-VEN-05 completo) está fuera del alcance de esta demo; aquí solo se muestra la detección de DNI duplicado.
