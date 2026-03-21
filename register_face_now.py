"""
register_face_now.py
====================
Script de registro facial directo por consola.
No requiere GUI ni dlib. Usa el backend HOG (cv2).

Uso:
    python register_face_now.py

Flujo:
  1. Muestra usuarios activos disponibles
  2. Pide seleccionar un usuario
  3. Abre la cámara, detecta rostro, captura embedding HOG de 128-dim
  4. Guarda el encoding en la tabla `encoding`
  5. Si el usuario no tiene locker asignado, asigna uno disponible

Requisitos: cv2, numpy, picamera2 (o webcam USB via OpenCV índice 0)
"""

import sys
import hashlib
import time
import logging

import cv2
import numpy as np

# ── Setup ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, ".")
logging.basicConfig(level=logging.WARNING)

from database.connection import fetch_all, fetch_one, execute
from core.face_recognition import FaceEmbeddingExtractor, FaceDetector

# ── Colores ANSI ──────────────────────────────────────────────────────────────
G  = "\033[92m"   # verde
Y  = "\033[93m"   # amarillo
R  = "\033[91m"   # rojo
B  = "\033[94m"   # azul
NC = "\033[0m"    # reset

def bold(s): return f"\033[1m{s}{NC}"
def ok(s):   print(f"  {G}✓{NC} {s}")
def warn(s): print(f"  {Y}⚠{NC}  {s}")
def err(s):  print(f"  {R}✗{NC} {s}")


# ── Helpers: cámara ───────────────────────────────────────────────────────────

def open_camera():
    """Intenta abrir la cámara (picamera2 primero, luego OpenCV)."""
    # Intentar picamera2
    try:
        from picamera2 import Picamera2
        cam = Picamera2(0)
        cfg = cam.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
        cam.configure(cfg)
        cam.start()
        time.sleep(0.5)
        ok("Cámara picamera2 iniciada")
        return ("picamera2", cam)
    except Exception as e:
        warn(f"picamera2 no disponible ({e}), intentando OpenCV...")

    # Fallback OpenCV
    for idx in range(4):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ok(f"Cámara OpenCV índice {idx}")
            return ("opencv", cap)
        cap.release()

    return None, None


def get_frame(kind, cam):
    if kind == "picamera2":
        return cam.capture_array()   # RGB888
    else:
        ret, frame = cam.read()
        if not ret:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # devolver RGB como picamera2


def release_camera(kind, cam):
    try:
        if kind == "picamera2":
            cam.stop()
        else:
            cam.release()
    except Exception:
        pass


# ── Detección de rostro ───────────────────────────────────────────────────────

