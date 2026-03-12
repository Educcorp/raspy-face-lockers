"""
RegisterUserScreen – Wizard de registro de usuario con captura facial.

Flujo (ventana por ventana, 480×800 px, touch-friendly):
  Paso 1 → Datos básicos (nombre, apellidos, matrícula, email, tel)
  Paso 2 → Tipo de usuario + unidad académica
  Paso 3 → PIN (4 dígitos con teclado numérico grande)
  Paso 4 → Captura facial (cámara + silueta guía, igual al locker físico)
            Al capturar un perfil frontal se pasa al siguiente.
            Botón "Registrar" guarda todo en la DB y llega al Paso 5.
  Paso 5 → Confirmación + opción de volver al dashboard

Seguridad del PIN: se almacena como SHA-256 hex (64 chars), igual que el locker.
Los vectores faciales se serializan con numpy tobytes() en la tabla encoding.
"""

import hashlib
import threading
import tkinter as tk
from typing import Optional
import logging

import customtkinter as ctk
from PIL import Image, ImageDraw

from database.connection import execute, fetch_all, fetch_one
from ui.admin_app import PALETTE

logger = logging.getLogger(__name__)

# cv2 y numpy se importan de forma lazy en _Step4FaceCapture para no bloquear
# si OpenCV no está instalado en el entorno de desarrollo.
try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    cv2 = None       # type: ignore
    np  = None       # type: ignore

WIN_W = 480
WIN_H = 800

# ── Constantes visuales (misma paleta que ScanningScreen) ────────────────────
SILO_NO_FACE = (200, 80,  80,  160)
SILO_OK_FACE = (90,  180, 90,  160)


# ══════════════════════════════════════════════════════════════════════════════
# Pantalla principal (contenedor del wizard)
# ══════════════════════════════════════════════════════════════════════════════

