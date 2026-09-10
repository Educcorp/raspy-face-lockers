-- Esquema PostgreSQL del panel web — equivalente remoto de
-- database/migrations/init_db.sql (SQLite, usado por el dispositivo Raspberry Pi).
--
-- Ambos —el software embebido del locker y este panel web— comparten la misma
-- base de datos remota. El reconocimiento facial y el control GPIO NO se tocan:
-- siguen viviendo exclusivamente en la Raspberry Pi.

CREATE TABLE IF NOT EXISTS tipo_usuarios (
    idTipoUsuario SERIAL PRIMARY KEY,
    nombreTipoUsuario TEXT NOT NULL CHECK (length(nombreTipoUsuario) <= 60),
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    fechaHoraReg TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraAct TIMESTAMPTZ NOT NULL DEFAULT now(),
    creadoPor INTEGER NOT NULL,
    modificadoPor INTEGER,
    CONSTRAINT uq_nombreTipoUsuario UNIQUE (nombreTipoUsuario)
);

CREATE INDEX IF NOT EXISTS idx_tipo_usuarios_estado ON tipo_usuarios (estado);

CREATE TABLE IF NOT EXISTS unidad_academica (
    idUnidadAcademica SERIAL PRIMARY KEY,
    nombreUnidadAcademica TEXT NOT NULL CHECK (length(nombreUnidadAcademica) <= 100),
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    zona TEXT CHECK (length(zona) <= 100),
    fechaHoraReg TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraAct TIMESTAMPTZ NOT NULL DEFAULT now(),
    creadoPor INTEGER NOT NULL,
    modificadoPor INTEGER,
    CONSTRAINT uq_nombreUnidadAcademica UNIQUE (nombreUnidadAcademica)
);

CREATE TABLE IF NOT EXISTS area_lockers (
    idArea SERIAL PRIMARY KEY,
    nombreArea TEXT NOT NULL CHECK (length(nombreArea) <= 30),
    idUsuario INTEGER,
    idUnidadAcademica INTEGER REFERENCES unidad_academica (idUnidadAcademica),
    fechaHoraReg TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraAct TIMESTAMPTZ NOT NULL DEFAULT now(),
    creadoPor INTEGER NOT NULL,
    modificadoPor INTEGER,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    CONSTRAINT uq_nombreArea UNIQUE (nombreArea)
);

