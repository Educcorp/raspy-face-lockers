# Smart Locker — contexto para Claude

Sistema de casilleros (lockers) con acceso por reconocimiento facial y PIN de
respaldo, para una escuela. Dos frontends comparten **una sola base de datos
lógica** (Postgres en Railway):

- **`webapp/`** — panel de administración web (Flask), desplegado en Railway.
  Registra usuarios, captura rostros, gestiona catálogos y asignaciones.
- **`ui/` + `core/` + `services/` + `database/` + `auth/`** — la app de la
  Raspberry Pi: kiosco físico (`main.py --mode locker`, CustomTkinter,
  480×800 portrait) + panel de administración local (`--mode admin`).
  Controla la cámara (picamera2), el reconocimiento facial (dlib) y los
  relés GPIO de los lockers.

Ambos lados leen/escriben la misma Postgres (`webapp/schema.sql` es el
esquema fuente). El objetivo explícito del proyecto es que la Pi deje de ser
un sistema local aislado y sea un cliente más de esa base compartida, con una
interfaz que replique el layout visual del panel web.

## Arranque

```bash
python main.py --mode locker   # kiosco físico (pantalla táctil de la Pi)
python main.py --mode admin    # panel de administración local
```

La app corre indistintamente desde `venv/` o el Python del sistema — ver
"dlib/onnxruntime fuera del venv" más abajo, por qué eso ya no importa.

`webapp/` se despliega aparte (Railway); no lo levanta `main.py`.

## Piezas que hay que conocer antes de tocar código

### 1. Postgres pliega los identificadores a minúsculas
`webapp/schema.sql` define columnas en camelCase (`idUsuario`,
`nombreTipoUsuario`, …) **sin comillas**, así que Postgres las guarda en
minúsculas reales (`idusuario`). Todo el código Python lee resultados por
clave camelCase exacta. La regla en cada `SELECT` de este repo:
```sql
SELECT idUsuario AS "idUsuario" FROM usuarios   -- alias citado preserva el case
```
`SELECT *` / `tabla.*` está prohibido en la práctica: hay que expandir a
columnas explícitas con su alias citado. Si un campo del UI aparece vacío
sin error, la primera sospecha es un alias faltante.

### 2. `database/connection.py` — pool de conexiones, no una por consulta
Contra el proxy TCP de Railway, abrir una conexión cuesta ~918ms (medido en
esta Pi) frente a ~141ms de la consulta en sí. La capa de datos usa
`psycopg2.pool.ThreadedConnectionPool` (no una conexión nueva por llamada).
API pública sin cambios: `fetch_all`, `fetch_one`, `execute`,
`execute_returning`, `db_session()` (context manager transaccional).

- Las consultas sueltas (`fetch_all`/`fetch_one`/`execute`) corren en
  **autocommit** — evita el COMMIT+ROLLBACK-de-cortesía que psycopg2 hace al
  devolver al pool una conexión con transacción abierta (ahorra ~2 viajes de
  red por consulta).
- `db_session()` sigue siendo transaccional (COMMIT al salir del bloque,
  ROLLBACK si algo falla) — verificado que un fallo a mitad de transacción
  revierte todo.
- **Un semáforo limita a 2 las operaciones simultáneas contra la BD.** No es
  arbitrario: se midió que este proxy de Railway *degrada* con más
  concurrencia (36 consultas / 6 hilos: 8.4 ops/s con límite 2, vs 1.38 ops/s
  sin límite). Es reentrante por hilo (una consulta anidada dentro de un
  `db_session()` no se bloquea a sí misma).
- `main.py` llama `database.connection.warmup()` en un hilo de fondo al
  arrancar, para que el pool ya esté caliente cuando la UI lo necesite.

### 3. Caché de embeddings + registro de accesos asíncrono
`services/user_service.get_active_face_encodings()` cachea en memoria (TTL
60s) — antes el bucle de reconocimiento del kiosko volvía a descargar todos
los embeddings en **cada intento** (~1.4s de red, congelando la vista previa
de la cámara). Las escrituras (alta, re-registro, cambio de estado, borrado)
invalidan el caché al instante; `force_refresh=True` se usa al verificar
duplicados en el registro, para no dejar pasar un rostro por dato rancio.

`services/access_log_service.register_access()` ya no escribe en línea:
encola y un hilo trabajador único hace el INSERT en segundo plano (antes
bloqueaba el hilo de la cámara ~1.5s por cada intento, con o sin match).

### 4. dlib/onnxruntime instalados fuera del venv — rescate de `sys.path`
En esta Pi, `dlib` vive en `~/.local/lib/python3.13/site-packages` (pip
`--user`) y `onnxruntime`/`picamera2` en `dist-packages` del sistema (apt,
por PEP 668). Un venv sin `--system-site-packages` no ve ninguna de las tres.

