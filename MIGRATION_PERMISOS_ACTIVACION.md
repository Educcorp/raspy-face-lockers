# Guía: Aplicar Migración de Permisos de Activación

## Cambios Implementados

Se agregó un nuevo campo **`permisoActivacion`** a la tabla `usuarios` que permite especificar qué recursos puede activar cada usuario.

### Valores permitidos:
- `recurso_compartido`: Solo puede acceder a recursos compartidos
- `locker`: Solo puede acceder a lockers
- `ambos`: Puede acceder a ambos tipos de recursos

## Cómo Aplicar la Migración

### Opción 1: Ejecutar SQL directamente en PostgreSQL

```bash
# Conectarse a la base de datos
psql -U [usuario] -h [host] -d [nombre_bd] -f webapp/migrations/add_permiso_activacion.sql
```

### Opción 2: Ejecutar desde Python en el shell

```bash
cd /home/pame/raspy-face-lockers
source .venv/bin/activate
python3
```

Luego en la consola Python:

```python
from webapp.db import cursor

with cursor() as cur:
    with open('webapp/migrations/add_permiso_activacion.sql', 'r') as f:
        cur.execute(f.read())
```

### Opción 3: Ejecutar desde Flask CLI

```bash
cd /home/pame/raspy-face-lockers
source .venv/bin/activate
python3 -m flask shell
```

Luego:

```python
from webapp.db import cursor

with cursor() as cur:
    with open('webapp/migrations/add_permiso_activacion.sql', 'r') as f:
        cur.execute(f.read())
exit()
```

## Verificación

Después de aplicar la migración, verifica que el campo se haya creado:

```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'usuarios' AND column_name = 'permisoActivacion';
```

Deberías ver:
- `column_name`: permisoActivacion
- `data_type`: text
- `is_nullable`: NO
- `column_default`: 'locker'::text

## Usuarios Existentes

- Todos los usuarios existentes recibirán automáticamente `permisoActivacion = 'locker'`
- El administrador puede cambiar este valor editando cada usuario en el formulario

## Probar en la Interfaz Web

1. Ir a `http://127.0.0.1:5000/usuarios/nuevo`
2. Llenar el formulario
3. Seleccionar "Permisos de activación" (nueva opción en el select)
4. Guardar el usuario
5. Editar un usuario existente y modificar sus permisos