CREATE TABLE IF NOT EXISTS usuarios (
    idUsuario SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL CHECK (length(nombre) <= 100),
    apPaterno TEXT NOT NULL CHECK (length(apPaterno) <= 100),
    apMaterno TEXT CHECK (length(apMaterno) <= 100),
    idTipoUsuario INTEGER NOT NULL,
    idUnidadAcademica INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo', 'suspendido')),
    emailInst TEXT NOT NULL CHECK (length(emailInst) <= 100),
    tel TEXT CHECK (length(tel) <= 20),
    matricula INTEGER NOT NULL,
    pin TEXT NOT NULL CHECK (length(pin) = 64),
    fechaHoraReg TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraAct TIMESTAMPTZ NOT NULL DEFAULT now(),
    creadoPor INTEGER NOT NULL,
    modificadoPor INTEGER,
    CONSTRAINT uq_emailInst UNIQUE (emailInst),
    CONSTRAINT uq_matricula UNIQUE (matricula),
    CONSTRAINT fk_usuario_tipo
        FOREIGN KEY (idTipoUsuario) REFERENCES tipo_usuarios (idTipoUsuario)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_usuario_unidad
        FOREIGN KEY (idUnidadAcademica) REFERENCES unidad_academica (idUnidadAcademica)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_usuarios_estado ON usuarios (estado);
CREATE INDEX IF NOT EXISTS idx_usuarios_tipo ON usuarios (idTipoUsuario);
CREATE INDEX IF NOT EXISTS idx_usuarios_unidad ON usuarios (idUnidadAcademica);

CREATE TABLE IF NOT EXISTS encoding (
    idEncoding SERIAL PRIMARY KEY,
    idUsuario INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    vector BYTEA NOT NULL,
    dimension INTEGER NOT NULL DEFAULT 128 CHECK (dimension > 0),
    hashVector TEXT CHECK (length(hashVector) = 64),
    tipoParte TEXT NOT NULL DEFAULT 'frontal' CHECK (tipoParte IN ('frontal', 'izquierda', 'derecha')),
    vectorDtype TEXT NOT NULL DEFAULT 'float32' CHECK (vectorDtype IN ('float32', 'float64')),
    modelo TEXT NOT NULL CHECK (length(modelo) <= 100),
    modeloVersion TEXT NOT NULL CHECK (length(modeloVersion) <= 100),
    createdAt TIMESTAMPTZ NOT NULL DEFAULT now(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_encoding_hash UNIQUE (hashVector),
    CONSTRAINT fk_encoding_usuario
        FOREIGN KEY (idUsuario) REFERENCES usuarios (idUsuario)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_encoding_usuario ON encoding (idUsuario, estado);

CREATE TABLE IF NOT EXISTS lockers (
    idLocker SERIAL PRIMARY KEY,
    idUnidadAcademica INTEGER NOT NULL,
    idArea INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo', 'mantenimiento')),
    fechaHoraReg TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraAct TIMESTAMPTZ NOT NULL DEFAULT now(),
    creadoPor INTEGER NOT NULL,
    modificadoPor INTEGER,
    CONSTRAINT fk_locker_unidad
        FOREIGN KEY (idUnidadAcademica) REFERENCES unidad_academica (idUnidadAcademica)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_locker_area
        FOREIGN KEY (idArea) REFERENCES area_lockers (idArea)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_lockers_estado ON lockers (estado);
CREATE INDEX IF NOT EXISTS idx_lockers_unidad ON lockers (idUnidadAcademica);

CREATE TABLE IF NOT EXISTS asignacion_locker (
    idLockerAsignado SERIAL PRIMARY KEY,
    idUsuario INTEGER NOT NULL,
    idLocker INTEGER NOT NULL,
    disponible TEXT NOT NULL DEFAULT 'no' CHECK (disponible IN ('si', 'no')),
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo', 'vencido')),
    fechaHoraReg TIMESTAMPTZ NOT NULL DEFAULT now(),
    fechaHoraAct TIMESTAMPTZ NOT NULL DEFAULT now(),
    creadoPor INTEGER NOT NULL,
    modificadoPor INTEGER,
    CONSTRAINT uq_usuario_activo UNIQUE (idUsuario, estado),
    CONSTRAINT uq_locker_activo UNIQUE (idLocker, estado),
    CONSTRAINT fk_asignacion_usuario
        FOREIGN KEY (idUsuario) REFERENCES usuarios (idUsuario)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_asignacion_locker
        FOREIGN KEY (idLocker) REFERENCES lockers (idLocker)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_asignacion_usuario ON asignacion_locker (idUsuario, estado);
CREATE INDEX IF NOT EXISTS idx_asignacion_locker ON asignacion_locker (idLocker, estado);

CREATE TABLE IF NOT EXISTS historial_accesos (
    idAcceso SERIAL PRIMARY KEY,
    idLockerAsignado INTEGER,
    idUsuario INTEGER,
    fechaHoraAcceso TIMESTAMPTZ NOT NULL DEFAULT now(),
    accesoPermitido TEXT NOT NULL DEFAULT 'si' CHECK (accesoPermitido IN ('si', 'no')),
    motivo TEXT CHECK (
        motivo IN (
            'facial', 'pin', 'sin_asignacion', 'limite_intentos',
            'no_reconocido', 'pin_incorrecto', 'limite_intentos_pin',
            'matricula_incorrecta', 'pin_cancelado',
            'puerta_cerrada', 'puerta_no_cerrada'
        ) OR motivo IS NULL
    ),
    fechaExpiracion TIMESTAMPTZ NOT NULL,
    CONSTRAINT fk_historial_asignacion
        FOREIGN KEY (idLockerAsignado) REFERENCES asignacion_locker (idLockerAsignado)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_historial_usuario
        FOREIGN KEY (idUsuario) REFERENCES usuarios (idUsuario)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_historial_expiracion ON historial_accesos (fechaExpiracion, accesoPermitido);
CREATE INDEX IF NOT EXISTS idx_historial_locker ON historial_accesos (idLockerAsignado, fechaHoraAcceso);

-- ── Triggers: equivalentes en Postgres a los AFTER UPDATE de SQLite ─────────
-- (en Postgres se implementan como BEFORE UPDATE que ajustan NEW antes de escribir)

CREATE OR REPLACE FUNCTION trg_touch_fecha_hora_act() RETURNS TRIGGER AS $$
BEGIN
    NEW.fechaHoraAct = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updatedAt = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_usuarios_act ON usuarios;
CREATE TRIGGER trg_usuarios_act BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION trg_touch_fecha_hora_act();

DROP TRIGGER IF EXISTS trg_tipo_usuarios_act ON tipo_usuarios;
CREATE TRIGGER trg_tipo_usuarios_act BEFORE UPDATE ON tipo_usuarios
    FOR EACH ROW EXECUTE FUNCTION trg_touch_fecha_hora_act();

CREATE TRIGGER trg_unidad_academica_act BEFORE UPDATE ON unidad_academica
    FOR EACH ROW EXECUTE FUNCTION trg_touch_fecha_hora_act();

DROP TRIGGER IF EXISTS trg_area_lockers_act ON area_lockers;
CREATE TRIGGER trg_area_lockers_act BEFORE UPDATE ON area_lockers
    FOR EACH ROW EXECUTE FUNCTION trg_touch_fecha_hora_act();

DROP TRIGGER IF EXISTS trg_lockers_act ON lockers;
CREATE TRIGGER trg_lockers_act BEFORE UPDATE ON lockers
    FOR EACH ROW EXECUTE FUNCTION trg_touch_fecha_hora_act();

DROP TRIGGER IF EXISTS trg_asignacion_act ON asignacion_locker;
CREATE TRIGGER trg_asignacion_act BEFORE UPDATE ON asignacion_locker
    FOR EACH ROW EXECUTE FUNCTION trg_touch_fecha_hora_act();

DROP TRIGGER IF EXISTS trg_encoding_act ON encoding;
CREATE TRIGGER trg_encoding_act BEFORE UPDATE ON encoding
    FOR EACH ROW EXECUTE FUNCTION trg_touch_updated_at();

-- ── Vistas ───────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_historial_detalle AS
SELECT
    h.idAcceso,
    COALESCE(u1.nombre || ' ' || u1.apPaterno, u2.nombre || ' ' || u2.apPaterno) AS nombreCompleto,
    COALESCE(u1.matricula, u2.matricula) AS matricula,
    l.idLocker,
    a.nombreArea,
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
ORDER BY h.fechaHoraAcceso DESC;

CREATE OR REPLACE VIEW v_lockers_disponibles AS
SELECT
    l.idLocker,
    ua.nombreUnidadAcademica,
    a.nombreArea,
    l.estado
FROM lockers l
JOIN unidad_academica ua ON l.idUnidadAcademica = ua.idUnidadAcademica
JOIN area_lockers a ON l.idArea = a.idArea
WHERE l.estado = 'activo'
  AND l.idLocker NOT IN (
      SELECT idLocker FROM asignacion_locker WHERE estado = 'activo'
  );

-- ── Datos semilla (catálogos mínimos) ───────────────────────────────────────

INSERT INTO tipo_usuarios (nombreTipoUsuario, estado, creadoPor)
VALUES ('Superadmin', 'activo', 1), ('Admin', 'activo', 1), ('Usuario', 'activo', 1)
ON CONFLICT (nombreTipoUsuario) DO NOTHING;

INSERT INTO unidad_academica (nombreUnidadAcademica, zona, estado, creadoPor)
VALUES ('General', NULL, 'activo', 1)
ON CONFLICT (nombreUnidadAcademica) DO NOTHING;

INSERT INTO area_lockers (nombreArea, idUsuario, estado, creadoPor)
VALUES ('General', NULL, 'activo', 1)
ON CONFLICT (nombreArea) DO NOTHING;