class RegisterUserScreen(ctk.CTkFrame):
    """
    Pantalla de registro de usuario.
    Contiene el wizard de múltiples pasos.
    """

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.controller = controller
        self._step_frames: list[ctk.CTkFrame] = []
        self._data: dict = {}  # datos recopilados a lo largo del wizard
        self._build_wizard()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build_wizard(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        steps = [
            _Step1BasicData,
            _Step2TypeUnit,
            _Step3PIN,
            _Step4FaceCapture,
            _Step5Confirm,
        ]
        self._step_frames = []
        for StepClass in steps:
            frame = StepClass(self, wizard=self)
            self._step_frames.append(frame)
            frame.grid(row=0, column=0, sticky="nsew")

        self._goto_step(0)

    # ── Navegación interna del wizard ─────────────────────────────────────────

    def _goto_step(self, idx: int) -> None:
        self._current_step = idx
        frame = self._step_frames[idx]
        frame.tkraise()
        if hasattr(frame, "on_enter"):
            frame.on_enter(self._data)

    def next_step(self, partial_data: dict) -> None:
        self._data.update(partial_data)
        self._goto_step(self._current_step + 1)

    def prev_step(self) -> None:
        if self._current_step > 0:
            self._goto_step(self._current_step - 1)

    def finish(self) -> None:
        """Vuelve al dashboard y reinicia el wizard."""
        self._data = {}
        from ui.admin.dashboard import DashboardScreen
        self.controller.show_frame(DashboardScreen)

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def on_show(self, **_kwargs) -> None:
        self._data = {}
        self._goto_step(0)

    def on_hide(self) -> None:
        # Detener cámara si estaba activa
        face_step: _Step4FaceCapture = self._step_frames[3]  # type: ignore
        face_step.stop_camera()


# ══════════════════════════════════════════════════════════════════════════════
# Paso 1 – Datos básicos
# ══════════════════════════════════════════════════════════════════════════════

class _Step1BasicData(ctk.CTkFrame):

    def __init__(self, parent, wizard: RegisterUserScreen):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.wizard = wizard
        self._vars: dict[str, tk.StringVar] = {
            k: tk.StringVar() for k in
            ["nombre", "apPaterno", "apMaterno", "matricula", "emailInst", "tel"]
        }
        self._build()

    def _build(self) -> None:
        _wizard_header(self, "Paso 1 de 5", "Datos básicos",
                       back_cmd=lambda: self.wizard.controller.show_frame(
                           __import__("ui.admin.dashboard",
                                      fromlist=["DashboardScreen"]).DashboardScreen
                       ))
        scroll = _scroll(self)

        fields = [
            ("nombre",    "Nombre *"),
            ("apPaterno", "Apellido paterno *"),
            ("apMaterno", "Apellido materno"),
            ("matricula", "Matrícula *"),
            ("emailInst", "Correo institucional *"),
            ("tel",       "Teléfono"),
        ]
        self._entries: dict[str, ctk.CTkEntry] = {}
        for key, label in fields:
            _field_label(scroll, label)
            e = ctk.CTkEntry(scroll, textvariable=self._vars[key],
                             font=ctk.CTkFont(size=16),
                             fg_color=PALETTE["CARD"],
                             border_color=PALETTE["BORDER"],
                             text_color=PALETTE["TEXT"], height=50)
            e.pack(fill="x", padx=4, pady=(0, 2))
            self._entries[key] = e

        self.lbl_err = ctk.CTkLabel(scroll, text="",
                                    font=ctk.CTkFont(size=13),
                                    text_color=PALETTE["DANGER"],
                                    fg_color="transparent")
        self.lbl_err.pack(pady=4)

        _big_btn(scroll, "Siguiente →", self._next)

    def _next(self) -> None:
        nombre    = self._vars["nombre"].get().strip()
        apPaterno = self._vars["apPaterno"].get().strip()
        mat       = self._vars["matricula"].get().strip()
        email     = self._vars["emailInst"].get().strip()

        if not all([nombre, apPaterno, mat, email]):
            self.lbl_err.configure(text="Por favor completa los campos requeridos (*)")
            return
        if not mat.isdigit():
            self.lbl_err.configure(text="La matrícula debe ser numérica")
            return
        self.lbl_err.configure(text="")
        self.wizard.next_step({
            "nombre":    nombre,
            "apPaterno": apPaterno,
            "apMaterno": self._vars["apMaterno"].get().strip() or None,
            "matricula": int(mat),
            "emailInst": email,
            "tel":       self._vars["tel"].get().strip() or None,
        })

    def on_enter(self, data: dict) -> None:
        # Restaurar si hay datos previos
        for k, var in self._vars.items():
            var.set(str(data.get(k, "") or ""))
        self.lbl_err.configure(text="")


# ══════════════════════════════════════════════════════════════════════════════
# Paso 2 – Tipo de usuario y unidad académica
# ══════════════════════════════════════════════════════════════════════════════

class _Step2TypeUnit(ctk.CTkFrame):

    def __init__(self, parent, wizard: RegisterUserScreen):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.wizard = wizard
        self._tipo_var   = tk.StringVar()
        self._unidad_var = tk.StringVar()
        self._tipos:    list[dict] = []
        self._unidades: list[dict] = []
        self._build()

    def _build(self) -> None:
        _wizard_header(self, "Paso 2 de 5", "Tipo y unidad",
                       back_cmd=self.wizard.prev_step)

        scroll = _scroll(self)

        _field_label(scroll, "Tipo de usuario *")
        self._tipo_menu = ctk.CTkOptionMenu(
            scroll, variable=self._tipo_var, values=["…"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=16), height=50,
        )
        self._tipo_menu.pack(fill="x", padx=4, pady=(0, 10))

        _field_label(scroll, "Unidad académica *")
        self._unidad_menu = ctk.CTkOptionMenu(
            scroll, variable=self._unidad_var, values=["…"],
            fg_color=PALETTE["CARD"], button_color=PALETTE["ACCENT"],
            button_hover_color=PALETTE["ACCENT_HOVER"], text_color=PALETTE["TEXT"],
            font=ctk.CTkFont(size=16), height=50,
        )
        self._unidad_menu.pack(fill="x", padx=4, pady=(0, 10))

        self.lbl_err = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=13),
                                    text_color=PALETTE["DANGER"],
                                    fg_color="transparent")
        self.lbl_err.pack(pady=4)
        _big_btn(scroll, "Siguiente →", self._next)

    def on_enter(self, data: dict) -> None:
        self._tipos = fetch_all(
            "SELECT idTipoUsuario, nombreTipoUsuario FROM tipo_usuarios WHERE estado='activo' ORDER BY nombreTipoUsuario"
        )
        self._unidades = fetch_all(
            "SELECT idUnidadAcademica, nombreUnidadAcademica FROM unidad_academica WHERE estado='activo' ORDER BY nombreUnidadAcademica"
        )
        tipo_names   = [t["nombreTipoUsuario"]    for t in self._tipos]
        unidad_names = [u["nombreUnidadAcademica"] for u in self._unidades]

        self._tipo_menu.configure(values=tipo_names or ["Sin tipos"])
        self._unidad_menu.configure(values=unidad_names or ["Sin unidades"])

        if tipo_names:
            self._tipo_var.set(data.get("tipo_nombre") or tipo_names[0])
        if unidad_names:
            self._unidad_var.set(data.get("unidad_nombre") or unidad_names[0])
        self.lbl_err.configure(text="")

    def _next(self) -> None:
        tipo_n   = self._tipo_var.get()
        unidad_n = self._unidad_var.get()
        tipo_id  = next((t["idTipoUsuario"]     for t in self._tipos   if t["nombreTipoUsuario"] == tipo_n),   None)
        unidad_id = next((u["idUnidadAcademica"] for u in self._unidades if u["nombreUnidadAcademica"] == unidad_n), None)

        if not tipo_id or not unidad_id:
            self.lbl_err.configure(text="Selecciona tipo y unidad válidos")
            return
        self.lbl_err.configure(text="")
        self.wizard.next_step({
            "idTipoUsuario":      tipo_id,
            "idUnidadAcademica":  unidad_id,
            "tipo_nombre":        tipo_n,
            "unidad_nombre":      unidad_n,
        })


