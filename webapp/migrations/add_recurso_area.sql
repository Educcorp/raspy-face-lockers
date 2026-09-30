-- Migración: asociar cada recurso a una unidad académica y un área (mismo
-- catálogo que ya usan los lockers, area_lockers.idUnidadAcademica).
-- Fecha: 2026-09-30
-- Nullable a propósito: los recursos creados antes de esta migración (p. ej.
-- "Taladro") no tienen unidad/área todavía. El formulario de alta/edición del
-- panel web SÍ las exige de aquí en adelante, y valida que el área elegida
-- realmente pertenezca a la unidad elegida (ver catalog_service.area_belongs_to_unidad
-- y webapp/blueprints/resources_bp.py) — igual que ya se validaba para lockers.
-- Idempotente: se puede ejecutar más de una vez.

ALTER TABLE recursos ADD COLUMN IF NOT EXISTS idUnidadAcademica INTEGER;
ALTER TABLE recursos ADD COLUMN IF NOT EXISTS idArea INTEGER;

DO $$
BEGIN
    ALTER TABLE recursos
        ADD CONSTRAINT fk_recurso_unidad
        FOREIGN KEY (idUnidadAcademica) REFERENCES unidad_academica (idUnidadAcademica)
        ON UPDATE CASCADE ON DELETE RESTRICT;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END
$$;

DO $$
BEGIN
    ALTER TABLE recursos
        ADD CONSTRAINT fk_recurso_area
        FOREIGN KEY (idArea) REFERENCES area_lockers (idArea)
        ON UPDATE CASCADE ON DELETE RESTRICT;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END
$$;

CREATE INDEX IF NOT EXISTS idx_recursos_unidad ON recursos (idUnidadAcademica);
CREATE INDEX IF NOT EXISTS idx_recursos_area ON recursos (idArea);
