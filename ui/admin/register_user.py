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
from auth.session import can_create_users, filter_assignable_user_types

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
        self._current_step = 0  # Initialize to avoid AttributeError
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
        # Llamar on_leave en el paso anterior si existe
        old_frame = self._step_frames[self._current_step]
        if hasattr(old_frame, "on_leave"):
            old_frame.on_leave()
        
        # Ir al nuevo paso
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
        if not can_create_users():
            from ui.admin.dashboard import DashboardScreen
            self.controller.show_frame(DashboardScreen)
            return
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
        self._tipos = filter_assignable_user_types(self._tipos)
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
        if not can_create_users():
            self.lbl_err.configure(text="Tu rol es de solo lectura")
            self._tipo_menu.configure(state="disabled")
            self._unidad_menu.configure(state="disabled")
            return

        self._tipo_menu.configure(state="normal")
        self._unidad_menu.configure(state="normal")
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
    con la silueta guía. Detecta el rostro automáticamente, muestra
    landmarks y captura el embedding de 128 dim (dlib) sin necesidad
    de presionar "Capturar" manualmente.

    Flujo automático:
      1. Se muestra el feed de cámara con silueta guía
      2. Al detectar un rostro estable por ~1.5 s → captura automática
      3. Se muestra confirmación + se habilita "Registrar"
      4. "Registrar" inserta usuario + encoding en la DB
    """

    STABLE_FRAMES_NEEDED = 12   # ~1.5 s a 8 fps de detección
    CAPTURE_COOLDOWN = 3.0      # segundos antes de re-intentar auto-captura

    def __init__(self, parent, wizard: RegisterUserScreen):
        super().__init__(parent, fg_color="#1A1A2E", corner_radius=0)
        self.wizard = wizard

        self._camera_running = False
        self._camera_thread: Optional[threading.Thread] = None
        self._current_frame: Optional[np.ndarray] = None
        self._detected_faces: list = []
        self._current_landmarks: list = []  # 68 puntos (x,y)
        self._photo_ref = None
        self._captured_embedding: Optional[np.ndarray] = None
        self._face_mgr = None

        # Auto-capture state
        self._stable_face_count = 0
        self._auto_captured = False
        self._last_capture_time = 0.0

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

        # Progreso de captura automática
        self.lbl_progress = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["ACCENT"], fg_color="transparent",
        )
        self.lbl_progress.place(relx=0.5, y=134, anchor="n")

        # Botones
        btn_row = ctk.CTkFrame(self, fg_color=PALETTE["CARD"],
                               corner_radius=0, height=90)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self.btn_capture = ctk.CTkButton(
            btn_row, text="Capturar",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PALETTE["ACCENT"], hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"], height=60, corner_radius=12,
            command=self._manual_capture,
        )
        self.btn_capture.grid(row=0, column=0, padx=(12, 6), pady=15, sticky="ew")

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
            self.lbl_status.configure(text="(!) OpenCV no instalado")
            return
        try:
            from core.face_recognition import FaceRecognitionManager
            logger.info("Inicializando FaceRecognitionManager para admin...")
            self._face_mgr = FaceRecognitionManager()

            if not self._face_mgr.initialize():
                logger.error("FaceRecognitionManager init failed")
                self.lbl_status.configure(text="✗ Cámara no disponible")
                self._face_mgr = None
                return

            logger.info("✓ FaceRecognitionManager inicializado")
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

    # ── Camera loop (thread) ──────────────────────────────────────────────────

    def _camera_loop(self) -> None:
        import time
        logger.info("Camera loop started")
        while self._camera_running:
            try:
                if self._face_mgr is None:
                    break

                frame = self._face_mgr.get_frame()
                if frame is None:
                    time.sleep(0.05)
                    continue

                self._current_frame = frame

                # Detección (dlib HOG + Haar cascade fallback integrado)
                faces = self._face_mgr.face_detector.detect(frame)

                self._detected_faces = faces

                # Extraer landmarks para el primer rostro (para dibujar en canvas)
                if faces and self._face_mgr.embedding_extractor.is_ready:
                    box = faces[0].get("box")
                    if box:
                        lm = self._face_mgr.get_landmarks(frame, box)
                        self._current_landmarks = lm or []
                    else:
                        self._current_landmarks = []
                else:
                    self._current_landmarks = []

                # Auto-captura: si hay rostro estable y aún no se capturó
                if faces and not self._auto_captured:
                    self._stable_face_count += 1
                else:
                    if not faces:
                        self._stable_face_count = 0

                if (self._stable_face_count >= self.STABLE_FRAMES_NEEDED
                        and not self._auto_captured
                        and time.time() - self._last_capture_time > self.CAPTURE_COOLDOWN):
                    self._try_auto_capture(frame, faces)

            except Exception as e:
                logger.error(f"Error en camera_loop: {e}")
                break
            time.sleep(0.05)  # ~20 fps de detección
        logger.info("Camera loop ended")

    def _try_auto_capture(self, frame: np.ndarray, faces: list) -> None:
        """Intenta auto-capturar el embedding en background."""
        import time
        if not faces or self._face_mgr is None:
            return

        box = faces[0].get("box")
        if not box:
            return

        logger.info("Auto-captura: extrayendo embedding dlib...")
        embedding = self._face_mgr.get_embedding(frame, box)

        if embedding is not None:
            self._captured_embedding = embedding
            self._auto_captured = True
            self._last_capture_time = time.time()
            logger.info(f"✓ Embedding capturado automáticamente: {embedding.shape}")
            # Actualizar UI desde thread principal
            self.after(0, self._on_auto_capture_success)
        else:
            logger.warning("Auto-captura: no se pudo extraer embedding")
            self._stable_face_count = 0

    def _on_auto_capture_success(self) -> None:
        """Callback en el hilo principal tras auto-captura exitosa."""
        self.lbl_status.configure(
            text="✓ Rostro capturado automáticamente",
            text_color="#A5D6A7",
        )
        self.lbl_progress.configure(text="Embedding 128-dim listo — presiona Registrar")
        self.btn_save.configure(state="normal")
        self.btn_capture.configure(
            text="Recapturar",
            fg_color="#555555",
        )

    # ── Display ───────────────────────────────────────────────────────────────

    def _update_canvas(self) -> None:
        if not self._camera_running:
            return

        if self._current_frame is not None:
            frame = self._current_frame.copy()

            # BGR → RGB para PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Redimensionar manteniendo aspect ratio
            h, w = frame_rgb.shape[:2]
            scale = min(WIN_W / w, 600 / h)
            new_w = int(w * scale)
            new_h = int(h * scale)

            frame_resized = cv2.resize(frame_rgb, (new_w, new_h),
                                       interpolation=cv2.INTER_LINEAR)

            # Canvas negro centrado
            canvas = np.zeros((600, WIN_W, 3), dtype=np.uint8)
            y_off = (600 - new_h) // 2
            x_off = (WIN_W - new_w) // 2
            canvas[y_off:y_off+new_h, x_off:x_off+new_w] = frame_resized

            img = Image.fromarray(canvas, mode="RGB").convert("RGBA")

            has_face = len(self._detected_faces) > 0
            outline_color = SILO_OK_FACE if has_face else SILO_NO_FACE

            # Dibujar landmarks en el frame (puntos verdes)
            if self._current_landmarks:
                draw_img = ImageDraw.Draw(img)
                for (lx, ly) in self._current_landmarks:
                    # Transformar coordenadas del frame original al canvas
                    sx = int(lx * scale) + x_off
                    sy = int(ly * scale) + y_off
                    r = 2
                    draw_img.ellipse([sx-r, sy-r, sx+r, sy+r],
                                     fill=(0, 255, 100, 220))

            # Silueta overlay
            overlay = self._silhouette_mask.copy()
            draw = ImageDraw.Draw(overlay)
            self._draw_outline(draw, outline_color)
            img = Image.alpha_composite(img, overlay)

            from PIL import ImageTk
            self._photo_ref = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw",
                                     image=self._photo_ref)

            # Status label
            if self._auto_captured:
                pass  # ya se mostró el mensaje de éxito
            elif has_face:
                pct = min(100, int(self._stable_face_count
                                   / self.STABLE_FRAMES_NEEDED * 100))
                self.lbl_status.configure(
                    text=f"Rostro detectado — capturando... {pct}%",
                    text_color="#A5D6A7",
                )
                self.lbl_progress.configure(
                    text="Mantén la posición",
                )
            else:
                self.lbl_status.configure(
                    text="Posiciona tu rostro en la silueta",
                    text_color=PALETTE["WHITE"],
                )
                self.lbl_progress.configure(text="")

        self.after(50, self._update_canvas)

    # ── Captura manual ────────────────────────────────────────────────────────

    def _manual_capture(self) -> None:
        """Botón Capturar / Recapturar."""
        logger.info("=== Botón Capturar presionado ===")
        if self._current_frame is None or self._face_mgr is None:
            self.lbl_status.configure(text="(!) Cámara no lista",
                                      text_color=PALETTE["DANGER"])
            return
        if not self._detected_faces:
            self.lbl_status.configure(text="(!) No se detectó ningún rostro",
                                      text_color=PALETTE["DANGER"])
            return

        frame = self._current_frame.copy()
        box = self._detected_faces[0].get("box")
        if not box:
            return

        self.lbl_status.configure(text="Extrayendo embedding...",
                                  text_color="#FFD54F")
        self.update_idletasks()

        embedding = self._face_mgr.get_embedding(frame, box)
        if embedding is None:
            self.lbl_status.configure(text="(!) No se pudo extraer embedding",
                                      text_color=PALETTE["DANGER"])
            return

        self._captured_embedding = embedding
        self._auto_captured = True
        self.lbl_status.configure(text="✓ Perfil facial capturado",
                                  text_color="#A5D6A7")
        self.lbl_progress.configure(text="Embedding 128-dim listo — presiona Registrar")
        self.btn_save.configure(state="normal")
        self.btn_capture.configure(text="Recapturar", fg_color="#555555")

    # ── Guardar usuario completo ──────────────────────────────────────────────

    def _save_user(self) -> None:
        if self._captured_embedding is None:
            self.lbl_status.configure(text="(!) Primero captura el rostro",
                                      text_color=PALETTE["DANGER"])
            return

        d = self.wizard._data
        logger.info(f"Guardando usuario: {d.get('nombre')} {d.get('apPaterno')}")

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
            logger.info(f"✓ Usuario insertado con ID={user_id}")
        except Exception as exc:
            logger.error(f"Error insertando usuario: {exc}")
            self.lbl_status.configure(
                text=f"Error al registrar: {exc}",
                text_color=PALETTE["DANGER"])
            return

        # Insertar encoding facial
        vec = self._captured_embedding
        vec_bytes = vec.tobytes()
        vec_hash = hashlib.sha256(vec_bytes).hexdigest()
        try:
            from config import FACE_RECOGNITION_CONFIG
            _modelo = FACE_RECOGNITION_CONFIG.get("model_type", "hog_cv2")
            execute("""
                INSERT INTO encoding
                    (idUsuario, estado, vector, dimension, hashVector,
                     tipoParte, vectorDtype, modelo, modeloVersion)
                VALUES (?, 'activo', ?, ?, ?, 'frontal', 'float32',
                        ?, '1.0')
            """, (user_id, vec_bytes, len(vec), vec_hash, _modelo))
            logger.info(f"✓ Encoding insertado para usuario {user_id} (modelo={_modelo})")
        except Exception as exc:
            logger.warning(f"Error insertando encoding (no bloquea registro): {exc}")

        self.stop_camera()
        self.wizard.next_step({"saved_user_id": user_id,
                               "saved_nombre": d["nombre"]})

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def on_enter(self, data: dict) -> None:
        logger.info("=== Entrando a Step4FaceCapture (Admin) ===")
        self._captured_embedding = None
        self._auto_captured = False
        self._stable_face_count = 0
        self._last_capture_time = 0.0
        self._current_landmarks = []
        self.btn_save.configure(state="disabled")
        self.btn_capture.configure(text="Capturar", fg_color=PALETTE["ACCENT"])
        self.lbl_progress.configure(text="")
        self.lbl_status.configure(text="Posiciona tu rostro en la silueta",
                                  text_color=PALETTE["WHITE"])
        logger.info("Iniciando cámara para registro...")
        self._start_camera()

    def on_leave(self) -> None:
        """Detiene la cámara cuando se sale de este paso."""
        logger.info("=== Saliendo de Step4FaceCapture ===")
        self.stop_camera()


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
