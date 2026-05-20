"""
i18n – Sistema de internacionalización ES / EN.

Uso:
    from ui.i18n import t, get_lang, set_lang, toggle, lang_btn_text

    t("key")               → texto en el idioma activo
    t("key", s=5)          → con interpolación de parámetros
    toggle()               → alterna entre "es" y "en"
    lang_btn_text()        → texto del botón de cambio de idioma
"""

_lang: str = "es"

STRINGS: dict[str, dict[str, str]] = {
    # ── Locker: StandbyScreen ────────────────────────────────────────────────
    "standby.instruction": {
        "es": "Acerca tu rostro a la cámara",
        "en": "Bring your face closer to the camera",
    },
    "standby.start_scan": {
        "es": "Iniciar escaneo",
        "en": "Start scan",
    },

    # ── Locker: ScanningScreen (estados) ─────────────────────────────────────
    "scan.position_face": {
        "es": "POSICIONA TU ROSTRO",
        "en": "POSITION YOUR FACE",
    },
    "scan.starting_camera": {
        "es": "INICIANDO CÁMARA...",
        "en": "STARTING CAMERA...",
    },
    "scan.identifying": {
        "es": "IDENTIFICANDO...",
        "en": "IDENTIFYING...",
    },
    "scan.move_face": {
        "es": "Mueve ligeramente tu rostro",
        "en": "Move your face slightly",
    },
    "scan.position_frame": {
        "es": "Posiciona tu rostro en el encuadre",
        "en": "Position your face in the frame",
    },
    "scan.access_granted": {
        "es": "✓ ACCESO CONCEDIDO",
        "en": "✓ ACCESS GRANTED",
    },
    "scan.identity_verified": {
        "es": "IDENTIDAD VERIFICADA",
        "en": "IDENTITY VERIFIED",
    },
    "scan.locker_number": {
        "es": "Locker número",
        "en": "Locker number",
    },
    "scan.no_locker": {
        "es": "Sin locker",
        "en": "No locker",
    },
    "scan.no_locker_assigned": {
        "es": "asignado",
        "en": "assigned",
    },
    "scan.matricula_label": {
        "es": "Matrícula",
        "en": "ID",
    },
    "scan.camera_error_title": {
        "es": "✗ Error de Cámara",
        "en": "✗ Camera Error",
    },
    "scan.camera_unavailable": {
        "es": "✗ Cámara no disponible",
        "en": "✗ Camera unavailable",
    },

    # ── Locker: ScanningScreen (dinámicos con parámetros) ────────────────────
    "scan.scanning_pct": {
        "es": "ESCANEANDO...  {pct}%",
        "en": "SCANNING...  {pct}%",
    },
    "scan.return_in": {
        "es": "Volviendo al inicio en {s} s…",
        "en": "Returning to start in {s} s…",
    },
    "scan.attempts": {
        "es": "Intentos: {a} / {m}",
        "en": "Attempts: {a} / {m}",
    },
    "scan.not_recognized_use_pin": {
        "es": "✗ No reconocido — usa tu PIN",
        "en": "✗ Not recognized — use your PIN",
    },
    "scan.face_not_recognized": {
        "es": "Rostro no reconocido ({a}/{m})",
        "en": "Face not recognized ({a}/{m})",
    },

    # ── Locker: ScanningScreen – overlay PIN ─────────────────────────────────
    "pin.step1": {
        "es": "PASO 1 DE 2  ·  IDENTIFÍCATE",
        "en": "STEP 1 OF 2  ·  IDENTIFY",
    },
    "pin.step2": {
        "es": "PASO 2 DE 2  ·  VERIFICA TU IDENTIDAD",
        "en": "STEP 2 OF 2  ·  VERIFY YOUR IDENTITY",
    },
    "pin.title_enter_matricula": {
        "es": "Ingresa tu matrícula",
        "en": "Enter your ID number",
    },
    "pin.instruction_matricula": {
        "es": "Escribe tu número de matrícula y presiona  ✓",
        "en": "Type your ID number and press  ✓",
    },
    "pin.instruction_pin": {
        "es": "Ingresa tu PIN de 4 dígitos",
        "en": "Enter your 4-digit PIN",
    },
    "pin.cancel": {
        "es": "Cancelar",
        "en": "Cancel",
    },
    "pin.err_enter_matricula": {
        "es": "Ingresa tu matrícula",
        "en": "Enter your ID number",
    },
    "pin.err_matricula_not_found": {
        "es": "Matrícula no encontrada",
        "en": "ID number not found",
    },
    "pin.err_enter_pin": {
        "es": "Ingresa tu PIN",
        "en": "Enter your PIN",
    },
    "pin.err_restart": {
        "es": "Error: reinicia el proceso",
        "en": "Error: restart the process",
    },

    # ── Locker: ScanningScreen – pantalla de bloqueo ─────────────────────────
    "lock.blocked": {
        "es": "BLOQUEADO",
        "en": "LOCKED",
    },
    "lock.too_many_fails": {
        "es": "Demasiados intentos fallidos",
        "en": "Too many failed attempts",
    },
    "lock.wait": {
        "es": "Espera  {s}  segundo{p}…",
        "en": "Wait  {s}  second{p}…",
    },
    "lock.auto_unlock": {
        "es": "El sistema se desbloqueará automáticamente",
        "en": "The system will unlock automatically",
    },

    # ── Locker: UserDisplayScreen ────────────────────────────────────────────
    "display.access_granted": {
        "es": "Acceso concedido",
        "en": "Access granted",
    },
    "display.locker": {
        "es": "Casillero",
        "en": "Locker",
    },
    "display.return_in": {
        "es": "Volviendo al inicio en {s} s…",
        "en": "Returning to start in {s} s…",
    },

    # ── Admin: LoginScreen ───────────────────────────────────────────────────
    "login.admin_access": {
        "es": "Acceso administrativo",
        "en": "Administrative access",
    },
    "login.subtitle": {
        "es": "Inicia sesión como Administrador o Superadmin para gestionar el sistema.",
        "en": "Sign in as Administrator or Superadmin to manage the system.",
    },
    "login.greeting": {
        "es": "Hola!!",
        "en": "Hello!!",
    },
    "login.instruction": {
        "es": "Ingresa para administrar usuarios, catálogos y asignaciones.",
        "en": "Sign in to manage users, catalogs and assignments.",
    },
    "login.matricula_label": {
        "es": "Matrícula",
        "en": "ID Number",
    },
    "login.matricula_placeholder": {
        "es": "Ej. 20260001",
        "en": "E.g. 20260001",
    },
    "login.pin_label": {
        "es": "PIN",
        "en": "PIN",
    },
    "login.btn_enter": {
        "es": "Ingresar",
        "en": "Sign in",
    },
    "login.note": {
        "es": "Solo cuentas con rol Administrador o Superadmin pueden ingresar.",
        "en": "Only Administrator or Superadmin accounts can sign in.",
    },
    "login.back_locker": {
        "es": "← Volver al locker",
        "en": "← Back to locker",
    },
    "login.err_empty": {
        "es": "Ingresa matrícula y PIN",
        "en": "Enter ID number and PIN",
    },
    "login.err_invalid": {
        "es": "Credenciales inválidas o cuenta inactiva",
        "en": "Invalid credentials or inactive account",
    },

    # ── Admin: DashboardScreen ───────────────────────────────────────────────
    "dash.user_prefix": {
        "es": "Usuario:",
        "en": "User:",
    },
    "dash.session_active": {
        "es": "Sesión activa",
        "en": "Active session",
    },
    "dash.modules_available": {
        "es": "Módulos disponibles",
        "en": "Available modules",
    },
    "dash.total_records": {
        "es": "Registros activos totales",
        "en": "Total active records",
    },
    "dash.register_user_btn": {
        "es": "+  Registrar Usuario",
        "en": "+  Register User",
    },
    "dash.catalogs_section": {
        "es": "Catálogos",
        "en": "Catalogs",
    },
    "dash.active_records": {
        "es": "Registros activos",
        "en": "Active records",
    },
    # Catálogos – etiquetas de tarjetas
    "cat.users.label":      {"es": "Usuarios",        "en": "Users"},
    "cat.users.hint":       {"es": "Gestión de cuentas", "en": "Account management"},
    "cat.lockers.label":    {"es": "Lockers",          "en": "Lockers"},
    "cat.lockers.hint":     {"es": "Inventario físico", "en": "Physical inventory"},
    "cat.areas.label":      {"es": "Áreas / Zonas",    "en": "Areas / Zones"},
    "cat.areas.hint":       {"es": "Ubicación por zona", "en": "Location by zone"},
    "cat.units.label":      {"es": "Unidades Acad.",   "en": "Acad. Units"},
    "cat.units.hint":       {"es": "Facultades y escuelas", "en": "Faculties and schools"},
    "cat.types.label":      {"es": "Tipos Usuario",    "en": "User Types"},
    "cat.types.hint":       {"es": "Roles del sistema", "en": "System roles"},
    "cat.assign.label":     {"es": "Asignaciones",     "en": "Assignments"},
    "cat.assign.hint":      {"es": "Lockers en uso",   "en": "Lockers in use"},
    # Diálogo de cierre de sesión
    "logout.dialog_title": {
        "es": "Cerrar sesión",
        "en": "Sign out",
    },
    "logout.message": {
        "es": "Estás a punto de cerrar sesión. ¿Deseas continuar?",
        "en": "You are about to sign out. Do you want to continue?",
    },
    "logout.note": {
        "es": "Si eliges No, continuarás con la sesión activa.",
        "en": "If you choose No, your session will remain active.",
    },
    "logout.no": {
        "es": "No",
        "en": "No",
    },
    "logout.yes": {
        "es": "Sí",
        "en": "Yes",
    },

    # ── Admin: UsersCatalogScreen ────────────────────────────────────────────
    "users.title": {
        "es": "Usuarios",
        "en": "Users",
    },
    "users.search_placeholder": {
        "es": "Buscar por nombre o matrícula…",
        "en": "Search by name or ID…",
    },

    # ── Admin: LockersCatalogScreen ──────────────────────────────────────────
    "lockers.title": {
        "es": "Lockers",
        "en": "Lockers",
    },
    "lockers.search_placeholder": {
        "es": "Buscar por área o ID…",
        "en": "Search by area or ID…",
    },

    # ── Admin: AreasCatalogScreen ────────────────────────────────────────────
    "areas.title": {
        "es": "Catálogos",
        "en": "Catalogs",
    },
    "areas.tab.areas": {
        "es": "Áreas",
        "en": "Areas",
    },
    "areas.tab.units": {
        "es": "Unidades",
        "en": "Units",
    },
    "areas.tab.types": {
        "es": "Tipos Usr.",
        "en": "User Types",
    },

    # ── Admin: LockerAssignmentScreen ────────────────────────────────────────
    "assignment.title": {
        "es": "Asignación de Lockers",
        "en": "Locker Assignment",
    },
    "assignment.student_label": {
        "es": "Usuario (alumno, admin o superadmin)",
        "en": "User (student, admin or superadmin)",
    },
    "assignment.locker_label": {
        "es": "Locker disponible",
        "en": "Available locker",
    },
    "assignment.no_students": {
        "es": "Sin alumnos activos",
        "en": "No active students",
    },
    "assignment.no_lockers": {
        "es": "Sin lockers disponibles",
        "en": "No available lockers",
    },

    # ── Admin: RegisterUserScreen ────────────────────────────────────────────
    "register.title": {
        "es": "Registrar Usuario",
        "en": "Register User",
    },
    "register.step1_label": {"es": "Paso 1 de 5", "en": "Step 1 of 5"},
    "register.step1_title": {"es": "Datos básicos", "en": "Basic data"},
    "register.step2_label": {"es": "Paso 2 de 5", "en": "Step 2 of 5"},
    "register.step2_title": {"es": "Tipo y unidad", "en": "Type and unit"},
    "register.step3_label": {"es": "Paso 3 de 5", "en": "Step 3 of 5"},
    "register.step3_title": {"es": "Establece un PIN", "en": "Set a PIN"},
    "register.step4_label": {"es": "Paso 4 de 5", "en": "Step 4 of 5"},
    "register.step4_title": {"es": "Captura facial", "en": "Facial capture"},
}


def t(key: str, **kwargs) -> str:
    """Retorna el texto para 'key' en el idioma activo."""
    entry = STRINGS.get(key, {})
    text = entry.get(_lang, entry.get("es", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def set_lang(lang: str) -> None:
    global _lang
    if lang in ("es", "en"):
        _lang = lang


def get_lang() -> str:
    return _lang


def toggle() -> None:
    global _lang
    _lang = "en" if _lang == "es" else "es"


def lang_btn_text() -> str:
    """Texto del botón de cambio (muestra el idioma al que se cambiará)."""
    return "🇺🇸 EN" if _lang == "es" else "🇲🇽 ES"