# ══════════════════════════════════════════════════════════════════════════════
# Paso 3 – PIN numérico (teclado táctil grande)
# ══════════════════════════════════════════════════════════════════════════════

class _Step3PIN(ctk.CTkFrame):

    MAX_DIGITS = 4

    def __init__(self, parent, wizard: RegisterUserScreen):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.wizard = wizard
        self._pin = ""
        self._build()

    def _build(self) -> None:
        _wizard_header(self, "Paso 3 de 5", "Establece un PIN",
                       back_cmd=self.wizard.prev_step)

        # Instrucción
        ctk.CTkLabel(self, text="El usuario usará este PIN de 4 dígitos\npara abrir su locker.",
                     font=ctk.CTkFont(size=14),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent", justify="center").pack(pady=(10, 4))

        # Display del PIN
        self.lbl_pin = ctk.CTkLabel(
            self, text="_ _ _ _",
            font=ctk.CTkFont(size=38, weight="bold"),
            text_color=PALETTE["ACCENT"], fg_color=PALETTE["CARD"],
            corner_radius=14, height=70, width=260,
        )
        self.lbl_pin.pack(pady=(8, 16))

        self.lbl_err = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13),
                                    text_color=PALETTE["DANGER"],
                                    fg_color="transparent")
        self.lbl_err.pack()

        # Teclado numérico 3×4
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(pady=8)
        btn_cfg = dict(
            font=ctk.CTkFont(size=26, weight="bold"),
            fg_color=PALETTE["CARD"], hover_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"],
            width=120, height=80, corner_radius=14,
        )
        for i, label in enumerate(["1","2","3","4","5","6","7","8","9","⌫","0","OK"]):
            r, c = divmod(i, 3)
            if label == "⌫":
                cmd = self._backspace
                cfg = {**btn_cfg, "text_color": PALETTE["DANGER"]}
            elif label == "OK":
                cmd = self._confirm
                cfg = {**btn_cfg, "fg_color": PALETTE["ACCENT"],
                       "hover_color": PALETTE["ACCENT_HOVER"],
                       "text_color": PALETTE["WHITE"]}
            else:
                cmd = lambda d=label: self._digit(d)
                cfg = btn_cfg
            ctk.CTkButton(pad, text=label, command=cmd, **cfg).grid(
                row=r, column=c, padx=6, pady=6)

    def _digit(self, d: str) -> None:
        if len(self._pin) < self.MAX_DIGITS:
            self._pin += d
            self._refresh()

    def _backspace(self) -> None:
        self._pin = self._pin[:-1]
        self._refresh()

    def _refresh(self) -> None:
        display = "  ".join(["●" if i < len(self._pin) else "_"
                              for i in range(self.MAX_DIGITS)])
        self.lbl_pin.configure(text=display)

    def _confirm(self) -> None:
        if len(self._pin) < self.MAX_DIGITS:
            self.lbl_err.configure(text=f"Ingresa {self.MAX_DIGITS} dígitos")
            return
        # Hashear PIN con SHA-256
        pin_hash = hashlib.sha256(self._pin.encode()).hexdigest()
        self.lbl_err.configure(text="")
        self.wizard.next_step({"pin_hash": pin_hash})

    def on_enter(self, _data: dict) -> None:
        self._pin = ""
        self._refresh()
        self.lbl_err.configure(text="")


