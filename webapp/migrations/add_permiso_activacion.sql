-- Migración: Agregar campo permisoactivacion a tabla usuarios
-- Fecha: 2026-09-21
-- Descripción: Agrega el campo permisoactivacion para determinar qué recursos
-- puede activar cada usuario (recurso_compartido, locker o ambos)

-- Agregar columna permisoactivacion con valor por defecto 'locker'
ALTER TABLE usuarios
ADD COLUMN IF NOT EXISTS permisoactivacion VARCHAR(20) NOT NULL DEFAULT 'locker';

-- Intentar agregar constraint de verificación (si no existe)
DO $$
BEGIN
    ALTER TABLE usuarios
    ADD CONSTRAINT chk_permiso_activacion CHECK (permisoactivacion IN ('recurso_compartido', 'locker', 'ambos'));
EXCEPTION WHEN duplicate_object THEN
    -- El constraint ya existe, no hacer nada
    NULL;
END
$$;

-- Crear índice para búsquedas por permiso
CREATE INDEX IF NOT EXISTS idx_usuarios_permisoactivacion ON usuarios (permisoactivacion);

-- Comentario de la columna (opcional, documenta el propósito)
COMMENT ON COLUMN usuarios.permisoactivacion IS 'Permisos de activación del usuario: recurso_compartido, locker o ambos';
