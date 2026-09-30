-- Migración: sesiones de uso de recursos compartidos
-- Fecha: 2026-09-30
-- Hasta ahora "activar un recurso" en el kiosco de la Pi era solo interfaz: no
-- quedaba ningún registro de quién lo estaba usando ni por cuánto tiempo, así
-- que no había forma de mostrar progreso, de dejar "terminar" a mitad de uso,
-- ni de impedir que dos personas reclamaran el mismo recurso a la vez.
-- `recurso_uso` es la sesión real. El candado de concurrencia es el índice
-- único parcial `uq_recurso_uso_activo`: solo puede existir una fila 'en_uso'
-- por recurso, y Postgres lo garantiza de forma atómica sin necesidad de un
-- FOR UPDATE manual (ver services/resource_service.py::claim_session, que
-- inserta con ON CONFLICT DO NOTHING sobre este mismo índice).
-- Depende de: add_recursos.sql (tabla `recursos` ya debe existir).
-- Idempotente: se puede ejecutar más de una vez.

CREATE TABLE IF NOT EXISTS recurso_uso (
    idRecursoUso SERIAL PRIMARY KEY,
    idRecurso INTEGER NOT NULL,
    idUsuario INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'en_uso'
        CHECK (estado IN ('en_uso', 'finalizado', 'expirado')),
    fechaHoraInicio TIMESTAMPTZ NOT NULL DEFAULT now(),
    duracionMinutos INTEGER NOT NULL CHECK (duracionMinutos > 0 AND duracionMinutos <= 180),
    fechaFinPrevista TIMESTAMPTZ NOT NULL,
    fechaFinReal TIMESTAMPTZ,
    -- 'usuario' = presionó "Terminar de usar"; 'sistema' = se cumplió el
    -- tiempo y nadie la cerró a mano (ver resource_session_worker.py).
    finalizadoPor TEXT CHECK (finalizadoPor IN ('usuario', 'sistema') OR finalizadoPor IS NULL),
    CONSTRAINT fk_recurso_uso_recurso
        FOREIGN KEY (idRecurso) REFERENCES recursos (idRecurso)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_recurso_uso_usuario
        FOREIGN KEY (idUsuario) REFERENCES usuarios (idUsuario)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_recurso_uso_activo
    ON recurso_uso (idRecurso) WHERE estado = 'en_uso';

CREATE INDEX IF NOT EXISTS idx_recurso_uso_usuario ON recurso_uso (idUsuario, estado);
CREATE INDEX IF NOT EXISTS idx_recurso_uso_fin_previsto ON recurso_uso (fechaFinPrevista) WHERE estado = 'en_uso';