# ══════════════════════════════════════════════════════════════════════════════
# Paso 4 – Captura facial (cámara con silueta guía)
# ══════════════════════════════════════════════════════════════════════════════

class _Step4FaceCapture(ctk.CTkFrame):
    """
    Paso de captura facial. Muestra la cámara en tiempo real
    con la silueta guía. Al presionar "Capturar" se extrae el
    embedding y se almacena temporalmente en self.wizard._data.
    El botón "Guardar y Registrar" inserta el usuario + encoding en la DB.
    """

    def __init__(self, parent, wizard: RegisterUserScreen):
        super().__init__(parent, fg_color="#1A1A2E", corner_radius=0)
        self.wizard = wizard

        self._camera_running = False
        self._camera_thread: Optional[threading.Thread] = None
        self._current_frame: Optional[np.ndarray] = None
        self._detected_faces: list = []
        self._photo_ref = None
        self._captured_embedding: Optional[np.ndarray] = None
        self._detector = None
        self._face_mgr = None

        self._silhouette_mask = self._make_silhouette()
        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        _wizard_header(self, "Paso 4 de 5", "Captura facial",
                       back_cmd=self.wizard.prev_step,
                       bg="#1A1A2E", text_color=PALETTE["WHITE"])

        # Canvas para el feed de la cámara
        self.canvas = tk.Canvas(
            self, width=WIN_W, height=600,
            bg="#1A1A2E", highlightthickness=0,
        )
        self.canvas.pack()

        # Status
        self.lbl_status = ctk.CTkLabel(
            self, text="Posiciona tu rostro en la silueta",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=PALETTE["WHITE"], fg_color="#2A2A3E",
            corner_radius=12, height=38, width=360,
        )
        self.lbl_status.place(relx=0.5, y=90, anchor="n")

        # Perfil badge
        self.lbl_profile = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["ACCENT"], fg_color="transparent",
        )
        self.lbl_profile.place(relx=0.5, y=134, anchor="n")

        # Botones
        btn_row = ctk.CTkFrame(self, fg_color=PALETTE["CARD"],
                               corner_radius=0, height=90)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="Capturar",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"], height=60, corner_radius=12,
            command=self._capture,
        ).grid(row=0, column=0, padx=(12, 6), pady=15, sticky="ew")

        self.btn_save = ctk.CTkButton(
            btn_row, text="Registrar",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PALETTE["SUCCESS"] if "SUCCESS" in PALETTE else "#27ae60",
            hover_color="#1e8449",
            text_color=PALETTE["WHITE"], height=60, corner_radius=12,
            command=self._save_user,
            state="disabled",
        )
        self.btn_save.grid(row=0, column=1, padx=(6, 12), pady=15, sticky="ew")

    # ── Silueta ───────────────────────────────────────────────────────────────

    def _make_silhouette(self) -> Image.Image:
        mask = Image.new("RGBA", (WIN_W, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(mask)
        draw.rectangle([(0, 0), (WIN_W, 600)], fill=(0, 0, 0, 80))
        cx, cy = WIN_W // 2, 280
        draw.ellipse([cx-95, cy-150, cx+95, cy+90], fill=(0, 0, 0, 0))
        draw.ellipse([cx-160, cy+90, cx+160, cy+230], fill=(0, 0, 0, 0))
        return mask

    def _draw_outline(self, draw: ImageDraw.Draw, color: tuple) -> None:
        cx, cy = WIN_W // 2, 280
        draw.ellipse([cx-95, cy-150, cx+95, cy+90],
                     outline=color[:3], width=3)
        draw.ellipse([cx-160, cy+90, cx+160, cy+230],
                     outline=color[:3], width=3)

    # ── Cámara ────────────────────────────────────────────────────────────────

    def _start_camera(self) -> None:
        if self._camera_running:
            return
        if not _CV2_AVAILABLE:
            self.lbl_status.configure(text="(!) OpenCV no instalado (pip install opencv-python)")
            logger.error("OpenCV not available")
            return
        try:
            from core.face_recognition import FaceRecognitionManager
            logger.info("Inicializando FaceRecognitionManager para admin...")
            self._face_mgr = FaceRecognitionManager()
            logger.info(f"Backend seleccionado: {self._face_mgr.backend_type}")
            
            if not self._face_mgr.initialize():
                error_msg = "No se pudo inicializar la cámara. Verifica:\n1. Cámara conectada\n2. Permisos de acceso\n3. Configuración en raspi-config"
                logger.error(f"FaceRecognitionManager initialization failed: {error_msg}")
                self.lbl_status.configure(text=f"✗ Cámara no disponible")
                self._face_mgr = None
                return
                
            logger.info("✓ FaceRecognitionManager inicializado correctamente")
            self._detector = self._face_mgr.face_detector
        except Exception as exc:
            logger.error(f"Error al inicializar cámara: {exc}", exc_info=True)
            self.lbl_status.configure(text=f"(!) Error: {str(exc)[:50]}")
            return

        self._camera_running = True
        self._camera_thread = threading.Thread(
            target=self._camera_loop, daemon=True
        )
        self._camera_thread.start()
        logger.info("Camera thread started")
        self._update_canvas()

    def stop_camera(self) -> None:
        self._camera_running = False
        if self._face_mgr is not None:
            try:
                self._face_mgr.release()
                logger.info("Camera released")
            except Exception as e:
                logger.error(f"Error releasing camera: {e}")
            self._face_mgr = None

    def _camera_loop(self) -> None:
        import time
        logger.info("Camera loop started")
        while self._camera_running:
            try:
                if self._face_mgr is None:
                    time.sleep(0.1)
                    break
                frame, faces = self._face_mgr.detect_faces_in_frame()
                if frame is not None:
                    self._current_frame = frame
                    self._detected_faces = faces
            except Exception as e:
                logger.error(f"Error en camera_loop: {e}")
                break
            time.sleep(0.033)
        logger.info("Camera loop ended")

    def _detect_faces(self, frame) -> list:
        if not _CV2_AVAILABLE:
            return []
        if self._detector and hasattr(self._detector, "detect"):
            try:
                return self._detector.detect(frame)
            except Exception:
                pass
        # Fallback: Haar cascade
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = cascade.detectMultiScale(gray, 1.1, 4)
        return [{"box": (x, y, w, h)} for (x, y, w, h) in faces] if len(faces) > 0 else []

    def _update_canvas(self) -> None:
        if not self._camera_running:
            return

        if self._current_frame is not None:
            frame = self._current_frame.copy()
            
            # Redimensionar manteniendo aspect ratio (no estirar)
            h, w = frame.shape[:2]
            scale = min(WIN_W / w, 600 / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            # Redimensionar
            frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Crear canvas con fondo negro y centrar la imagen
            canvas = np.zeros((600, WIN_W, 3), dtype=np.uint8)
            y_offset = (600 - new_h) // 2
            x_offset = (WIN_W - new_w) // 2
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_resized
            
            # Convertir BGR → RGB
            frame_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb).convert("RGBA")

            has_face = len(self._detected_faces) > 0
            outline_color = SILO_OK_FACE if has_face else SILO_NO_FACE

            # Silueta overlay
            overlay = self._silhouette_mask.copy()
            draw = ImageDraw.Draw(overlay)
            self._draw_outline(draw, outline_color)
            img = Image.alpha_composite(img, overlay)

            from PIL import ImageTk
            self._photo_ref = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw",
                                     image=self._photo_ref)

            # Status
            if has_face:
                self.lbl_status.configure(text="Rostro detectado — listo para capturar",
                                          text_color="#A5D6A7")
            else:
                self.lbl_status.configure(text="Posiciona tu rostro en la silueta",
                                          text_color=PALETTE["WHITE"])

        self.after(33, self._update_canvas)

    # ── Captura ───────────────────────────────────────────────────────────────

    def _capture(self) -> None:
        if not _CV2_AVAILABLE:
            self.lbl_status.configure(text="(!) OpenCV no disponible",
                                      text_color=PALETTE["DANGER"])
            return
        if self._current_frame is None:
            return
        if not self._detected_faces:
            self.lbl_status.configure(text="(!) No se detectó rostro", text_color=PALETTE["DANGER"])
            return

        frame = self._current_frame.copy()
        embedding = self._extract_embedding(frame)
        if embedding is None:
            self.lbl_status.configure(text="(!) No se pudo extraer el perfil",
                                      text_color=PALETTE["DANGER"])
            return

        self._captured_embedding = embedding
        self.lbl_status.configure(text="(OK) Perfil facial capturado",
                                  text_color="#A5D6A7")
        self.lbl_profile.configure(text="Perfil frontal listo")
        self.btn_save.configure(state="normal")

    def _extract_embedding(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Intenta extraer un vector de embedding del frame.
        Usa el FaceRecognitionManager si está disponible;
        si no, usa el parche de región normalizada como placeholder (128-dim).
        """
        try:
            from core.face_recognition import get_face_recognition_manager
            mgr = get_face_recognition_manager()
            if hasattr(mgr, "get_embedding"):
                return mgr.get_embedding(frame)
        except Exception:
            pass

        # Fallback: recortar rostro y normalizar como vector 128-dim
        if not self._detected_faces:
            return None
        face_info = self._detected_faces[0]
        box = face_info.get("box") or face_info.get("bbox")
        if box is None:
            return None
        x, y, w, h = [int(v) for v in box[:4]]
        face_crop = frame[max(0, y):y+h, max(0, x):x+w]
        if face_crop.size == 0:
            return None
        resized = cv2.resize(face_crop, (16, 8))
        vec = resized.astype(np.float32).flatten()
        # Pad/trim to 128
        if len(vec) < 128:
            vec = np.pad(vec, (0, 128 - len(vec)))
        else:
            vec = vec[:128]
        norm = np.linalg.norm(vec)
        return (vec / norm) if norm > 0 else vec

    # ── Guardar usuario completo ──────────────────────────────────────────────

    def _save_user(self) -> None:
        d = self.wizard._data
        # Insertar usuario
        try:
            user_id = execute("""
                INSERT INTO usuarios
                    (nombre, apPaterno, apMaterno, idTipoUsuario, idUnidadAcademica,
                     emailInst, tel, matricula, pin, creadoPor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                d["nombre"], d["apPaterno"], d.get("apMaterno"),
                d["idTipoUsuario"], d["idUnidadAcademica"],
                d["emailInst"], d.get("tel"),
                d["matricula"], d["pin_hash"],
            ))
        except Exception as exc:
            self.lbl_status.configure(
                text=f"Error al registrar: {exc}",
                text_color=PALETTE["DANGER"])
            return

        # Insertar encoding si se capturó
        if self._captured_embedding is not None:
            vec = self._captured_embedding
            vec_bytes = vec.tobytes()
            vec_hash  = hashlib.sha256(vec_bytes).hexdigest()
            try:
                execute("""
                    INSERT INTO encoding
                        (idUsuario, estado, vector, dimension, hashVector,
                         tipoParte, vectorDtype, modelo, modeloVersion)
                    VALUES (?, 'activo', ?, ?, ?, 'frontal', 'float32',
                            'fallback_haar', '1.0')
                """, (user_id, vec_bytes, len(vec), vec_hash))
            except Exception:
                pass  # hash duplicado u otro error — no bloquea el registro

        self.stop_camera()
        self.wizard.next_step({"saved_user_id": user_id,
                               "saved_nombre": d["nombre"]})

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def on_enter(self, data: dict) -> None:
        logger.info("=== Entrando a Step4FaceCapture (Admin) ===")
        self._captured_embedding = None
        self.btn_save.configure(state="disabled")
        self.lbl_profile.configure(text="")
        self.lbl_status.configure(text="Posiciona tu rostro en la silueta",
                                  text_color=PALETTE["WHITE"])
        logger.info("Iniciando cámara para registro...")
        self._start_camera()


# ══════════════════════════════════════════════════════════════════════════════
# Paso 5 – Confirmación
# ══════════════════════════════════════════════════════════════════════════════

class _Step5Confirm(ctk.CTkFrame):

    def __init__(self, parent, wizard: RegisterUserScreen):
        super().__init__(parent, fg_color=PALETTE["BG"], corner_radius=0)
        self.wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=0)

        ctk.CTkLabel(center, text="[OK]",
                     font=ctk.CTkFont(size=80),
                     fg_color="transparent",
                     text_color="#27ae60").pack(pady=(0, 12))

        self.lbl_msg = ctk.CTkLabel(
            center, text="",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["TEXT"], fg_color="transparent",
            wraplength=380, justify="center",
        )
        self.lbl_msg.pack(pady=8)

        ctk.CTkLabel(center, text="El usuario fue registrado exitosamente.",
                     font=ctk.CTkFont(size=14),
                     text_color=PALETTE["MUTED"],
                     fg_color="transparent").pack(pady=4)

        _big_btn(center, "Volver al inicio", self.wizard.finish)

        ctk.CTkButton(
            center, text="+  Registrar otro usuario",
            font=ctk.CTkFont(size=15),
            fg_color=PALETTE["CARD"], hover_color=PALETTE["BORDER"],
            text_color=PALETTE["TEXT"], height=50, corner_radius=12,
            command=lambda: self.wizard.on_show(),
        ).pack(fill="x", padx=24, pady=(6, 0))

    def on_enter(self, data: dict) -> None:
        nombre = data.get("saved_nombre", "")
        self.lbl_msg.configure(text=f"¡Listo, {nombre}!")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de UI compartidos entre pasos