def wait_for_face(kind, cam, detector: FaceDetector, timeout: float = 30.0) -> tuple:
    """
    Espera hasta detectar un rostro estable por ≥15 frames.
    Retorna (frame_bgr, face_box) o (None, None) si timeout.
    """
    print(f"\n  {B}Posiciona tu rostro frente a la cámara...{NC}")
    print(f"  (ventana de preview — presiona Q para cancelar)\n")

    stable_count = 0
    STABLE_NEEDED = 15
    start = time.time()

    while time.time() - start < timeout:
        frame_rgb = get_frame(kind, cam)
        if frame_rgb is None:
            time.sleep(0.05)
            continue

        # El detector espera BGR
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        faces = detector.detect(frame_bgr)

        # Preview con indicador
        preview = frame_bgr.copy()
        if faces:
            stable_count += 1
            box = faces[0]["box"]
            x, y, w, h = [int(v) for v in box]
            pct = min(100, int(stable_count / STABLE_NEEDED * 100))
            color = (0, int(2.55 * pct), int(2.55 * (100 - pct)))  # rojo → verde
            cv2.rectangle(preview, (x, y), (x+w, y+h), color, 2)
            cv2.putText(preview, f"Capturando: {pct}%",
                        (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        else:
            stable_count = max(0, stable_count - 2)
            cv2.putText(preview, "Buscando rostro...",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 100, 255), 2)

        cv2.imshow("Registro Facial — presiona Q para cancelar", preview)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

        if stable_count >= STABLE_NEEDED:
            cv2.destroyAllWindows()
            return frame_bgr, faces[0]["box"]

        time.sleep(0.05)

    cv2.destroyAllWindows()
    return None, None


# ── Registro en DB ────────────────────────────────────────────────────────────

def save_encoding(user_id: int, embedding: np.ndarray) -> bool:
    """Desactiva encodings previos y guarda el nuevo."""
    from config import FACE_RECOGNITION_CONFIG

    # Marcar encodings anteriores como inactivo
    execute("UPDATE encoding SET estado='inactivo' WHERE idUsuario=?", (user_id,))

    vec_bytes = embedding.tobytes()
    vec_hash  = hashlib.sha256(vec_bytes).hexdigest()
    modelo    = FACE_RECOGNITION_CONFIG.get("model_type", "hog_cv2")

    try:
        execute("""
            INSERT INTO encoding
                (idUsuario, estado, vector, dimension, hashVector,
                 tipoParte, vectorDtype, modelo, modeloVersion)
            VALUES (?, 'activo', ?, ?, ?, 'frontal', 'float32', ?, '1.0')
        """, (user_id, vec_bytes, len(embedding), vec_hash, modelo))
        return True
    except Exception as e:
        err(f"Error guardando encoding: {e}")
        return False


def assign_locker_if_needed(user_id: int) -> int | None:
    """Asigna el primer locker disponible al usuario si no tiene ninguno."""
    existing = fetch_one(
        "SELECT idLocker FROM asignacion_locker WHERE idUsuario=? AND estado='activo'",
        (user_id,)
    )
    if existing:
        return existing["idLocker"]

    # Buscar primer locker sin asignación activa
    all_lockers = fetch_all("SELECT idLocker FROM lockers WHERE estado='activo'")
    assigned_lockers = {
        r["idLocker"]
        for r in fetch_all("SELECT idLocker FROM asignacion_locker WHERE estado='activo'")
    }

    for lk in all_lockers:
        lid = lk["idLocker"]
        if lid not in assigned_lockers:
            execute("""
                INSERT INTO asignacion_locker (idLocker, idUsuario, disponible, estado)
                VALUES (?, ?, 'si', 'activo')
            """, (lid, user_id))
            return lid

    return None


# ── Flujo principal ───────────────────────────────────────────────────────────

def main():
    print()
    print(bold("═══════════════════════════════════════════"))
    print(bold("  Smart Locker — Registro Facial Rápido    "))
    print(bold("═══════════════════════════════════════════"))
    print()

    # Mostrar usuarios disponibles
    users = fetch_all("SELECT idUsuario, nombre, apPaterno FROM usuarios WHERE estado='activo'")
    if not users:
        err("No hay usuarios activos en la base de datos. Registra usuarios primero.")
        sys.exit(1)

    print("Usuarios disponibles:")
    for u in users:
        print(f"  [{u['idUsuario']}] {u['nombre']} {u['apPaterno']}")

    print()
    try:
        uid_str = input("Ingresa el ID del usuario a registrar: ").strip()
        user_id = int(uid_str)
    except (ValueError, EOFError):
        err("ID inválido.")
        sys.exit(1)

    user = fetch_one("SELECT * FROM usuarios WHERE idUsuario=? AND estado='activo'", (user_id,))
    if not user:
        err(f"Usuario {user_id} no encontrado o inactivo.")
        sys.exit(1)

    nombre_completo = f"{user['nombre']} {user['apPaterno']}".strip()
    print()
    ok(f"Usuario: {bold(nombre_completo)} (ID={user_id})")

    # Inicializar detector y extractor
    detector  = FaceDetector()
    extractor = FaceEmbeddingExtractor()
    ok(f"Extractor HOG listo (is_ready={extractor.is_ready}, dlib={extractor._use_dlib})")

    # Abrir cámara
    kind, cam = open_camera()
    if cam is None:
        err("No se pudo abrir ninguna cámara.")
        sys.exit(1)

    # Capturar rostro
    print()
    frame_bgr, face_box = wait_for_face(kind, cam, detector, timeout=30.0)
    release_camera(kind, cam)

    if frame_bgr is None:
        err("No se detectó ningún rostro. Intenta de nuevo.")
        sys.exit(1)

    ok("Rostro detectado")

    # Extraer embedding
    print(f"  Extrayendo embedding HOG...")
    embedding = extractor.get_embedding(frame_bgr, face_box)
    if embedding is None:
        err("No se pudo extraer embedding. Intenta de nuevo.")
        sys.exit(1)

    ok(f"Embedding extraído: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")

    # Guardar en DB
    if save_encoding(user_id, embedding):
        ok("Encoding guardado en DB")
    else:
        err("Fallo al guardar encoding.")
        sys.exit(1)

    # Asignar locker
    locker_id = assign_locker_if_needed(user_id)
    if locker_id:
        ok(f"Locker asignado: {bold(f'Locker #{locker_id}')}")
    else:
        warn("No hay lockers disponibles para asignar.")

    print()
    print(bold("═══════════════════════════════════════════"))
    print(bold(f"  ✅  {nombre_completo} registrado correctamente"))
    if locker_id:
        print(bold(f"  🔒  Locker #{locker_id} asignado"))
    print(bold("═══════════════════════════════════════════"))
    print()
    print(f"  Ahora inicia el panel del locker:")
    print(f"  {B}python main.py --mode locker{NC}")
    print()


if __name__ == "__main__":
    main()