`core/face_recognition.py` intenta el import normal y, si falla, agrega esas
rutas a `sys.path` y reintenta (mismo patrón que ya existía para
`picamera2`). **Esto es crítico**: si dlib no carga, el extractor de
embeddings cae silenciosamente a un fallback (`grayscale 16x8`) que nunca
puede compararse con los rostros ya guardados (todos `dlib_resnet_v1`), y el
sistema niega el acceso a todo el mundo sin ningún error visible — el log de
arranque decía `Embeddings dlib: OK` incluso en modo fallback porque
`is_ready` es `True` en ambos casos. **Ya se corrigió eso también**: el log
ahora distingue los tres estados (`dlib resnet v1 (OK)` / `MODO FALLBACK` /
`NO DISPONIBLE`) — si alguna vez vuelve a aparecer "MODO FALLBACK", ese es el
punto de partida.

### 5. Anti-spoofing: DESHABILITADO (`config.py` → `ANTI_SPOOF_CONFIG["enabled"] = False`)
Los `.onnx` de `assets/models/` (`2.7_80x80_MiniFASNetV2.onnx`,
`4_0_0_80x80_MiniFASNetV1SE.onnx`) están mal convertidos: se comportan como
funciones **prácticamente constantes**. Probado con 12 entradas radicalmente
distintas (negro, blanco, ruido, tablero de ajedrez, 8 parches de fotos
reales) — los logits varían menos de 0.6 y la clase "falso" gana 12/12 veces,
con un score fijo de ~0.95. Con `required: True` (fail-closed) esto negaba
**todo** acceso sin llegar nunca a comparar rostros.

Para reactivarlo: re-convertir los `.pth` originales con
`tools/antispoof/convert_to_onnx.py` (requiere `torch`, no instalado aquí) y
**verificar que la salida realmente reacciona a la entrada** antes de confiar
en ella — esa comprobación es la que faltó la primera vez.
⚠️ Con el anti-spoof apagado, una foto impresa o una pantalla podría abrir un
locker. Aceptado temporalmente para poder seguir depurando el reconocimiento
real; no es el estado deseado para producción.

### 6. Umbral de distancia facial — un solo número, compartido a propósito
`core/face_recognition.py::MIN_FACE_SIZE_RATIO = 0.12` (~1 metro, calculado
por geometría de la Pi Camera v2/3 a 62° HFOV — no medido aún con esta
cámara real). Lo usan **tres sitios**, todos a propósito con el mismo valor,
para que la distancia de interacción sea consistente en toda la experiencia:
- `ui/locker_screen/standby_screen.py` — dispara la transición a
  `ScanningScreen` cuando alguien se acerca (3s continuos, solo detecciones
  HOG — el fallback Haar da falsos positivos sobre paredes/objetos y aquí
  activaría el sistema sin que hubiera nadie).
- `ui/locker_screen/scanning_screen.py` — compuerta de autenticación real +
  el hint "acércate más"/"aléjate un poco" (`scan.hint_closer` /
  `scan.hint_farther`, ya existía, se muestra solo mientras dura el video).
- `ui/admin/register_user.py` — compuerta de calidad al capturar poses.

**No cambiar este ratio en un solo sitio** sin pensar en los otros dos — es
intencional que compartan valor.

### 7. `_refine_rect` en la extracción de embeddings
`FaceEmbeddingExtractor.get_embedding()` no aplica CLAHE (la ecualización
adaptativa desestabilizaba el embedding entre frames con encuadres
ligeramente distintos) y re-detecta la caja del rostro a resolución nativa
con HOG (`_refine_rect`) en vez de reusar la caja escalada desde la
detección a 400px — esa caja traía temblor de cuantización que se
amplificaba ~3px por cada píxel a 400px y degradaba los 68 landmarks. El
`upsample` de ese refinado es condicional al tamaño de la cara (evita pagar
4x el costo en caras ya grandes).

### 8. GPIO / hardware físico
- `core/gpio_controller.py` — 4 relés (HW-316, activo-bajo) para los
  solenoides de los lockers 1-4, pines BCM 17/27/22/23.
  `GPIO_CONFIG["locker_open_seconds"] = 2.5` es cuánto tiempo el relé queda
  energizado (ventana real para que la persona jale la puerta) — pendiente
  de subir a ~10s a pedido del usuario (2026-09-23), aún no aplicado.
- `core/door_switch_controller.py` + `DOOR_SWITCH_CONFIG` — sensores de
  puerta (KW11-3Z) en los mismos 4 lockers, pines BCM 5/6/12/13. Se sondean
  para saber si la puerta sigue abierta y avisar (`DOOR_ALERT_DELAY_S=10s`
  antes de alertar, en `scanning_screen.py`).
- `core/tool_gpio_controller.py` — relé aparte (BCM24) para un taladro/toma
  controlada, no lockers; llegó por otra rama (`ferrrr`), no tocado en estas
  sesiones.
- **`ui/admin/locker_assignment.py`** tiene la sección "Abrir locker
  manualmente". El 2026-09-23 se intentó restaurar ahí un mensaje de estado
  ("Locker N abierto") que existía antes de un refactor y se había perdido
  — **el usuario reportó que esos cambios rompieron los sensores y los
  descartó** (revertidos, no están en el árbol). Si se vuelve a tocar este
  archivo, ir con cuidado especial y probar con hardware real antes de
  darlo por bueno.

