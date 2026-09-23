-- Migración: Admin y Superadmin siempre tienen permiso de activación "ambos"
-- Fecha: 2026-09-23
-- Descripción: El panel web ya no muestra "Permisos de activación" para
-- Admin/Superadmin y guarda "ambos" automáticamente. Esta migración corrige
-- los administradores que ya existían con el valor por defecto ('locker').
-- Los nombres de tipo coinciden con normalize_role() de webapp/auth.py.

UPDATE usuarios
SET permisoactivacion = 'ambos'
WHERE permisoactivacion <> 'ambos'
  AND idTipoUsuario IN (
      SELECT idTipoUsuario
      FROM tipo_usuarios
      WHERE lower(trim(nombreTipoUsuario)) IN (
          'superadmin', 'super administrador', 'superadministrador',
          'admin', 'administrador'
      )
  );
