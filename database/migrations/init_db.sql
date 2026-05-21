PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tipo_usuarios (
	idTipoUsuario INTEGER PRIMARY KEY AUTOINCREMENT,
	nombreTipoUsuario TEXT NOT NULL CHECK(length(nombreTipoUsuario) <= 60),
	estado TEXT NOT NULL DEFAULT 'activo' CHECK(estado IN ('activo', 'inactivo')),
	fechaHoraReg TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	fechaHoraAct TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	creadoPor INTEGER NOT NULL,
	modificadoPor INTEGER,
	CONSTRAINT uq_nombreTipoUsuario UNIQUE (nombreTipoUsuario)
);

CREATE INDEX IF NOT EXISTS idx_tipo_usuarios_estado
	ON tipo_usuarios(estado);

CREATE TABLE IF NOT EXISTS unidad_academica (
	idUnidadAcademica INTEGER PRIMARY KEY AUTOINCREMENT,
	nombreUnidadAcademica TEXT NOT NULL CHECK(length(nombreUnidadAcademica) <= 100),
	estado TEXT NOT NULL DEFAULT 'activo' CHECK(estado IN ('activo', 'inactivo')),
	zona TEXT CHECK(length(zona) <= 100),
	fechaHoraReg TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	fechaHoraAct TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	creadoPor INTEGER NOT NULL,
	modificadoPor INTEGER,
	CONSTRAINT uq_nombreUnidadAcademica UNIQUE (nombreUnidadAcademica)
);

CREATE TABLE IF NOT EXISTS area_lockers (
	idArea INTEGER PRIMARY KEY AUTOINCREMENT,
	nombreArea TEXT NOT NULL CHECK(length(nombreArea) <= 30),
	idUsuario INTEGER,
	fechaHoraReg TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	fechaHoraAct TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	creadoPor INTEGER NOT NULL,
	modificadoPor INTEGER,
	estado TEXT NOT NULL DEFAULT 'activo' CHECK(estado IN ('activo', 'inactivo')),
	CONSTRAINT uq_nombreArea UNIQUE (nombreArea)
);

