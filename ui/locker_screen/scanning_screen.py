"""
ScanningScreen – pantalla de escaneo facial (480×800 px).

La cámara ocupa casi toda la ventana. Se dibuja una silueta guía
que cambia de rojo a verde según la detección del rostro.
Al reconocer al usuario, se muestra un overlay verde con los datos
(nombre, casillero, fecha) y un countdown de regreso automático.
Un botón de flecha ← en la parte inferior permite volver al standby.
"""

import customtkinter as ctk
import threading
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter
import logging
from typing import Optional
from datetime import datetime
from datetime import timedelta

from config import FACE_RECOGNITION_CONFIG
from database.connection import fetch_all, execute

logger = logging.getLogger(__name__)


class ScanningScreen(ctk.CTkFrame):
    """
    Pantalla activa durante el reconocimiento facial.
    La cámara ocupa toda la ventana con silueta guía superpuesta.
    """

    BG_COLOR   = "#1A1A2E"   # fondo oscuro para contraste con cámara
    PRIMARY    = "#5B8C5A"
    SUCCESS    = "#4CAF50"
    WARNING    = "#D4A34A"
    DANGER     = "#C75C5C"
    TEXT_COLOR = "#FFFFFF"
    MUTED      = "#B0B0B0"

    # Colores de la silueta
    SILHOUETTE_NO_FACE  = (200, 80, 80, 160)    # rojo semi-transparente
    SILHOUETTE_FACE_OK  = (90, 180, 90, 160)     # verde semi-transparente

    MAX_ATTEMPTS    = 3
    DISPLAY_SECONDS = 8
    RECOGNITION_INTERVAL_FRAMES = 6
    STABLE_FACE_FRAMES = 8
    RECOGNITION_COOLDOWN_SECONDS = 2.0

    # Dimensiones de la ventana
    WIN_W = 480
    WIN_H = 800

    def __init__(self, parent: ctk.CTk, controller) -> None:
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._attempts  = 0
        self._face_detected = False
        self._success_shown = False
        self._return_job = None
        self._frame_counter = 0
        self._stable_face_frames = 0
        self._last_recognition_ts = 0.0
        self._last_seen_face_box = None

        # Variables de captura de cámara
        self._camera_thread: Optional[threading.Thread] = None
        self._camera_running = False
        self._camera_frame: Optional[np.ndarray] = None
        self._detected_faces = []
        self._photo_image: Optional[tkinter.PhotoImage] = None

        # Datos del usuario reconocido
        self._user_data: Optional[dict] = None

        # Inicializar módulo de reconocimiento facial
        try:
            from core.face_recognition import get_face_recognition_manager
            self.face_manager = get_face_recognition_manager()
        except Exception as e:
            logger.error(f"Error importando FaceRecognitionManager: {e}")
            self.face_manager = None

        # Pre-generar la máscara de silueta
        self._silhouette_mask = self._create_silhouette_mask()

        self._build_ui()

    # ── Crear silueta de persona ──────────────────────────────────────────────

    def _create_silhouette_mask(self) -> Image.Image:
        """Crea una máscara PNG con la silueta de cabeza/hombros recortada."""
        mask = Image.new("RGBA", (self.WIN_W, self.WIN_H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(mask)

        # Fondo semitransparente oscuro
        draw.rectangle([(0, 0), (self.WIN_W, self.WIN_H)], fill=(0, 0, 0, 100))

        cx, cy = self.WIN_W // 2, self.WIN_H // 2 - 60

        # Recortar zona de la cabeza (elipse)
        head_rx, head_ry = 95, 120
        head_box = [cx - head_rx, cy - head_ry - 30, cx + head_rx, cy + head_ry - 30]
        draw.ellipse(head_box, fill=(0, 0, 0, 0))

        # Recortar zona cuello + hombros (elipse ancha)
        body_cy = cy + head_ry + 20
        body_rx, body_ry = 160, 100
        body_box = [cx - body_rx, body_cy - 10, cx + body_rx, body_cy + body_ry + 40]
        draw.ellipse(body_box, fill=(0, 0, 0, 0))

        return mask

    def _draw_silhouette_outline(self, draw: ImageDraw.Draw, color_rgba: tuple) -> None:
        """Dibuja el contorno de la silueta (cabeza + hombros) con el color dado."""
        cx, cy = self.WIN_W // 2, self.WIN_H // 2 - 60
        color_rgb = color_rgba[:3]

        head_rx, head_ry = 95, 120
        head_box = [cx - head_rx, cy - head_ry - 30, cx + head_rx, cy + head_ry - 30]
        draw.ellipse(head_box, outline=color_rgb, width=3)

        body_cy = cy + head_ry + 20
        body_rx, body_ry = 160, 100
        body_box = [cx - body_rx, body_cy - 10, cx + body_rx, body_cy + body_ry + 40]
        draw.ellipse(body_box, outline=color_rgb, width=3)

    # ── Construcción de UI ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Canvas que ocupa TODA la ventana para dibujar cámara + overlays
        self.canvas = tkinter.Canvas(
            self,
            width=self.WIN_W,
            height=self.WIN_H,
            bg="#1A1A2E",
            highlightthickness=0,
        )
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # ── Status label en la parte superior ─────────────────────────────────
        self.lbl_status = ctk.CTkLabel(
            self,
            text="Posiciona tu rostro en la silueta",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=self.TEXT_COLOR,
            fg_color="#2A2A3E",
            corner_radius=16,
            height=36,
            width=360,
        )
        self.lbl_status.place(relx=0.5, y=30, anchor="n")

        # ── Contador de intentos ──────────────────────────────────────────────
        self.lbl_attempts = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=self.MUTED,
            fg_color="transparent",
        )
        self.lbl_attempts.place(relx=0.5, y=72, anchor="n")

        # ── Botón de retroceso (flecha) en la parte inferior ─────────────────
        self.btn_back = ctk.CTkButton(
            self,
            text="←",
            font=ctk.CTkFont(size=28, weight="bold"),
            fg_color="#3A3A50",
            hover_color="#4A4A60",
            text_color="#FFFFFF",
            width=56, height=56,
            corner_radius=28,
            command=self._go_standby,
        )
        self.btn_back.place(x=80, rely=0.94, anchor="center")

        # ── Botón DEV simular éxito (solo desarrollo) ────────────────────
        self.btn_dev = ctk.CTkButton(
            self,
            text="✓ Simular",
            font=ctk.CTkFont(size=14),
            fg_color="#2A3A2A",
            hover_color="#3A4A3A",
            text_color="#A5D6A7",
            width=100, height=40,
            corner_radius=20,
            command=self._dev_simulate_success,
        )
        self.btn_dev.place(x=400, rely=0.94, anchor="center")

        # ── Overlay de éxito (oculto por defecto) ────────────────────────────
        self.success_frame = ctk.CTkFrame(
            self,
            fg_color=self.SUCCESS,
            corner_radius=20,
            width=420,
            height=260,
        )
        # No se muestra aún — se coloca con .place() al detectar éxito

        # Contenido del overlay de éxito
        self.lbl_success_icon = ctk.CTkLabel(
            self.success_frame,
            text="✓",
            font=ctk.CTkFont(size=52, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_icon.pack(pady=(15, 2))

        self.lbl_success_title = ctk.CTkLabel(
            self.success_frame,
            text="¡Acceso concedido!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_title.pack(pady=(0, 4))

        self.lbl_success_name = ctk.CTkLabel(
            self.success_frame,
            text="—",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_name.pack(pady=(0, 2))

        self.lbl_success_matricula = ctk.CTkLabel(
            self.success_frame,
            text="Matrícula —",
            font=ctk.CTkFont(size=15),
            text_color="#E8F5E9",
            fg_color="transparent",
        )
        self.lbl_success_matricula.pack(pady=(0, 2))

        self.lbl_success_locker = ctk.CTkLabel(
            self.success_frame,
            text="Casillero —",
            font=ctk.CTkFont(size=16),
            text_color="#E8F5E9",
            fg_color="transparent",
        )
        self.lbl_success_locker.pack(pady=(0, 2))

        self.lbl_success_fecha = ctk.CTkLabel(
            self.success_frame,
            text="—",
            font=ctk.CTkFont(size=14),
            text_color="#C8E6C9",
            fg_color="transparent",
        )
        self.lbl_success_fecha.pack(pady=(0, 2))

        self.lbl_countdown = ctk.CTkLabel(
            self.success_frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#A5D6A7",
            fg_color="transparent",
        )
        self.lbl_countdown.pack(pady=(2, 8))

    # ── Captura de video en background ────────────────────────────────────────

    def _camera_loop(self) -> None:
        """Thread worker que captura frames y detecta rostros."""
        import time

        if not self.face_manager:
            logger.error("FaceManager no inicializado")
            self.after(0, self._show_camera_error, "Gestor de reconocimiento facial no disponible")
            return

        if not self.face_manager.initialized:
            logger.warning("Intentando inicializar cámara...")
            init_ok = False
            for attempt in range(1, 4):
                if self.face_manager.initialize():
                    init_ok = True
                    break
                logger.warning(f"Inicialización de cámara falló (intento {attempt}/3)")
                try:
                    self.face_manager.release()
                except Exception:
                    pass
                time.sleep(0.35 * attempt)

            if not init_ok:
                logger.error("✗ No se pudo inicializar cámara")
                error_msg = "No se pudo acceder a la cámara. Verifica:\n1. Cámara conectada\n2. Permisos de acceso\n3. Configuración en raspi-config"
                self.after(0, self._show_camera_error, error_msg)
                return

        logger.info("✓ Camera loop iniciado correctamente")
        frame_count = 0

        try:
            while self._camera_running:
                frame, faces = self.face_manager.detect_faces_in_frame()

                if frame is None:
                    time.sleep(0.05)
                    continue

                frame_count += 1
                self._camera_frame = frame
                self._detected_faces = faces
                self._face_detected = len(faces) > 0
                self._frame_counter += 1

                if self._success_shown:
                    time.sleep(0.066)
                    continue

                if faces:
                    self._stable_face_frames += 1
                    self._last_seen_face_box = faces[0].get("box")
                else:
                    self._stable_face_frames = 0
                    self._last_seen_face_box = None

                enough_frames = self._frame_counter % self.RECOGNITION_INTERVAL_FRAMES == 0
                enough_stability = self._stable_face_frames >= self.STABLE_FACE_FRAMES
                cooldown_ok = (time.time() - self._last_recognition_ts) >= self.RECOGNITION_COOLDOWN_SECONDS

                if faces and enough_frames and enough_stability and cooldown_ok:
                    self._last_recognition_ts = time.time()
                    try:
                        user_data = self._recognize_current_face(frame, faces)
                        if user_data:
                            self.after(0, self.on_face_match, user_data)
                        else:
                            self.after(0, self.on_face_no_match)
                    except Exception as recognition_error:
                        logger.error(f"Error durante autenticación facial: {recognition_error}")
                        self.after(0, self.on_face_no_match)

                try:
                    self._update_camera_display(frame, faces)
                except Exception as e:
                    logger.error(f"Error actualizando display: {e}")

                time.sleep(0.066)

                if frame_count % 30 == 0:
                    logger.info(f"Camera loop: {frame_count} frames, {len(faces)} rostros")

        except Exception as e:
            logger.error(f"Error en camera loop: {e}")
            self.after(0, self._show_camera_error, f"Error crítico: {str(e)}")
        finally:
            if self.face_manager:
                try:
                    self.face_manager.release()
                except:
                    pass
            logger.info(f"Camera loop finalizado. Total: {frame_count}")

    def _update_camera_display(self, frame: np.ndarray, faces: list) -> None:
        """Dibuja el frame de cámara a pantalla completa con silueta superpuesta."""
        try:
            # Picamera2 "RGB888" retorna BGR en memoria — convertir a RGB para PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Redimensionar manteniendo aspect ratio (no estirar)
            h, w = frame_rgb.shape[:2]
            scale = min(self.WIN_W / w, self.WIN_H / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            # Redimensionar
            frame_resized = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Crear canvas con fondo negro y centrar la imagen
            canvas = np.zeros((self.WIN_H, self.WIN_W, 3), dtype=np.uint8)
            y_offset = (self.WIN_H - new_h) // 2
            x_offset = (self.WIN_W - new_w) // 2
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_resized
            
            # Convertir a PIL directamente (sin conversión de canales)
            pil_image = Image.fromarray(canvas, mode="RGB").convert("RGBA")

            # Superponer la máscara de silueta semitransparente
            pil_image = Image.alpha_composite(pil_image, self._silhouette_mask)

            # Dibujar contorno de silueta: rojo si no hay rostro, verde si sí
            draw = ImageDraw.Draw(pil_image)
            if len(faces) > 0:
                self._draw_silhouette_outline(draw, self.SILHOUETTE_FACE_OK)
            else:
                self._draw_silhouette_outline(draw, self.SILHOUETTE_NO_FACE)

            # Convertir a RGB para PhotoImage
            pil_rgb = pil_image.convert("RGB")

            import tempfile
            ppm_path = "/tmp/locker_scan.ppm"
            try:
                pil_rgb.save(ppm_path, "PPM")
                new_photo = tkinter.PhotoImage(file=ppm_path)
                self._photo_image = new_photo
                self.after(0, self._set_camera_image)
            except Exception as e:
                logger.warning(f"Error creando PhotoImage: {e}")

        except Exception as e:
            logger.error(f"Error actualizando display: {e}")

    def _show_camera_error(self, error_msg: str) -> None:
        """Muestra un mensaje de error cuando la cámara no está disponible."""
        logger.error(f"Camera Error: {error_msg}")
        
        # Mostrar error en el canvas
        self.canvas.delete("all")
        self.canvas.create_rectangle(
            0, 0, self.WIN_W, self.WIN_H,
            fill=self.BG_COLOR,
            outline=self.BG_COLOR
        )
        
        # Título de error
        self.canvas.create_text(
            self.WIN_W // 2, 150,
            text="✗ Error de Cámara",
            font=("Arial", 24, "bold"),
            fill="#FF6B6B",
            justify="center"
        )
        
        # Mensaje de error detallado
        self.canvas.create_text(
            self.WIN_W // 2, 300,
            text=error_msg,
            font=("Arial", 14),
            fill="#FFFFFF",
            justify="center",
            width=360
        )
        
        # Instrucción
        self.canvas.create_text(
            self.WIN_W // 2, 550,
            text="Presiona ← para volver al inicio",
            font=("Arial", 12),
            fill="#CCCCCC",
            justify="center"
        )
        
        # Actualizar status label
        self.lbl_status.configure(
            text="✗ Cámara no disponible",
            text_color="#FF6B6B"
        )
        
        # Asegurarse de que los botones estén visibles
        self.btn_back.place(x=80, rely=0.94, anchor="center")
        self.btn_dev.place_forget()  # Ocultar botón de simulación en caso de error


    def _set_camera_image(self) -> None:
        """Pone la imagen en el canvas (main thread)."""
        try:
            if self._photo_image is not None:
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self._photo_image)
                self.canvas.image = self._photo_image

                # Actualizar texto del status según detección
                if not self._success_shown:
                    if self._face_detected:
                        self.lbl_status.configure(
                            text="Rostro detectado — autenticando…",
                            text_color="#A5D6A7",
                        )
                    else:
                        self.lbl_status.configure(
                            text="Posiciona tu rostro en la silueta",
                            text_color="#FFFFFF",
                        )
        except Exception as e:
            logger.error(f"Error mostrando imagen: {e}")

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """Inicia captura de vídeo cuando la pantalla se activa."""
        self._attempts = 0
        self._success_shown = False
        self._user_data = None
        self._frame_counter = 0
        self._stable_face_frames = 0
        self._last_recognition_ts = 0.0
        self._last_seen_face_box = None
        self.lbl_status.configure(text="Iniciando cámara…", text_color="#FFFFFF")
        self.lbl_attempts.configure(text="")
        self.success_frame.place_forget()
        self.btn_back.place(x=80, rely=0.94, anchor="center")
        self.btn_dev.place(x=400, rely=0.94, anchor="center")

        if not self._camera_running:
            self._camera_running = True
            self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
            self._camera_thread.start()
            self.after(1000, lambda: self.lbl_status.configure(
                text="Posiciona tu rostro en la silueta", text_color="#FFFFFF"
            ))

    def on_hide(self) -> None:
        """Detiene captura de vídeo al salir de la pantalla."""
        self._camera_running = False
        if self._camera_thread:
            self._camera_thread.join(timeout=2.0)
        if self._return_job:
            self.after_cancel(self._return_job)
            self._return_job = None
        logger.info("Camera capture detenido")

    def on_face_match(self, user_data: dict) -> None:
        """Muestra el overlay verde de éxito con los datos del usuario."""
        self._success_shown = True
        self._user_data = user_data

        self.lbl_status.configure(text="✓ Acceso concedido", text_color="#A5D6A7")
        self.lbl_attempts.configure(text="")

        # Llenar datos en el overlay
        self.lbl_success_name.configure(text=user_data.get("nombre", "—"))
        self.lbl_success_matricula.configure(
            text=f"Matrícula  {user_data.get('matricula', '—')}"
        )
        self.lbl_success_locker.configure(
            text=f"Casillero  {user_data.get('locker_numero', '—')}"
        )
        self.lbl_success_fecha.configure(text=user_data.get("fecha", "—"))

        # Mostrar overlay verde
        self.success_frame.place(relx=0.5, rely=0.75, anchor="center")
        self.btn_back.place_forget()
        self.btn_dev.place_forget()

        # Iniciar countdown
        self._start_countdown(self.DISPLAY_SECONDS)

    def on_face_no_match(self) -> None:
        """Llamado cuando no hay match."""
        if self._success_shown:
            return

        self._attempts += 1
        self.lbl_attempts.configure(
            text=f"Intentos: {self._attempts} / {self.MAX_ATTEMPTS}"
        )
        if self._attempts >= self.MAX_ATTEMPTS:
            self.lbl_status.configure(text="✗ Acceso denegado", text_color="#EF9A9A")
            self.after(2500, self._go_standby)
        else:
            self.lbl_status.configure(
                text=f"Rostro no reconocido ({self._attempts}/{self.MAX_ATTEMPTS})",
                text_color="#FFCC80",
            )

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _start_countdown(self, seconds: int) -> None:
        if self._return_job is not None:
            self.after_cancel(self._return_job)

        if seconds <= 0:
            self._go_standby()
            return

        self.lbl_countdown.configure(text=f"Volviendo al inicio en {seconds} s…")
        self._return_job = self.after(1000, self._start_countdown, seconds - 1)

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _go_standby(self) -> None:
        from ui.locker_screen.standby_screen import StandbyScreen
        self.controller.show_frame(StandbyScreen)

    def _recognize_current_face(self, frame: np.ndarray, faces: list) -> Optional[dict]:
        if not faces or not self.face_manager:
            return None

        face_box = faces[0].get("box")
        if not face_box:
            return None

        probe_embedding = self.face_manager.get_embedding(frame, face_box)
        if probe_embedding is None:
            logger.debug("No se pudo extraer embedding para autenticación")
            return None

        candidates = self._load_active_face_encodings()
        if not candidates:
            logger.warning("No hay encodings activos en BD para autenticar")
            return None

        best_candidate = None
        best_distance = 999.0
        for candidate in candidates:
            stored_vec = candidate.get("vector_np")
            if stored_vec is None:
                continue
            distance = self.face_manager.embedding_extractor.compare_embeddings(
                probe_embedding.astype(np.float32, copy=False),
                stored_vec,
            )
            if distance < best_distance:
                best_distance = distance
                best_candidate = candidate

        if not best_candidate:
            return None

        threshold = self._threshold_for_model(best_candidate.get("modelo"))
        logger.info(
            "Auth facial: mejor candidato id=%s distancia=%.4f umbral=%.4f modelo=%s",
            best_candidate.get("idUsuario"),
            best_distance,
            threshold,
            best_candidate.get("modelo"),
        )

        if best_distance > threshold:
            self._register_access_attempt(best_candidate.get("idLockerAsignado"), permitted=False)
            return None

        self._register_access_attempt(best_candidate.get("idLockerAsignado"), permitted=True)
        full_name = " ".join(
            p for p in [
                best_candidate.get("nombre"),
                best_candidate.get("apPaterno"),
                best_candidate.get("apMaterno"),
            ] if p
        ).strip()

        return {
            "nombre": full_name or "Usuario",
            "matricula": best_candidate.get("matricula") or "—",
            "locker_numero": best_candidate.get("idLocker") or "Sin asignar",
            "fecha": datetime.now().strftime("%d/%m/%Y  %H:%M"),
        }

    def _threshold_for_model(self, model_name: Optional[str]) -> float:
        default_threshold = float(FACE_RECOGNITION_CONFIG.get("distance_threshold", 0.6))
        if (model_name or "").startswith("fallback"):
            return 0.95
        return default_threshold

    def _load_active_face_encodings(self) -> list[dict]:
        rows = fetch_all(
            """
            SELECT
                e.idUsuario,
                e.vector,
                e.dimension,
                e.vectorDtype,
                e.modelo,
                u.nombre,
                u.apPaterno,
                u.apMaterno,
                u.matricula,
                a.idLockerAsignado,
                l.idLocker
            FROM encoding e
            JOIN usuarios u
                ON u.idUsuario = e.idUsuario
            LEFT JOIN asignacion_locker a
                ON a.idUsuario = u.idUsuario AND a.estado = 'activo'
            LEFT JOIN lockers l
                ON l.idLocker = a.idLocker
            WHERE e.estado = 'activo'
              AND u.estado = 'activo'
            """
        )

        parsed: list[dict] = []
        for row in rows:
            raw = row.get("vector")
            dim = int(row.get("dimension") or 128)
            dtype_name = (row.get("vectorDtype") or "float32").strip().lower()
            dtype = np.float64 if dtype_name == "float64" else np.float32
            if raw is None:
                continue

            vector_np = np.frombuffer(raw, dtype=dtype)
            if vector_np.size != dim:
                logger.warning(
                    "Encoding inválido usuario=%s esperado=%s real=%s",
                    row.get("idUsuario"),
                    dim,
                    vector_np.size,
                )
                continue

            if dtype != np.float32:
                vector_np = vector_np.astype(np.float32)

            row["vector_np"] = vector_np
            parsed.append(row)

        return parsed

    def _register_access_attempt(self, locker_assignment_id: Optional[int], permitted: bool) -> None:
        try:
            now = datetime.now()
            expires_at = now + (timedelta(minutes=5) if permitted else timedelta(minutes=1))
            execute(
                """
                INSERT INTO historial_accesos
                    (idLockerAsignado, accesoPermitido, motivo, fechaExpiracion)
                VALUES (?, ?, ?, ?)
                """,
                (
                    locker_assignment_id,
                    "si" if permitted else "no",
                    "facial",
                    expires_at.strftime("%Y-%m-%dT%H:%M:%S"),
                ),
            )
        except Exception as e:
            logger.warning(f"No se pudo registrar historial de acceso: {e}")

    def _dev_simulate_success(self) -> None:
        """Solo para desarrollo: simula un acceso exitoso."""
        dummy_user = {
            "nombre":        "Juan Pérez López",
            "locker_numero": 3,
            "fecha":         datetime.now().strftime("%d/%m/%Y  %H:%M"),
        }
        self.on_face_match(dummy_user)
