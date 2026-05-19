"""
core/i18n.py – Sistema de internacionalización ES/EN.

Uso básico:
    from core.i18n import t, set_language, get_language, register_observer, unregister_observer

    t("standby_approach")            → "Acerca tu rostro a la cámara"
    t("scan_scanning_pct", pct=42)   → "ESCANEANDO...  42%"
    set_language("en")               → cambia a inglés y notifica observers
"""

from __future__ import annotations

import os
import threading
import logging
from typing import Callable

logger = logging.getLogger(__name__)

_LANG_FILE = "/tmp/locker_lang.txt"
_DEFAULT_LANG = "es"

# ── Diccionario de traducciones ───────────────────────────────────────────────

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "es": {
        # LOCKER – StandbyScreen
        "standby_approach":          "Acerca tu rostro a la cámara",
        "standby_start_scan":        "Iniciar escaneo",

        # LOCKER – ScanningScreen
        "scan_position":             "Posiciona tu rostro",
        "scan_starting_camera":      "INICIANDO CÁMARA...",
        "scan_identifying":          "IDENTIFICANDO...",
        "scan_scanning_pct":         "ESCANEANDO...  {pct}%",
        "scan_move_face":            "Mueve ligeramente tu rostro",
        "scan_position_frame":       "Posiciona tu rostro en el encuadre",
        "scan_returning":            "Volviendo al inicio en {seconds} s…",
        "scan_locker_number":        "Locker número",
        "scan_no_locker":            "Sin locker",
        "scan_no_locker_assigned":   "asignado",
        "scan_access_granted":       "✓ ACCESO CONCEDIDO",
        "scan_identity_verified":    "IDENTIDAD VERIFICADA",
        "scan_camera_error":         "✗ Cámara no disponible",
        "scan_back_to_start":        "Presiona ← para volver al inicio",
        "scan_not_recognized":       "✗ No reconocido — usa tu PIN",
        "scan_face_attempts":        "Rostro no reconocido ({a}/{m})",
        "scan_camera_error_title":   "✗ Error de Cámara",

        # PIN overlay
        "pin_step1":                 "PASO 1 DE 2  ·  IDENTIFÍCATE",
        "pin_step2":                 "PASO 2 DE 2  ·  VERIFICA TU IDENTIDAD",
        "pin_enter_matricula":       "Ingresa tu matrícula",
        "pin_matricula_instruction": "Escribe tu número de matrícula y presiona  ✓",
        "pin_enter_pin":             "Ingresa tu PIN de 4 dígitos",
        "pin_not_found":             "Matrícula no encontrada",
        "pin_enter_pin_err":         "Ingresa tu PIN",
        "pin_restart":               "Error: reinicia el proceso",
        "pin_wrong":                 "Matrícula o PIN incorrecto  ({r} intento{s} restante)",
        "pin_cancel":                "Cancelar",
        "pin_enter_matricula_err":   "Ingresa tu matrícula",

        # LOCK overlay
        "lock_blocked":              "BLOQUEADO",
        "lock_too_many":             "Demasiados intentos fallidos",
        "lock_wait":                 "Espera  {seconds}  segundo{s}…",
        "lock_auto_unlock":          "El sistema se desbloqueará automáticamente",

        # ADMIN – LoginScreen
        "login_title":               "Acceso administrativo",
        "login_subtitle":            "Inicia sesión como Administrador o Superadmin para gestionar el sistema.",
        "login_hello":               "Hola!!",
        "login_description":         "Ingresa para administrar usuarios, catálogos y asignaciones.",
        "login_matricula":           "Matrícula",
        "login_pin":                 "PIN",
        "login_placeholder_mat":     "Ej. 20260001",
        "login_enter_btn":           "Ingresar",
        "login_err_empty":           "Ingresa matrícula y PIN",
        "login_err_invalid":         "Credenciales inválidas o cuenta inactiva",
        "login_note":                "Solo cuentas con rol Administrador o Superadmin pueden ingresar.",
        "login_back_locker":         "← Volver al locker",

        # ADMIN – DashboardScreen
        "dash_catalogs":             "Catálogos",
        "dash_modules":              "Módulos disponibles",
        "dash_total_records":        "Registros activos totales",
        "dash_register_user":        "+  Registrar Usuario",
        "dash_users":                "Usuarios",
        "dash_lockers":              "Lockers",
        "dash_areas":                "Áreas / Zonas",
        "dash_academic":             "Unidades Acad.",
        "dash_user_types":           "Tipos Usuario",
        "dash_assignments":          "Asignaciones",
        "dash_accounts":             "Gestión de cuentas",
        "dash_inventory":            "Inventario físico",
        "dash_location":             "Ubicación por zona",
        "dash_faculties":            "Facultades y escuelas",
        "dash_roles":                "Roles del sistema",
        "dash_in_use":               "Lockers en uso",
        "dash_active_records":       "Registros activos",
        "dash_logout":               "Cerrar sesión",
        "dash_logout_confirm":       "¿Deseas continuar?",
        "dash_logout_detail":        "Si eliges No, continuarás con la sesión activa.",
        "dash_logout_no":            "No",
        "dash_logout_yes":           "Sí",

        # ADMIN – UsersCatalogScreen
        "users_title":               "Usuarios",
        "users_search":              "Buscar por nombre o matrícula…",
        "users_no_results":          "Sin resultados",
        "users_detail_title":        "Detalle de Usuario",
        "users_edit":                "Editar",
        "users_read_only":           "Solo lectura",
        "users_no_face":             "(!) Sin rostro registrado",
        "users_face_ok":             "[OK] {n} perfil(es) facial(es) registrado(s)",
        "users_save":                "Guardar cambios",
        "users_reregister_face":     "Re-registrar rostro",
        "users_disable":             "Inhabilitar",
        "users_enable":              "Habilitar",
        "users_protected":           "Protegido",
        "users_your_account":        "Tu cuenta",
        "users_delete_perm":         "Eliminar permanentemente",
        "users_cancel":              "Cancelar",
        "users_confirm":             "Confirmar",
        "users_field_nombre":        "Nombre",
        "users_field_apPaterno":     "Apellido Paterno",
        "users_field_apMaterno":     "Apellido Materno",
        "users_field_matricula":     "Matrícula",
        "users_field_email":         "Correo institucional",
        "users_field_tel":           "Teléfono",
        "users_field_tipo":          "Tipo de usuario",
        "users_field_unidad":        "Unidad académica",
        "users_field_estado":        "Estado",

        # ADMIN – RegisterUserScreen
        "reg_step1":                 "Paso 1 de 5",
        "reg_step1_title":           "Datos básicos",
        "reg_step2":                 "Paso 2 de 5",
        "reg_step2_title":           "Tipo y unidad",
        "reg_step3":                 "Paso 3 de 5",
        "reg_step3_title":           "Establece un PIN",
        "reg_step3_desc":            "El usuario usará este PIN de 4 dígitos\npara abrir su locker.",
        "reg_step4":                 "Paso 4 de 5",
        "reg_step4_title":           "Captura facial",
        "reg_step5":                 "Paso 5 de 5",
        "reg_next":                  "Siguiente →",
        "reg_back":                  "← Atrás",
        "reg_register":              "Registrar",
        "reg_repeat_pose":           "Repetir pose",
        "reg_finish":                "Volver al inicio",
        "reg_another":               "+  Registrar otro usuario",
        "reg_registered_ok":         "El usuario fue registrado exitosamente.",
        "reg_face_updated":          "El rostro fue actualizado exitosamente.",
        "reg_pose_frontal":          "Mira directo a la cámara",
        "reg_pose_right":            "Gira tu cabeza hacia tu DERECHA  →",
        "reg_pose_left":             "Gira tu cabeza hacia tu IZQUIERDA  ←",

        # ADMIN – AreasCatalogScreen
        "areas_title":               "Catálogos",
        "areas_tab_areas":           "Áreas",
        "areas_tab_units":           "Unidades",
        "areas_tab_types":           "Tipos Usr.",
        "areas_no_areas":            "Sin áreas registradas",
        "areas_no_units":            "Sin unidades registradas",
        "areas_no_types":            "Sin tipos registrados",
        "areas_save":                "Guardar",
        "areas_enable":              "Habilitar",
        "areas_disable":             "Inhabilitar",
        "areas_delete":              "Eliminar permanentemente",

        # ADMIN – LockersCatalogScreen
        "lockers_title":             "Lockers",
        "lockers_search":            "Buscar por área o ID…",
        "lockers_no_results":        "Sin resultados",
        "lockers_detail":            "Detalle de Locker",
        "lockers_save_state":        "Guardar estado",
        "lockers_disable":           "Inhabilitar",
        "lockers_delete":            "Eliminar locker",
        "lockers_no_assignment":     "Sin asignación activa",

        # ADMIN – LockerAssignmentScreen
        "assign_title":              "Asignación de Lockers",
        "assign_user":               "Usuario (alumno, admin o superadmin)",
        "assign_no_users":           "Sin alumnos activos",
        "assign_available_locker":   "Locker disponible",
        "assign_no_lockers":         "Sin lockers disponibles",
        "assign_assigned_locker":    "Locker asignado (para liberar)",
        "assign_no_assigned":        "Sin asignaciones activas",
        "assign_btn":                "Asignar",
        "assign_release":            "Liberar locker",
        "assign_active_list":        "Asignaciones activas",
        "assign_no_active":          "No hay asignaciones activas",
        "assign_open_manual":        "Abrir locker manualmente",

        # COMMON
        "common_back":               "←",
        "common_cancel":             "Cancelar",
        "common_confirm":            "Confirmar",
        "common_save":               "Guardar",
        "common_error":              "Error",
        "common_inactive":           "[INACTIVO]",
        "common_active_status":      "●  Activo",
        "common_inactive_status":    "●  Inactivo",
        "common_maintenance":        "●  Mantenimiento",
        "common_no_results":         "Sin resultados",
    },

    "en": {
        # LOCKER – StandbyScreen
        "standby_approach":          "Bring your face to the camera",
        "standby_start_scan":        "Start scan",

        # LOCKER – ScanningScreen
        "scan_position":             "Position your face",
        "scan_starting_camera":      "STARTING CAMERA...",
        "scan_identifying":          "IDENTIFYING...",
        "scan_scanning_pct":         "SCANNING...  {pct}%",
        "scan_move_face":            "Move your face slightly",
        "scan_position_frame":       "Position your face in the frame",
        "scan_returning":            "Returning to start in {seconds} s…",
        "scan_locker_number":        "Locker number",
        "scan_no_locker":            "No locker",
        "scan_no_locker_assigned":   "assigned",
        "scan_access_granted":       "✓ ACCESS GRANTED",
        "scan_identity_verified":    "IDENTITY VERIFIED",
        "scan_camera_error":         "✗ Camera unavailable",
        "scan_back_to_start":        "Press ← to go back",
        "scan_not_recognized":       "✗ Not recognized — use your PIN",
        "scan_face_attempts":        "Face not recognized ({a}/{m})",
        "scan_camera_error_title":   "✗ Camera Error",

        # PIN overlay
        "pin_step1":                 "STEP 1 OF 2  ·  IDENTIFY YOURSELF",
        "pin_step2":                 "STEP 2 OF 2  ·  VERIFY YOUR IDENTITY",
        "pin_enter_matricula":       "Enter your student ID",
        "pin_matricula_instruction": "Type your student ID and press  ✓",
        "pin_enter_pin":             "Enter your 4-digit PIN",
        "pin_not_found":             "Student ID not found",
        "pin_enter_pin_err":         "Enter your PIN",
        "pin_restart":               "Error: restart the process",
        "pin_wrong":                 "Wrong ID or PIN  ({r} attempt{s} remaining)",
        "pin_cancel":                "Cancel",
        "pin_enter_matricula_err":   "Enter your student ID",

        # LOCK overlay
        "lock_blocked":              "LOCKED OUT",
        "lock_too_many":             "Too many failed attempts",
        "lock_wait":                 "Wait  {seconds}  second{s}…",
        "lock_auto_unlock":          "System will unlock automatically",

        # ADMIN – LoginScreen
        "login_title":               "Admin Access",
        "login_subtitle":            "Sign in as Administrator or Superadmin to manage the system.",
        "login_hello":               "Hello!!",
        "login_description":         "Sign in to manage users, catalogs and assignments.",
        "login_matricula":           "Student ID",
        "login_pin":                 "PIN",
        "login_placeholder_mat":     "e.g. 20260001",
        "login_enter_btn":           "Sign in",
        "login_err_empty":           "Enter student ID and PIN",
        "login_err_invalid":         "Invalid credentials or inactive account",
        "login_note":                "Only Administrator or Superadmin accounts can sign in.",
        "login_back_locker":         "← Back to locker",

        # ADMIN – DashboardScreen
        "dash_catalogs":             "Catalogs",
        "dash_modules":              "Available modules",
        "dash_total_records":        "Total active records",
        "dash_register_user":        "+  Register User",
        "dash_users":                "Users",
        "dash_lockers":              "Lockers",
        "dash_areas":                "Areas / Zones",
        "dash_academic":             "Academic Units",
        "dash_user_types":           "User Types",
        "dash_assignments":          "Assignments",
        "dash_accounts":             "Account management",
        "dash_inventory":            "Physical inventory",
        "dash_location":             "Zone location",
        "dash_faculties":            "Faculties & schools",
        "dash_roles":                "System roles",
        "dash_in_use":               "Lockers in use",
        "dash_active_records":       "Active records",
        "dash_logout":               "Sign out",
        "dash_logout_confirm":       "Do you want to continue?",
        "dash_logout_detail":        "If you choose No, your session will remain active.",
        "dash_logout_no":            "No",
        "dash_logout_yes":           "Yes",

        # ADMIN – UsersCatalogScreen
        "users_title":               "Users",
        "users_search":              "Search by name or student ID…",
        "users_no_results":          "No results",
        "users_detail_title":        "User Detail",
        "users_edit":                "Edit",
        "users_read_only":           "Read only",
        "users_no_face":             "(!) No face registered",
        "users_face_ok":             "[OK] {n} facial profile(s) registered",
        "users_save":                "Save changes",
        "users_reregister_face":     "Re-register face",
        "users_disable":             "Disable",
        "users_enable":              "Enable",
        "users_protected":           "Protected",
        "users_your_account":        "Your account",
        "users_delete_perm":         "Delete permanently",
        "users_cancel":              "Cancel",
        "users_confirm":             "Confirm",
        "users_field_nombre":        "First name",
        "users_field_apPaterno":     "Last name",
        "users_field_apMaterno":     "Second last name",
        "users_field_matricula":     "Student ID",
        "users_field_email":         "Institutional email",
        "users_field_tel":           "Phone",
        "users_field_tipo":          "User type",
        "users_field_unidad":        "Academic unit",
        "users_field_estado":        "Status",

        # ADMIN – RegisterUserScreen
        "reg_step1":                 "Step 1 of 5",
        "reg_step1_title":           "Basic data",
        "reg_step2":                 "Step 2 of 5",
        "reg_step2_title":           "Type & unit",
        "reg_step3":                 "Step 3 of 5",
        "reg_step3_title":           "Set a PIN",
        "reg_step3_desc":            "The user will use this 4-digit PIN\nto open their locker.",
        "reg_step4":                 "Step 4 of 5",
        "reg_step4_title":           "Face capture",
        "reg_step5":                 "Step 5 of 5",
        "reg_next":                  "Next →",
        "reg_back":                  "← Back",
        "reg_register":              "Register",
        "reg_repeat_pose":           "Repeat pose",
        "reg_finish":                "Back to start",
        "reg_another":               "+  Register another user",
        "reg_registered_ok":         "User registered successfully.",
        "reg_face_updated":          "Face updated successfully.",
        "reg_pose_frontal":          "Look directly at the camera",
        "reg_pose_right":            "Turn your head to the RIGHT  →",
        "reg_pose_left":             "Turn your head to the LEFT  ←",

        # ADMIN – AreasCatalogScreen
        "areas_title":               "Catalogs",
        "areas_tab_areas":           "Areas",
        "areas_tab_units":           "Units",
        "areas_tab_types":           "User Types",
        "areas_no_areas":            "No areas registered",
        "areas_no_units":            "No units registered",
        "areas_no_types":            "No types registered",
        "areas_save":                "Save",
        "areas_enable":              "Enable",
        "areas_disable":             "Disable",
        "areas_delete":              "Delete permanently",

        # ADMIN – LockersCatalogScreen
        "lockers_title":             "Lockers",
        "lockers_search":            "Search by area or ID…",
        "lockers_no_results":        "No results",
        "lockers_detail":            "Locker Detail",
        "lockers_save_state":        "Save status",
        "lockers_disable":           "Disable",
        "lockers_delete":            "Delete locker",
        "lockers_no_assignment":     "No active assignment",

        # ADMIN – LockerAssignmentScreen
        "assign_title":              "Locker Assignment",
        "assign_user":               "User (student, admin or superadmin)",
        "assign_no_users":           "No active students",
        "assign_available_locker":   "Available locker",
        "assign_no_lockers":         "No lockers available",
        "assign_assigned_locker":    "Assigned locker (to release)",
        "assign_no_assigned":        "No active assignments",
        "assign_btn":                "Assign",
        "assign_release":            "Release locker",
        "assign_active_list":        "Active assignments",
        "assign_no_active":          "No active assignments",
        "assign_open_manual":        "Open locker manually",

        # COMMON
        "common_back":               "←",
        "common_cancel":             "Cancel",
        "common_confirm":            "Confirm",
        "common_save":               "Save",
        "common_error":              "Error",
        "common_inactive":           "[INACTIVE]",
        "common_active_status":      "●  Active",
        "common_inactive_status":    "●  Inactive",
        "common_maintenance":        "●  Maintenance",
        "common_no_results":         "No results",
    },
}

