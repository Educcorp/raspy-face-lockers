-- Migración: apertura remota de lockers desde el panel web
-- Fecha: 2026-09-23
-- La web (Railway) no puede activar los relés GPIO de la Raspberry Pi. En su lugar
-- escribe comandos en `comandos_locker`; la Pi los consulta, los ejecuta y publica
-- el estado de las puertas en `estado_puerta` (que además sirve de "latido": si no
-- se actualiza, la web sabe que la Pi está desconectada).
-- Idempotente: se puede ejecutar más de una vez.

CREATE TABLE IF NOT EXISTS comandos_locker (
    idComando SERIAL PRIMARY KEY,
    idLocker INTEGER NOT NULL,
    accion TEXT NOT NULL DEFAULT 'abrir' CHECK (accion IN ('abrir')),
    estado TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'ejecutando', 'completado', 'error', 'expirado')),
    solicitadoPor INTEGER,
    fechaHoraSolicitud TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraEjecucion TIMESTAMPTZ,
    detalle TEXT,
    CONSTRAINT fk_comando_locker
        FOREIGN KEY (idLocker) REFERENCES lockers (idLocker)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_comando_usuario
        FOREIGN KEY (solicitadoPor) REFERENCES usuarios (idUsuario)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_comandos_estado ON comandos_locker (estado, fechaHoraSolicitud);
CREATE INDEX IF NOT EXISTS idx_comandos_locker ON comandos_locker (idLocker, fechaHoraSolicitud);

CREATE TABLE IF NOT EXISTS estado_puerta (
    idLocker INTEGER PRIMARY KEY,
    -- TRUE = puerta cerrada, FALSE = abierta, NULL = sin lectura del sensor
    cerrada BOOLEAN,
    fechaHoraAct TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_estado_puerta_locker
        FOREIGN KEY (idLocker) REFERENCES lockers (idLocker)
        ON UPDATE CASCADE ON DELETE CASCADE
);
