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

import threading
import tkinter as tk
from typing import Optional
import logging
import sqlite3
import hashlib

import customtkinter as ctk
from PIL import Image, ImageDraw

from database.connection import fetch_all, fetch_one
from services import user_service
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
    Paso de captura facial guiada con 3 poses: frontal, derecha, izquierda.

    Flujo:
      1. Instrucción de pose + silueta guía en pantalla
      2. Al detectar rostro estable → captura automática del embedding
      3. Avanza automáticamente a la siguiente pose
      4. Tras capturar las 3 poses → habilita "Registrar"
      5. Guarda 3 encodings por usuario (mejora reconocimiento multi-ángulo)
    """

    STABLE_FRAMES_NEEDED = 15
    CAPTURE_COOLDOWN = 2.0
    CANVAS_H = 540

    # Poses guiadas en orden
    CAPTURE_POSES = [
        {"tipoParte": "frontal",   "instruccion": "Mira directo a la cámara",           "icono": "●"},
        {"tipoParte": "derecha",   "instruccion": "Gira tu cabeza hacia tu DERECHA  →",  "icono": "→"},
        {"tipoParte": "izquierda", "instruccion": "Gira tu cabeza hacia tu IZQUIERDA  ←", "icono": "←"},
    ]

    def __init__(self, parent, wizard: RegisterUserScreen):
        super().__init__(parent, fg_color="#1A1A2E", corner_radius=0)
        self.wizard = wizard

        self._camera_running = False
        self._camera_thread: Optional[threading.Thread] = None
        self._current_frame: Optional[np.ndarray] = None
        self._detected_faces: list = []
        self._current_landmarks: list = []
        self._photo_ref = None
        self._face_mgr = None
        self._embedding_mode = "dlib"

        # Estado multi-pose
        self._current_pose_idx: int = 0
        self._captured_poses: list[dict] = []   # [{"tipoParte": str, "embedding": ndarray}]
        self._stable_face_count: int = 0
        self._pose_captured: bool = False       # pose actual ya capturada
        self._advance_pending: bool = False     # esperando auto-avance a siguiente pose
        self._last_capture_time: float = 0.0

        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        _wizard_header(self, "Paso 4 de 5", "Captura facial",
                       back_cmd=self.wizard.prev_step,
                       bg="#1A1A2E", text_color=PALETTE["WHITE"])

        # ── Indicadores de progreso de poses ─────────────────────────────────
        prog_row = ctk.CTkFrame(self, fg_color="#0E0E1E", height=56, corner_radius=0)
        prog_row.pack(fill="x")
        prog_row.pack_propagate(False)

        inner = ctk.CTkFrame(prog_row, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        self._pose_dot_labels: list[ctk.CTkLabel] = []
        self._pose_name_labels: list[ctk.CTkLabel] = []
        pose_names = ["Frente", "Derecha", "Izquierda"]
        for i, name in enumerate(pose_names):
            col = ctk.CTkFrame(inner, fg_color="transparent")
            col.pack(side="left", padx=22)
            dot = ctk.CTkLabel(col, text="○", font=ctk.CTkFont(size=20),
                               text_color="#444444", fg_color="transparent")
            dot.pack()
            lbl = ctk.CTkLabel(col, text=name, font=ctk.CTkFont(size=10),
                               text_color="#444444", fg_color="transparent")
            lbl.pack()
            self._pose_dot_labels.append(dot)
            self._pose_name_labels.append(lbl)

        # ── Canvas de cámara ──────────────────────────────────────────────────
        self.canvas = tk.Canvas(
            self, width=WIN_W, height=self.CANVAS_H,
            bg="#1A1A2E", highlightthickness=0,
        )
        self.canvas.pack()

        # ── Labels superpuestos sobre el canvas ───────────────────────────────
        self.lbl_status = ctk.CTkLabel(
            self, text="Posiciona tu rostro",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=PALETTE["WHITE"], fg_color="#1A1A2E",
            corner_radius=10, height=36, width=380,
        )
        self.lbl_status.place(relx=0.5, y=82, anchor="n")

        self.lbl_progress = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["ACCENT"], fg_color="transparent",
        )
        self.lbl_progress.place(relx=0.5, y=124, anchor="n")

        # Barra de progreso de captura de pose
        self.pose_progress = ctk.CTkProgressBar(
            self, width=340, height=10,
            fg_color="#2A2A3E", progress_color=PALETTE["ACCENT"],
            corner_radius=5,
        )
        self.pose_progress.set(0)
        self.pose_progress.place(relx=0.5, rely=0.82, anchor="center")

        # ── Botones inferiores ────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color=PALETTE["CARD"],
                               corner_radius=0, height=90)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self.btn_retry = ctk.CTkButton(
            btn_row, text="Repetir pose",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#444444", hover_color="#333333",
            text_color=PALETTE["WHITE"], height=60, corner_radius=12,
            command=self._retry_last_pose, state="disabled",
        )
        self.btn_retry.grid(row=0, column=0, padx=(12, 6), pady=15, sticky="ew")

        self.btn_save = ctk.CTkButton(
            btn_row, text="Registrar",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PALETTE.get("SUCCESS", "#27ae60"), hover_color="#1e8449",
            text_color=PALETTE["WHITE"], height=60, corner_radius=12,
            command=self._save_user, state="disabled",
        )
        self.btn_save.grid(row=0, column=1, padx=(6, 12), pady=15, sticky="ew")

    def _refresh_pose_indicators(self) -> None:
        """Actualiza los indicadores ○/◉/● según las poses completadas."""
        total = len(self.CAPTURE_POSES)
        captured = len(self._captured_poses)
        for i in range(total):
            dot = self._pose_dot_labels[i]
            lbl = self._pose_name_labels[i]
            if i < captured:
                dot.configure(text="●", text_color="#A5D6A7")
                lbl.configure(text_color="#A5D6A7")
            elif i == self._current_pose_idx:
                dot.configure(text="◉", text_color="#FFD54F")
                lbl.configure(text_color="#FFD54F")
            else:
                dot.configure(text="○", text_color="#444444")
                lbl.configure(text_color="#444444")

    def _show_pose_instruction(self) -> None:
        """Muestra instrucción y progreso para la pose actual."""
        if self._current_pose_idx >= len(self.CAPTURE_POSES):
            return
        pose = self.CAPTURE_POSES[self._current_pose_idx]
        captured = len(self._captured_poses)
        total = len(self.CAPTURE_POSES)
        self.lbl_status.configure(
            text=f"Pose {captured + 1}/{total}:  {pose['instruccion']}",
            text_color=PALETTE["WHITE"],
        )
        self.lbl_progress.configure(text="Mantén el rostro estable...", text_color=PALETTE["ACCENT"])

    # ── Cámara ────────────────────────────────────────────────────────────────

    def _start_camera(self) -> None:
        if self._camera_running:
            return
        if not _CV2_AVAILABLE:
            self.lbl_status.configure(text="(!) OpenCV no instalado")
            return
        try:
            from core.face_recognition import FaceRecognitionManager
            self._face_mgr = FaceRecognitionManager()
            if not self._face_mgr.initialize():
                self.lbl_status.configure(text="✗ Cámara no disponible",
                                          text_color=PALETTE["DANGER"])
                self._face_mgr = None
                return
            if not self._face_mgr.embedding_extractor.is_ready:
                self.lbl_status.configure(text="✗ Extractor facial no disponible",
                                          text_color=PALETTE["DANGER"])
                self.lbl_progress.configure(text="Instala dlib + modelos para registrar rostros",
                                            text_color=PALETTE["DANGER"])
                self._face_mgr.release()
                self._face_mgr = None
                return
            self._embedding_mode = (
                "dlib" if getattr(self._face_mgr.embedding_extractor, "uses_dlib", False)
                else "fallback"
            )
            if self._embedding_mode == "fallback":
                self.lbl_progress.configure(
                    text="Modo básico: sin modelos dlib. Usa buena iluminación.",
                    text_color="#FFD54F",
                )
        except Exception as exc:
            logger.error(f"Error al inicializar cámara: {exc}", exc_info=True)
            self.lbl_status.configure(text=f"(!) Error: {str(exc)[:60]}")
            return

        self._camera_running = True
        self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._camera_thread.start()
        self._update_canvas()

    def stop_camera(self) -> None:
        self._camera_running = False
        if self._face_mgr is not None:
            try:
                self._face_mgr.release()
            except Exception:
                pass
            self._face_mgr = None

    # ── Camera loop (hilo worker) ─────────────────────────────────────────────

    def _camera_loop(self) -> None:
        import time
        while self._camera_running:
            try:
                if self._face_mgr is None:
                    break
                frame = self._face_mgr.get_frame()
                if frame is None:
                    time.sleep(0.05)
                    continue

                self._current_frame = frame
                faces = self._face_mgr.face_detector.detect(frame)
                self._detected_faces = faces

                if faces:
                    box = faces[0].get("box")
                    self._current_landmarks = self._face_mgr.get_landmarks(frame, box) or [] if box else []
                else:
                    self._current_landmarks = []

                # Conteo de estabilidad para auto-captura
                all_done = len(self._captured_poses) >= len(self.CAPTURE_POSES)
                if faces and not self._pose_captured and not all_done and not self._advance_pending:
                    self._stable_face_count += 1
                elif not faces:
                    self._stable_face_count = 0

                if (self._stable_face_count >= self.STABLE_FRAMES_NEEDED
                        and not self._pose_captured
                        and not all_done
                        and not self._advance_pending
                        and time.time() - self._last_capture_time > self.CAPTURE_COOLDOWN):
                    self._try_capture_pose(frame, faces)

            except Exception as e:
                logger.error(f"Error en camera_loop registro: {e}")
                break
            time.sleep(0.05)

    def _try_capture_pose(self, frame, faces) -> None:
        import time
        if not faces or self._face_mgr is None:
            return
        box = faces[0].get("box")
        if not box:
            return

        pose = self.CAPTURE_POSES[self._current_pose_idx]
        embedding = self._face_mgr.get_embedding(frame, box)
        if embedding is not None:
            self._captured_poses.append({"tipoParte": pose["tipoParte"], "embedding": embedding})
            self._pose_captured = True
            self._last_capture_time = time.time()
            logger.info("Pose '%s' capturada (%d/%d)", pose["tipoParte"],
                        len(self._captured_poses), len(self.CAPTURE_POSES))
            self.after(0, self._on_pose_captured)
        else:
            logger.warning("No se pudo extraer embedding para pose '%s'", pose["tipoParte"])
            self._stable_face_count = 0

    # ── Callbacks en hilo principal ───────────────────────────────────────────

    def _on_pose_captured(self) -> None:
        captured = len(self._captured_poses)
        total = len(self.CAPTURE_POSES)
        self._refresh_pose_indicators()
        self.btn_retry.configure(state="normal")

        if captured >= total:
            self.lbl_status.configure(
                text=f"✓ {total}/{total} poses capturadas",
                text_color="#A5D6A7",
            )
            self.lbl_progress.configure(
                text="Biometría completa — presiona Registrar",
                text_color="#A5D6A7",
            )
            self.btn_save.configure(state="normal")
            self.btn_retry.configure(state="normal")
        else:
            next_pose = self.CAPTURE_POSES[captured]
            self.lbl_status.configure(
                text=f"✓ Pose {captured}/{total} lista",
                text_color="#A5D6A7",
            )
            self.lbl_progress.configure(
                text=f"Siguiente: {next_pose['instruccion']}",
                text_color="#81D4FA",
            )
            self._advance_pending = True
            self.after(1600, self._advance_pose)

    def _advance_pose(self) -> None:
        self._current_pose_idx = len(self._captured_poses)
        self._stable_face_count = 0
        self._pose_captured = False
        self._advance_pending = False
        self._refresh_pose_indicators()
        self._show_pose_instruction()

    def _retry_last_pose(self) -> None:
        if not self._captured_poses:
            return
        removed = self._captured_poses.pop()
        self._current_pose_idx = len(self._captured_poses)
        self._stable_face_count = 0
        self._pose_captured = False
        self._advance_pending = False
        self.btn_save.configure(state="disabled")
        self.btn_retry.configure(state="disabled" if not self._captured_poses else "normal")
        self._refresh_pose_indicators()
        self._show_pose_instruction()
        logger.info("Pose '%s' eliminada para re-capturar", removed["tipoParte"])

    # ── Actualización de canvas ───────────────────────────────────────────────

    def _update_canvas(self) -> None:
        if not self._camera_running:
            return

        if self._current_frame is not None:
            frame_rgb = cv2.flip(cv2.cvtColor(self._current_frame, cv2.COLOR_BGR2RGB), 1)
            h, w = frame_rgb.shape[:2]
            scale = min(WIN_W / w, self.CANVAS_H / h)
            new_w, new_h = int(w * scale), int(h * scale)
            frame_resized = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            canvas_arr = np.zeros((self.CANVAS_H, WIN_W, 3), dtype=np.uint8)
            y_off = (self.CANVAS_H - new_h) // 2
            x_off = (WIN_W - new_w) // 2
            canvas_arr[y_off:y_off + new_h, x_off:x_off + new_w] = frame_resized

            pil_image = Image.fromarray(canvas_arr, "RGB")
            draw = ImageDraw.Draw(pil_image)
            has_face = len(self._detected_faces) > 0

            # Corner-bracket face guide (clean, no circles or silhouette ellipses)
            cx, cy = WIN_W // 2, self.CANVAS_H // 2 - 20
            gw, gh = 130, 175
            x1, y1, x2, y2 = cx - gw, cy - gh, cx + gw, cy + gh
            color = (90, 180, 90) if has_face else (200, 80, 80)
            cl, lw = 36, 5
            draw.line([(x1,      y1), (x1 + cl, y1)], fill=color, width=lw)
            draw.line([(x1,      y1), (x1,      y1 + cl)], fill=color, width=lw)
            draw.line([(x2 - cl, y1), (x2,      y1)], fill=color, width=lw)
            draw.line([(x2,      y1), (x2,      y1 + cl)], fill=color, width=lw)
            draw.line([(x1,      y2 - cl), (x1,  y2)], fill=color, width=lw)
            draw.line([(x1,      y2), (x1 + cl, y2)], fill=color, width=lw)
            draw.line([(x2,      y2 - cl), (x2,  y2)], fill=color, width=lw)
            draw.line([(x2 - cl, y2), (x2,      y2)], fill=color, width=lw)

            from PIL import ImageTk
            self._photo_ref = ImageTk.PhotoImage(pil_image)
            self.canvas.create_image(0, 0, anchor="nw", image=self._photo_ref)

            all_done = len(self._captured_poses) >= len(self.CAPTURE_POSES)
            if not all_done and not self._pose_captured and not self._advance_pending:
                if has_face:
                    pct = min(100, int(self._stable_face_count / self.STABLE_FRAMES_NEEDED * 100))
                    self.pose_progress.set(pct / 100)
                    if pct > 0:
                        self.lbl_progress.configure(
                            text=f"Mantén la posición... {pct}%",
                            text_color=PALETTE["ACCENT"],
                        )
                    else:
                        self._show_pose_instruction()
                else:
                    self.pose_progress.set(0)
                    self._show_pose_instruction()
            elif all_done:
                self.pose_progress.set(1.0)

        self.after(50, self._update_canvas)

    # ── Guardar usuario con 3 encodings ──────────────────────────────────────

    def _save_user(self) -> None:
        if len(self._captured_poses) < len(self.CAPTURE_POSES):
            self.lbl_status.configure(
                text=f"(!) Captura las {len(self.CAPTURE_POSES)} poses primero",
                text_color=PALETTE["DANGER"],
            )
            return

        self.btn_save.configure(state="disabled")
        d = self.wizard._data
        modelo_name = "dlib_resnet_v1" if self._embedding_mode == "dlib" else "fallback_gray_16x8"

        poses = [
            {
                "tipoParte": p["tipoParte"],
                "embedding": p["embedding"],
                "modelo":    modelo_name,
            }
            for p in self._captured_poses
        ]

        try:
            user_id = user_service.create_user_with_encodings(d, poses)
        except sqlite3.IntegrityError as exc:
            logger.error("IntegrityError al guardar usuario: %s", exc)
            self.btn_save.configure(state="normal")
            self.lbl_status.configure(
                text="Error: matrícula o correo ya existe",
                text_color=PALETTE["DANGER"],
            )
            return
        except Exception as exc:
            logger.error("Error insertando usuario: %s", exc)
            self.btn_save.configure(state="normal")
            self.lbl_status.configure(
                text=f"Error al registrar: {str(exc)[:60]}",
                text_color=PALETTE["DANGER"],
            )
            return

        self.stop_camera()
        self.wizard.next_step({"saved_user_id": user_id, "saved_nombre": d["nombre"]})

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def on_enter(self, data: dict) -> None:
        logger.info("Entrando a captura facial multi-pose")
        self._current_pose_idx = 0
        self._captured_poses = []
        self._stable_face_count = 0
        self._pose_captured = False
        self._advance_pending = False
        self._last_capture_time = 0.0
        self._current_landmarks = []
        self.btn_save.configure(state="disabled")
        self.btn_retry.configure(state="disabled")
        self._refresh_pose_indicators()
        self._show_pose_instruction()
        self._start_camera()
        self.pose_progress.set(0)

    def on_leave(self) -> None:
        logger.info("Saliendo de captura facial")
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