# ── Estado interno (thread-safe) ──────────────────────────────────────────────

_lock = threading.Lock()
_current_lang: str = _DEFAULT_LANG
_observers: list[Callable[[], None]] = []


def _load_persisted_lang() -> str:
    try:
        if os.path.exists(_LANG_FILE):
            lang = open(_LANG_FILE).read().strip()
            if lang in _TRANSLATIONS:
                return lang
    except Exception:
        pass
    return _DEFAULT_LANG


def _persist_lang(lang: str) -> None:
    try:
        with open(_LANG_FILE, "w") as f:
            f.write(lang)
    except Exception as e:
        logger.debug(f"No se pudo persistir idioma: {e}")


# Cargar idioma guardado al importar el módulo
_current_lang = _load_persisted_lang()


# ── API pública ───────────────────────────────────────────────────────────────

def t(key: str, **kwargs) -> str:
    """
    Retorna el texto traducido para *key* en el idioma actual.
    Si se pasan kwargs, aplica str.format_map() al texto resultante.
    Si la clave no existe devuelve la clave misma para facilitar depuración.
    """
    with _lock:
        lang = _current_lang
    text = _TRANSLATIONS.get(lang, {}).get(key)
    if text is None:
        # Fallback a español
        text = _TRANSLATIONS["es"].get(key, key)
    if kwargs:
        try:
            text = text.format_map(kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def set_language(lang: str) -> None:
    """Cambia el idioma activo y notifica a todos los observers registrados."""
    if lang not in _TRANSLATIONS:
        logger.warning(f"Idioma desconocido: {lang!r}. Ignorado.")
        return
    with _lock:
        global _current_lang
        if _current_lang == lang:
            return
        _current_lang = lang
        observers_snapshot = list(_observers)
    _persist_lang(lang)
    for cb in observers_snapshot:
        try:
            cb()
        except Exception as e:
            logger.warning(f"Error en observer de idioma: {e}")


def get_language() -> str:
    """Retorna el idioma actual ('es' o 'en')."""
    with _lock:
        return _current_lang


def register_observer(cb: Callable[[], None]) -> None:
    """Registra una función que se llama cuando cambia el idioma."""
    with _lock:
        if cb not in _observers:
            _observers.append(cb)


def unregister_observer(cb: Callable[[], None]) -> None:
    """Elimina un observer previamente registrado."""
    with _lock:
        try:
            _observers.remove(cb)
        except ValueError:
            pass