CREATE TABLE IF NOT EXISTS usuarios (
	idUsuario INTEGER PRIMARY KEY AUTOINCREMENT,
	nombre TEXT NOT NULL CHECK(length(nombre) <= 100),
	apPaterno TEXT NOT NULL CHECK(length(apPaterno) <= 100),
	apMaterno TEXT CHECK(length(apMaterno) <= 100),
	idTipoUsuario INTEGER NOT NULL,
	idUnidadAcademica INTEGER NOT NULL,
	estado TEXT NOT NULL DEFAULT 'activo' CHECK(estado IN ('activo', 'inactivo', 'suspendido')),
	emailInst TEXT NOT NULL CHECK(length(emailInst) <= 100),
	tel TEXT CHECK(length(tel) <= 20),
	matricula INTEGER NOT NULL,
	pin TEXT NOT NULL CHECK(length(pin) = 64),
	fechaHoraReg TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	fechaHoraAct TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	creadoPor INTEGER NOT NULL,
	modificadoPor INTEGER,
	CONSTRAINT uq_emailInst UNIQUE (emailInst),
	CONSTRAINT uq_matricula UNIQUE (matricula),
	CONSTRAINT fk_usuario_tipo
		FOREIGN KEY (idTipoUsuario) REFERENCES tipo_usuarios(idTipoUsuario)
		ON UPDATE CASCADE ON DELETE RESTRICT,
	CONSTRAINT fk_usuario_unidad
		FOREIGN KEY (idUnidadAcademica) REFERENCES unidad_academica(idUnidadAcademica)
		ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_usuarios_estado ON usuarios(estado);
CREATE INDEX IF NOT EXISTS idx_usuarios_tipo ON usuarios(idTipoUsuario);
CREATE INDEX IF NOT EXISTS idx_usuarios_unidad ON usuarios(idUnidadAcademica);

CREATE TABLE IF NOT EXISTS encoding (
	idEncoding INTEGER PRIMARY KEY AUTOINCREMENT,
	idUsuario INTEGER NOT NULL,
	estado TEXT NOT NULL DEFAULT 'activo' CHECK(estado IN ('activo', 'inactivo')),
	vector BLOB NOT NULL,
	dimension INTEGER NOT NULL DEFAULT 128 CHECK(dimension > 0),
	hashVector TEXT CHECK(length(hashVector) = 64),
	tipoParte TEXT NOT NULL DEFAULT 'frontal' CHECK(tipoParte IN ('frontal', 'izquierda', 'derecha')),
	vectorDtype TEXT NOT NULL DEFAULT 'float32' CHECK(vectorDtype IN ('float32', 'float64')),
	modelo TEXT NOT NULL CHECK(length(modelo) <= 100),
	modeloVersion TEXT NOT NULL CHECK(length(modeloVersion) <= 100),
	createdAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	updatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	CONSTRAINT uq_encoding_hash UNIQUE (hashVector),
	CONSTRAINT fk_encoding_usuario
		FOREIGN KEY (idUsuario) REFERENCES usuarios(idUsuario)
		ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_encoding_usuario
	ON encoding(idUsuario, estado);

CREATE TABLE IF NOT EXISTS lockers (
	idLocker INTEGER PRIMARY KEY AUTOINCREMENT,
	idUnidadAcademica INTEGER NOT NULL,
	idArea INTEGER NOT NULL,
	estado TEXT NOT NULL DEFAULT 'activo' CHECK(estado IN ('activo', 'inactivo', 'mantenimiento')),
	fechaHoraReg TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	fechaHoraAct TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	creadoPor INTEGER NOT NULL,
	modificadoPor INTEGER,
	CONSTRAINT fk_locker_unidad
		FOREIGN KEY (idUnidadAcademica) REFERENCES unidad_academica(idUnidadAcademica)
		ON UPDATE CASCADE ON DELETE RESTRICT,
	CONSTRAINT fk_locker_area
		FOREIGN KEY (idArea) REFERENCES area_lockers(idArea)
		ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_lockers_estado ON lockers(estado);
CREATE INDEX IF NOT EXISTS idx_lockers_unidad ON lockers(idUnidadAcademica);

CREATE TABLE IF NOT EXISTS asignacion_locker (
	idLockerAsignado INTEGER PRIMARY KEY AUTOINCREMENT,
	idUsuario INTEGER NOT NULL,
	idLocker INTEGER NOT NULL,
	disponible TEXT NOT NULL DEFAULT 'no' CHECK(disponible IN ('si', 'no')),
	estado TEXT NOT NULL DEFAULT 'activo' CHECK(estado IN ('activo', 'inactivo', 'vencido')),
	fechaHoraReg TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	fechaHoraAct TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	creadoPor INTEGER NOT NULL,
	modificadoPor INTEGER,
	CONSTRAINT uq_usuario_activo UNIQUE (idUsuario, estado),
	CONSTRAINT uq_locker_activo UNIQUE (idLocker, estado),
	CONSTRAINT fk_asignacion_usuario
		FOREIGN KEY (idUsuario) REFERENCES usuarios(idUsuario)
		ON UPDATE CASCADE ON DELETE RESTRICT,
	CONSTRAINT fk_asignacion_locker
		FOREIGN KEY (idLocker) REFERENCES lockers(idLocker)
		ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_asignacion_usuario
	ON asignacion_locker(idUsuario, estado);

CREATE INDEX IF NOT EXISTS idx_asignacion_locker
	ON asignacion_locker(idLocker, estado);

CREATE TABLE IF NOT EXISTS historial_accesos (
	idAcceso INTEGER PRIMARY KEY AUTOINCREMENT,
	idLockerAsignado INTEGER,
	fechaHoraAcceso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
	accesoPermitido TEXT NOT NULL DEFAULT 'si' CHECK(accesoPermitido IN ('si', 'no')),
	motivo TEXT CHECK(motivo IN (
		'facial', 'pin', 'sin_asignacion', 'limite_intentos',
		'no_reconocido', 'pin_incorrecto', 'limite_intentos_pin',
		'matricula_incorrecta', 'pin_cancelado'
	) OR motivo IS NULL),
	fechaExpiracion TEXT NOT NULL,
	CONSTRAINT fk_historial_asignacion
		FOREIGN KEY (idLockerAsignado) REFERENCES asignacion_locker(idLockerAsignado)
		ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_historial_expiracion
	ON historial_accesos(fechaExpiracion, accesoPermitido);

CREATE INDEX IF NOT EXISTS idx_historial_locker
	ON historial_accesos(idLockerAsignado, fechaHoraAcceso);

CREATE TRIGGER IF NOT EXISTS trg_usuarios_act
	AFTER UPDATE ON usuarios
	FOR EACH ROW
BEGIN
	UPDATE usuarios
	   SET fechaHoraAct = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
	 WHERE idUsuario = NEW.idUsuario;
END;

CREATE TRIGGER IF NOT EXISTS trg_tipo_usuarios_act
	AFTER UPDATE ON tipo_usuarios
	FOR EACH ROW
BEGIN
	UPDATE tipo_usuarios
	   SET fechaHoraAct = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
	 WHERE idTipoUsuario = NEW.idTipoUsuario;
END;

CREATE TRIGGER IF NOT EXISTS trg_unidad_academica_act
	AFTER UPDATE ON unidad_academica
	FOR EACH ROW
BEGIN
	UPDATE unidad_academica
	   SET fechaHoraAct = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
	 WHERE idUnidadAcademica = NEW.idUnidadAcademica;
END;

CREATE TRIGGER IF NOT EXISTS trg_lockers_act
	AFTER UPDATE ON lockers
	FOR EACH ROW
BEGIN
	UPDATE lockers
	   SET fechaHoraAct = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
	 WHERE idLocker = NEW.idLocker;
END;

CREATE TRIGGER IF NOT EXISTS trg_asignacion_act
	AFTER UPDATE ON asignacion_locker
	FOR EACH ROW
BEGIN
	UPDATE asignacion_locker
	   SET fechaHoraAct = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
	 WHERE idLockerAsignado = NEW.idLockerAsignado;
END;

CREATE TRIGGER IF NOT EXISTS trg_encoding_act
	AFTER UPDATE ON encoding
	FOR EACH ROW
BEGIN
	UPDATE encoding
	   SET updatedAt = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
	 WHERE idEncoding = NEW.idEncoding;
END;

CREATE VIEW IF NOT EXISTS v_historial_detalle AS
SELECT
	h.idAcceso,
	u.nombre || ' ' || u.apPaterno AS nombreCompleto,
	u.matricula,
	l.idLocker,
	a.nombreArea,
	h.fechaHoraAcceso,
	h.accesoPermitido,
	h.motivo,
	h.fechaExpiracion
FROM historial_accesos h
LEFT JOIN asignacion_locker al ON h.idLockerAsignado = al.idLockerAsignado
LEFT JOIN usuarios u ON al.idUsuario = u.idUsuario
LEFT JOIN lockers l ON al.idLocker = l.idLocker
LEFT JOIN area_lockers a ON l.idArea = a.idArea
ORDER BY h.fechaHoraAcceso DESC;

CREATE VIEW IF NOT EXISTS v_lockers_disponibles AS
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

INSERT OR IGNORE INTO tipo_usuarios (idTipoUsuario, nombreTipoUsuario, estado, creadoPor)
VALUES
	(1, 'Superadmin', 'activo', 1),
	(2, 'Admin', 'activo', 1),
	(4, 'Usuario', 'activo', 1);

INSERT OR IGNORE INTO unidad_academica (idUnidadAcademica, nombreUnidadAcademica, zona, estado, creadoPor)
VALUES
	(1, 'General', NULL, 'activo', 1);

INSERT OR IGNORE INTO area_lockers (idArea, nombreArea, idUsuario, estado, creadoPor)
VALUES
	(1, 'General', NULL, 'activo', 1);