## Convenciones del repo

- **Case-fold de Postgres** (punto 1) — la regla más fácil de romper sin
  darse cuenta.
- Estilo de indentación **mixto por archivo**: la mayoría usa espacios, pero
  `ui/admin/locker_assignment.py` usa TABS. Revisar antes de editar.
- i18n: `ui/i18n.py`, diccionario plano `STRINGS[key][lang]`, con
  interpolación `t("key", n=5)`. ES/EN. No crear textos hardcodeados en las
  pantallas del kiosko/admin de la Pi.
- El layout de `ui/` debe replicar visualmente `webapp/templates/` +
  `webapp/static/css/style.css` (paleta/tipografía centralizada en
  `ui/theme.py`, tokens espejo de las variables CSS del web).
- No hay pool/caché equivalentes en `webapp/` — esas optimizaciones son
  solo del lado Pi (`database/connection.py` en la raíz, no
  `webapp/db.py`).
- Verificaciones de cambios en `core/face_recognition.py` o en los flujos de
  cámara: preferir pruebas con `unittest.mock` + un `customtkinter.CTk()`
  oculto (`root.withdraw()`) manejado con `root.mainloop()` real (no
  `root.update()` en loop manual — eso rompe el cross-thread `self.after()`
  con `RuntimeError: main thread is not in main loop`) antes de pedir al
  usuario que pruebe con hardware real.

## Historial de cambios relevantes (sesiones con Claude Code en esta Pi)

Orden cronológico, resumido — el detalle completo vive en los commits.

1. **Migración SQLite → Postgres remota** (`database/connection.py`
   reescrito, todo el SQL de `services/*.py` y `ui/admin/*.py` traducido con
   alias citados, triggers de Postgres reemplazando los `strftime()`
   manuales). Verificado en vivo contra Railway.
2. **Rediseño visual completo de `ui/`** para replicar el layout del panel
   web: `ui/theme.py` y `ui/components.py` nuevos, paleta terracota/crema,
   `NavDrawer` lateral, pantallas de escaneo/PIN/standby rediseñadas.
3. **Depuración de "acceso denegado" del reconocimiento facial** — cadena de
   causas encontradas y corregidas una por una: FK al re-registrar desde la
   Pi (id de usuario obsoleto tras borrar), extracción de embeddings
   inestable (CLAHE + caja mal alineada, ver punto 7), anti-spoof fail-closed
   con modelos rotos (ver punto 5), y finalmente dlib cayendo a fallback por
   no verse desde el venv (ver punto 4) — esta última era la causa real de
   que ningún rostro de la web se reconociera en la Pi.
4. **Optimización de rendimiento** (queja: "el sistema está muy lento") —
   pool de conexiones + límite de concurrencia (punto 2), caché de
   embeddings + registro de accesos asíncrono (punto 3), bucle de detección
   de cámara reordenado para ecualizar *después* de reducir resolución en
   vez de antes (ahorra procesar 39ms sobre píxeles que se iban a descartar).
5. **Detección de "acercarse" al standby** — se probaron dos diseños: uno
   con textos de estado ("Te vemos, sigue acercándote" / "Perfecto, quédate
   quieto") que el usuario pidió revertir por no gustarle, y el diseño final
   (punto 6): activación silenciosa "de la nada" como el original, solo
   con el umbral recalibrado a ~1m y filtrado a detecciones HOG.
6. **Instalación de Claude Code CLI nativo** en esta Pi
   (`~/.local/bin/claude`, vía `curl -fsSL https://claude.ai/install.sh |
   bash`) — agregado `~/.local/bin` al PATH en `~/.bashrc`.

## Pendiente / próximos pasos conocidos

- Subir `GPIO_CONFIG["locker_open_seconds"]` de 2.5 a ~10s (pedido
  2026-09-23, no aplicado aún).
- Re-convertir y validar los modelos de anti-spoofing (punto 5) antes de
  reactivarlos — el sistema hoy no tiene protección contra fotos/pantallas.
- Calibrar `MIN_FACE_SIZE_RATIO` con una medición real en esta cámara (hoy
  es un cálculo geométrico, dos veces corregido a mano por estar mal la
  primera vez).
- Revisar el orden de color RGB/BGR entre lo que entrega `picamera2` y lo
  que espera `get_embedding()` — quedó señalado como sospechoso pendiente,
  nunca descartado con una prueba en vivo.
- `ui/admin/locker_assignment.py`: la restauración del mensaje "Locker N
  abierto" quedó revertida por romper los sensores — si se retoma, probar
  con hardware real, no solo con mocks.
- `run.sh` estaba roto por un `.venv/` vacío heredado — no verificado si
  sigue así.
- Rotar la contraseña de Postgres de Railway (apareció en texto plano en
  una conversación anterior).
