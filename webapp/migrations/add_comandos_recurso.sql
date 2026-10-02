-- Migración: activación remota de recursos compartidos desde el panel web
-- Fecha: 2026-10-01
-- Mismo patrón que add_comandos_locker.sql: la web (Railway) no puede tocar el
-- relé de la herramienta, así que encola un comando en `comandos_recurso`; la
-- Raspberry Pi (services/remote_command_service.py) lo reclama, abre la sesión
-- en `recurso_uso` y activa el relé en el puerto BCM que tenga configurado para
-- ese recurso (config.py → TOOL_GPIO_CONFIG["pins"]). El latido de la Pi sigue
-- siendo `estado_puerta`.
-- Idempotente: se puede ejecutar más de una vez.

CREATE TABLE IF NOT EXISTS comandos_recurso (
    idComando SERIAL PRIMARY KEY,
    idRecurso INTEGER NOT NULL,
    accion TEXT NOT NULL CHECK (accion IN ('activar', 'desactivar')),
    -- Solo para 'activar': cuánto dura la sesión (mismo tope que recurso_uso, 3 h).
    duracionSegundos INTEGER CHECK (duracionSegundos > 0 AND duracionSegundos <= 10800),
    estado TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'ejecutando', 'completado', 'error', 'expirado')),
    solicitadoPor INTEGER,
    fechaHoraSolicitud TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraEjecucion TIMESTAMPTZ,
    detalle TEXT,
    CONSTRAINT chk_comando_recurso_duracion CHECK (
        (accion = 'activar' AND duracionSegundos IS NOT NULL) OR accion = 'desactivar'
    ),
    CONSTRAINT fk_comando_recurso
        FOREIGN KEY (idRecurso) REFERENCES recursos (idRecurso)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_comando_recurso_usuario
        FOREIGN KEY (solicitadoPor) REFERENCES usuarios (idUsuario)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_comandos_recurso_estado ON comandos_recurso (estado, fechaHoraSolicitud);
CREATE INDEX IF NOT EXISTS idx_comandos_recurso_recurso ON comandos_recurso (idRecurso, fechaHoraSolicitud);

-- Nuevo motivo de historial: 'remoto' (recurso activado desde el panel web).
ALTER TABLE historial_accesos DROP CONSTRAINT IF EXISTS historial_accesos_motivo_check;
ALTER TABLE historial_accesos ADD CONSTRAINT historial_accesos_motivo_check CHECK (
    motivo IN (
        'facial', 'pin', 'sin_asignacion', 'limite_intentos',
        'no_reconocido', 'pin_incorrecto', 'limite_intentos_pin',
        'matricula_incorrecta', 'pin_cancelado',
        'puerta_cerrada', 'puerta_no_cerrada',
        'recurso_en_uso', 'recurso_finalizado', 'recurso_expirado',
        'remoto'
    ) OR motivo IS NULL
);
