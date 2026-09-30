-- Migración: distinguir accesos a locker vs. recurso en historial_accesos
-- Fecha: 2026-09-30
-- Hasta ahora historial_accesos solo podía apuntar a un locker (idLockerAsignado).
-- El flujo de "recurso" ni siquiera escribía nada aquí. Se agrega un modelo de
-- "arco exclusivo": una columna discriminadora (tipoAcceso) más una segunda FK
-- nullable (idRecursoUso), paralela a la ya existente idLockerAsignado, con un
-- CHECK que impone que solo una de las dos esté presente por fila. No se toca
-- la FK ni el comportamiento existente de locker.
-- Depende de: add_recurso_uso.sql (tabla `recurso_uso` ya debe existir).
-- Idempotente: se puede ejecutar más de una vez.

ALTER TABLE historial_accesos
    ADD COLUMN IF NOT EXISTS tipoAcceso TEXT NOT NULL DEFAULT 'locker',
    ADD COLUMN IF NOT EXISTS idRecursoUso INTEGER;

DO $$ BEGIN
    ALTER TABLE historial_accesos ADD CONSTRAINT chk_historial_tipo_acceso
        CHECK (tipoAcceso IN ('locker', 'recurso'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE historial_accesos ADD CONSTRAINT chk_historial_tipo_consistente CHECK (
        (tipoAcceso = 'locker'  AND idRecursoUso IS NULL) OR
        (tipoAcceso = 'recurso' AND idLockerAsignado IS NULL)
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE historial_accesos ADD CONSTRAINT fk_historial_recurso_uso
        FOREIGN KEY (idRecursoUso) REFERENCES recurso_uso (idRecursoUso)
        ON UPDATE CASCADE ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Postgres no permite ALTER de un CHECK existente: hay que dropearlo y recrearlo
-- con los 3 motivos nuevos del flujo de recursos.
ALTER TABLE historial_accesos DROP CONSTRAINT IF EXISTS historial_accesos_motivo_check;
ALTER TABLE historial_accesos ADD CONSTRAINT historial_accesos_motivo_check CHECK (
    motivo IN (
        'facial', 'pin', 'sin_asignacion', 'limite_intentos',
        'no_reconocido', 'pin_incorrecto', 'limite_intentos_pin',
        'matricula_incorrecta', 'pin_cancelado',
        'puerta_cerrada', 'puerta_no_cerrada',
        'recurso_en_uso', 'recurso_finalizado', 'recurso_expirado'
    ) OR motivo IS NULL
);

CREATE INDEX IF NOT EXISTS idx_historial_tipo ON historial_accesos (tipoAcceso, fechaHoraAcceso);

-- CREATE OR REPLACE VIEW no permite insertar una columna a mitad de la lista
-- (solo agregar al final) — hay que dropear y recrear.
DROP VIEW IF EXISTS v_historial_detalle;
CREATE VIEW v_historial_detalle AS
SELECT
    h.idAcceso,
    h.tipoAcceso,
    COALESCE(u1.nombre || ' ' || u1.apPaterno, u2.nombre || ' ' || u2.apPaterno) AS nombreCompleto,
    COALESCE(u1.matricula, u2.matricula) AS matricula,
    l.idLocker,
    a.nombreArea,
    r.idRecurso,
    r.nombre AS nombreRecurso,
    h.fechaHoraAcceso,
    h.accesoPermitido,
    h.motivo,
    h.fechaExpiracion
FROM historial_accesos h
LEFT JOIN asignacion_locker al ON h.idLockerAsignado = al.idLockerAsignado
LEFT JOIN usuarios u1 ON al.idUsuario = u1.idUsuario
LEFT JOIN usuarios u2 ON h.idUsuario = u2.idUsuario
LEFT JOIN lockers l ON al.idLocker = l.idLocker
LEFT JOIN area_lockers a ON l.idArea = a.idArea
LEFT JOIN recurso_uso ru ON h.idRecursoUso = ru.idRecursoUso
LEFT JOIN recursos r ON ru.idRecurso = r.idRecurso
ORDER BY h.fechaHoraAcceso DESC;
