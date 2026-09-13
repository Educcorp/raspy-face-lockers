# Panel Web — Smart Locker System

Aplicación web (Flask) para administrar usuarios, catálogos, lockers e
historial de accesos del Smart Locker System **desde un navegador**, sin
depender del panel de escritorio ni de estar frente a la Raspberry Pi.

## Qué SÍ hace y qué NO hace

- Administra: usuarios, tipos de usuario, unidades académicas, áreas,
  lockers, asignaciones, historial de accesos, **y captura de rostro**.
- El **registro** del rostro (capturar los embeddings de un usuario) se hace
  desde aquí, usando la cámara del navegador del equipo del administrador
  (`webapp/face_processing.py` + `webapp/blueprints/face_bp.py`).
- La **autenticación** (comparar un rostro en vivo contra los ya
  registrados para abrir un locker) sigue siendo responsabilidad exclusiva
  del software que corre en la Raspberry Pi (`ui/`, `core/`, `services/` en
  la raíz del repo, bajo RaspiOS) — eso no se tocó.
- Para que ambos lados generen embeddings comparables, `webapp/face_processing.py`
  reutiliza directamente las clases `FaceDetector`/`FaceEmbeddingExtractor` de
  `core/face_recognition.py` (mismos modelos dlib: `shape_predictor_68_face_landmarks`
  + `dlib_face_recognition_resnet_model_v1`, embeddings 128-dim).
- Un usuario creado desde `/usuarios/nuevo` queda **pendiente de registro
  facial** (sin filas en `encoding`) hasta que un administrador le captura
  el rostro desde `/usuarios/<id>/rostro`.

## Arquitectura

Este panel y el software de la Raspberry Pi comparten **la misma base de
datos remota** (PostgreSQL). El Pi deja de usar su archivo SQLite local
(`database/migrations/raspi-face-lockers.db`) y en su lugar apunta, vía red,
a esta misma base de datos — ver `webapp/schema.sql` para el esquema
equivalente en Postgres del `database/migrations/init_db.sql` original.

No hay una API intermedia: tanto el Pi como este panel hablan directo con
la base de datos remota.

## Configuración local

```bash
cd webapp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env con tu cadena de conexión de PostgreSQL real
```

## Primer arranque (crear esquema + admin)

Desde la raíz del repositorio (para que `utils.validators` sea importable):

```bash
export FLASK_APP=webapp.app:create_app
flask init-db          # aplica webapp/schema.sql en la BD remota
flask create-admin      # crea el primer usuario Superadmin del panel
```

## Correr en desarrollo

```bash
flask run --debug
```

## Desplegar en producción

```bash
gunicorn -w 2 -b 0.0.0.0:8000 webapp.wsgi:app
```

Cualquier host que dé un PostgreSQL administrado y permita correr un
proceso Python (Railway, Render, Fly.io, un VPS, etc.) sirve. Variables de
entorno requeridas: `DATABASE_URL`, `SECRET_KEY`.

## Migrar el Pi para usar la base de datos remota

El código en `database/connection.py` usa `sqlite3` directamente. Para que
el Pi comparta la base remota con este panel, su capa de datos debe
cambiar de `sqlite3` a `psycopg2` apuntando al mismo `DATABASE_URL` — es un
cambio aislado a `database/connection.py` y no debería requerir tocar
`services/*.py` si se mantiene la misma interfaz (`fetch_all`, `fetch_one`,
`execute`, `db_session`). Ese trabajo queda fuera de este panel web y debe
hacerse (y probarse) directamente sobre RaspiOS.

## Flujo de alta de usuario (100% web)

1. Un administrador crea al usuario desde `/usuarios/nuevo` (datos + PIN).
   Queda marcado como "Pendiente" en el dashboard y en la lista de usuarios.
2. Desde la lista de usuarios (o el propio formulario de edición), entra a
   "Registrar rostro" (`/usuarios/<id>/rostro`) y captura 4 poses con la
   cámara del navegador: frontal, derecha, izquierda y arriba — al estilo
   del enrollment de Face ID.
3. Cada pose se valida en el servidor (detección + extracción del embedding
   con dlib) y se compara contra los rostros ya registrados de otros
   usuarios para evitar duplicados, antes de guardarse.
4. Al completar las 4 poses y presionar "Guardar rostro", se reemplazan los
   encodings del usuario en una sola transacción y el badge cambia a
   "Registrado" automáticamente.
5. La app del Pi (`ui/admin/register_user.py`) sigue existiendo tal cual —
   no se tocó — pero ya no es la vía esperada para dar de alta rostros
   nuevos; el flujo oficial es el de este panel.

## Nota sobre el Dockerfile

`dlib` no tiene wheel precompilado para este entorno, así que el Dockerfile
usa un build multi-stage: una etapa `builder` con `cmake`/`build-essential`
compila las dependencias en un venv, y la imagen final (`python:3.12-slim`)
solo copia ese venv ya compilado — así el build tarda más (~5-10 min por
compilar dlib) pero la imagen final se mantiene liviana. Los modelos dlib
se descargan durante el build (`RUN python download_models.py`).
