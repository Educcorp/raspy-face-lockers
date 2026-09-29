-- Migración: catálogo real de recursos compartidos + autorizaciones por usuario
-- Fecha: 2026-09-29
-- Antes "Recursos" era una vista de demostración con dos recursos fijos en código
-- (resources_bp.py::SHARED_RESOURCES) y el estado activo/inactivo solo vivía en el
-- localStorage del navegador. Ahora los recursos son un catálogo real, y cada uno
-- puede tener varios usuarios autorizados a activarlo (a diferencia de los lockers,
-- que tienen una asignación 1-a-1 por locker).
-- Idempotente: se puede ejecutar más de una vez.

CREATE TABLE IF NOT EXISTS recursos (
    idRecurso SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL CHECK (length(nombre) <= 60),
    descripcion TEXT CHECK (length(descripcion) <= 300),
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    fechaHoraReg TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraAct TIMESTAMPTZ NOT NULL DEFAULT now(),
    creadoPor INTEGER NOT NULL,
    modificadoPor INTEGER,
    CONSTRAINT uq_recurso_nombre UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS recurso_autorizados (
    idRecursoAutorizado SERIAL PRIMARY KEY,
    idRecurso INTEGER NOT NULL,
    idUsuario INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    fechaHoraReg TIMESTAMPTZ NOT NULL DEFAULT now(),
    creadoPor INTEGER NOT NULL,
    modificadoPor INTEGER,
    CONSTRAINT fk_recurso_autorizado_recurso
        FOREIGN KEY (idRecurso) REFERENCES recursos (idRecurso)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_recurso_autorizado_usuario
        FOREIGN KEY (idUsuario) REFERENCES usuarios (idUsuario)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_recurso_autorizado_activo
    ON recurso_autorizados (idRecurso, idUsuario) WHERE estado = 'activo';

CREATE OR REPLACE FUNCTION trg_touch_fecha_hora_act() RETURNS TRIGGER AS $$
BEGIN
    NEW.fechaHoraAct = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_recursos_act ON recursos;
CREATE TRIGGER trg_recursos_act BEFORE UPDATE ON recursos
    FOR EACH ROW EXECUTE FUNCTION trg_touch_fecha_hora_act();