# ══════════════════════════════════════════════════════════════════════════════

def _wizard_header(parent, step_label: str, title: str, back_cmd,
                   bg=None, text_color=None) -> ctk.CTkFrame:
    bg = bg or PALETTE["CARD"]
    text_color = text_color or PALETTE["TEXT"]
    hdr = ctk.CTkFrame(parent, fg_color=bg, height=70, corner_radius=0)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)

    ctk.CTkButton(
        hdr, text="←", width=46, height=46,
        font=ctk.CTkFont(size=22, weight="bold"),
        fg_color="transparent", hover_color=PALETTE["BORDER"],
        text_color=text_color, command=back_cmd,
    ).pack(side="left", padx=8)

    labelframe = ctk.CTkFrame(hdr, fg_color="transparent")
    labelframe.pack(side="left", padx=4)
    ctk.CTkLabel(labelframe, text=step_label, font=ctk.CTkFont(size=11),
                 text_color=PALETTE["MUTED"],
                 fg_color="transparent").pack(anchor="w")
    ctk.CTkLabel(labelframe, text=title,
                 font=ctk.CTkFont(size=19, weight="bold"),
                 text_color=text_color,
                 fg_color="transparent").pack(anchor="w")
    return hdr


def _scroll(parent) -> ctk.CTkScrollableFrame:
    sf = ctk.CTkScrollableFrame(
        parent, fg_color=PALETTE["BG"],
        scrollbar_button_color=PALETTE["BORDER"],
        scrollbar_button_hover_color=PALETTE["ACCENT"],
    )
    sf.pack(fill="both", expand=True, padx=14, pady=10)
    return sf


def _field_label(parent, text: str) -> None:
    ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=12),
                 text_color=PALETTE["MUTED"],
                 fg_color="transparent").pack(anchor="w", padx=4, pady=(10, 2))


def _big_btn(parent, text: str, command) -> None:
    ctk.CTkButton(
        parent, text=text,
        font=ctk.CTkFont(size=17, weight="bold"),
        fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
        text_color=PALETTE["WHITE"], height=58, corner_radius=14,
        command=command,
    ).pack(fill="x", padx=4, pady=18)
