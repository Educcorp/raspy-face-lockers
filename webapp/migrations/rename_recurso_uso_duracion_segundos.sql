-- Migración: recurso_uso.duracionMinutos → duracionSegundos
-- Fecha: 2026-09-30
-- El selector de tiempo del kiosco pasó de un spinner de 15 en 15 minutos a
-- 3 bandas HH:MM:SS con teclado numérico (precisión de segundos). Antes de
-- este cambio duracionMinutos ya perdía la parte de segundos que el usuario
-- pudiera elegir; se renombra la columna y se guarda con precisión real.
-- recurso_uso está vacía en producción al momento de esta migración (sin
-- filas reales que preservar) — cambio de bajo riesgo.
-- Idempotente: se puede ejecutar más de una vez.

DO $$ BEGIN
    ALTER TABLE recurso_uso RENAME COLUMN duracionMinutos TO duracionSegundos;
EXCEPTION WHEN undefined_column THEN NULL; END $$;

ALTER TABLE recurso_uso DROP CONSTRAINT IF EXISTS recurso_uso_duracionminutos_check;
ALTER TABLE recurso_uso DROP CONSTRAINT IF EXISTS recurso_uso_duracionsegundos_check;
ALTER TABLE recurso_uso ADD CONSTRAINT recurso_uso_duracionsegundos_check
    CHECK (duracionSegundos > 0 AND duracionSegundos <= 10800);
