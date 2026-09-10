# Panel Web — Smart Locker System

Aplicación web (Flask) para administrar usuarios, catálogos, lockers e
historial de accesos del Smart Locker System **desde un navegador**, sin
depender del panel de escritorio ni de estar frente a la Raspberry Pi.

## Qué SÍ hace y qué NO hace

- Administra: usuarios, tipos de usuario, unidades académicas, áreas,
  lockers, asignaciones y consulta de historial.
- **No** hace captura de cámara, reconocimiento facial ni control de GPIO.
  Eso sigue siendo responsabilidad exclusiva del software que corre en la
  Raspberry Pi (`ui/`, `core/`, `services/` en la raíz del repo), que seguirá
  ejecutándose ahí bajo RaspiOS.
- Un usuario creado desde este panel queda **pendiente de registro facial**
  (sin filas en `encoding`) hasta que un operador lo capture físicamente en
  el kiosco del locker.

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

## Flujo de alta de usuario (panel web + Pi)

1. Un administrador crea al usuario desde `/usuarios/nuevo` (datos + PIN).
   Queda marcado como "pendiente de registro facial" en el dashboard y en
   la lista de usuarios.
2. Se le indica a la persona que se presente físicamente ante el
   dispositivo del locker.
3. En el Pi, un operador usa el flujo existente de captura de rostro
   (hoy en `ui/admin/register_user.py` en la app de escritorio) para
   completar el registro de ese usuario ya existente en la base remota.
4. Una vez capturado el rostro, el badge cambia a "Registrado" en el panel
   web automáticamente (se basa en si existen filas activas en `encoding`).

Nota: el flujo de captura en el Pi actualmente está pensado para alta
conjunta (usuario + rostro en un solo paso). Falta un ajuste puntual ahí
para que también pueda **seleccionar un usuario ya existente y pendiente**
y completarle solo el rostro — no se modificó en este cambio porque es
código exclusivo del dispositivo físico.
