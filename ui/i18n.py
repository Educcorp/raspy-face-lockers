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
    "scan.access_denied": {
        "es": "✗ ACCESO DENEGADO",
        "en": "✗ ACCESS DENIED",
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
    "pin.hello_name": {
        "es": "Hola, {name}",
        "en": "Welcome, {name}",
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
    "cat.types.label":      {"es": "Historial Acceso", "en": "Access History"},
    "cat.types.hint":       {"es": "Accesos registrados", "en": "Registered accesses"},
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
    "areas.tab.history": {
        "es": "Historial",
        "en": "History",
    },

    # ── Admin: Historial de accesos ──────────────────────────────────────────
    "hist.no_records":    {"es": "Sin registros de acceso",  "en": "No access records"},
    "hist.granted":       {"es": "Concedido",                "en": "Granted"},
    "hist.denied":        {"es": "Denegado",                 "en": "Denied"},
    "hist.unknown_user":  {"es": "Sin asignación",           "en": "No assignment"},

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

    # ── Compartidos (botones y estados comunes) ──────────────────────────────
    "common.no_results":     {"es": "Sin resultados",            "en": "No results"},
    "common.save":           {"es": "Guardar",                   "en": "Save"},
    "common.save_changes":   {"es": "Guardar cambios",           "en": "Save changes"},
    "common.cancel":         {"es": "Cancelar",                  "en": "Cancel"},
    "common.confirm":        {"es": "Confirmar",                 "en": "Confirm"},
    "common.edit":           {"es": "Editar",                    "en": "Edit"},
    "common.read_only":      {"es": "Solo lectura",              "en": "Read only"},
    "common.enable":         {"es": "Habilitar",                 "en": "Enable"},
    "common.disable":        {"es": "Inhabilitar",               "en": "Disable"},
    "common.delete_permanent": {"es": "Eliminar permanentemente", "en": "Delete permanently"},
    "common.status":         {"es": "Estado",                    "en": "Status"},
    "common.inactive_badge": {"es": "[INACTIVO]",                "en": "[INACTIVE]"},
    "common.matr_prefix":    {"es": "Matr.",                     "en": "ID"},
    "common.since":          {"es": "Desde",                     "en": "Since"},

    # ── Admin: UserDetailOverlay ─────────────────────────────────────────────
    "users.detail_title":      {"es": "Detalle de Usuario",      "en": "User Detail"},
    "users.field_name":        {"es": "Nombre  (máx. {n} car.)", "en": "Name  (max. {n} char.)"},
    "users.field_lastname1":   {"es": "Apellido Paterno  (máx. {n} car.)", "en": "First Surname  (max. {n} char.)"},
    "users.field_lastname2":   {"es": "Apellido Materno  (máx. {n} car.)", "en": "Second Surname  (max. {n} char.)"},
    "users.field_matricula":   {"es": "Matrícula  (5-10 dígitos)",          "en": "ID Number  (5-10 digits)"},
    "users.field_email":       {"es": "Correo institucional  (máx. {n} car.)", "en": "Institutional email  (max. {n} char.)"},
    "users.field_phone":       {"es": "Teléfono  (opcional, 10-15 dígitos)", "en": "Phone  (optional, 10-15 digits)"},
    "users.field_type":        {"es": "Tipo de usuario",         "en": "User type"},
    "users.field_unit":        {"es": "Unidad académica",        "en": "Academic unit"},
    "users.no_face":           {"es": "Sin rostro registrado",   "en": "No face registered"},
    "users.no_face_warning":   {"es": "(!) Sin rostro registrado", "en": "(!) No face registered"},
    "users.face_count":        {"es": "✓ {n} perfil(es) facial(es) registrado(s)", "en": "✓ {n} facial profile(s) registered"},
    "users.reregister_face":   {"es": "Actualizar rostro",     "en": "Update face"},
    "users.protected":         {"es": "Protegido",               "en": "Protected"},
    "users.your_account":      {"es": "Tu cuenta",               "en": "Your account"},
    "users.err_superadmin_locked": {"es": "Solo puede existir un Superadmin en el sistema", "en": "Only one Superadmin is allowed in the system"},
    "users.err_matricula_taken": {"es": "La matrícula {mat} ya pertenece a otro usuario", "en": "ID {mat} already belongs to another user"},
    "users.err_email_taken":   {"es": "El correo {email} ya pertenece a otro usuario", "en": "Email {email} already belongs to another user"},
    "users.err_select_type_unit": {"es": "Selecciona un tipo de usuario y unidad académica válidos", "en": "Select a valid user type and academic unit"},
    "users.confirm_enable":    {"es": "¿Habilitar este usuario?\nSu acceso quedará activo nuevamente.", "en": "Enable this user?\nTheir access will be active again."},
    "users.confirm_disable":   {"es": "¿Inhabilitar este usuario?\nSu acceso quedará desactivado.", "en": "Disable this user?\nTheir access will be deactivated."},

    # ── Admin: LockerDetailOverlay ───────────────────────────────────────────
    "lockers.detail_title":      {"es": "Detalle de Locker",     "en": "Locker Detail"},
    "lockers.field_area":        {"es": "Área",                  "en": "Area"},
    "lockers.field_unit":        {"es": "Unidad académica",      "en": "Academic unit"},
    "lockers.area_prefix":       {"es": "Área:",                 "en": "Area:"},
    "lockers.current_assignment":{"es": "Asignación actual",     "en": "Current assignment"},
    "lockers.no_assignment":     {"es": "Sin asignación activa", "en": "No active assignment"},
    "lockers.system_protected":  {"es": "Locker de sistema — protegido", "en": "System locker — protected"},
    "lockers.system_warning":    {"es": "Los lockers 1-4 son predeterminados del sistema\ny no pueden modificarse ni eliminarse.", "en": "Lockers 1-4 are system defaults\nand cannot be modified or deleted."},
    "lockers.save_status":       {"es": "Guardar estado",        "en": "Save status"},
    "lockers.delete_btn":        {"es": "Eliminar locker",       "en": "Delete locker"},
    "lockers.inactive_badge":    {"es": "[INACTIVO]",            "en": "[INACTIVE]"},

    # ── Admin: AreasCatalogScreen (empty states) ─────────────────────────────
    "areas.no_area":    {"es": "Sin área",                 "en": "No area"},
    "areas.no_areas":   {"es": "Sin áreas registradas",    "en": "No areas registered"},
    "areas.no_units":   {"es": "Sin unidades registradas", "en": "No units registered"},
    "areas.no_types":   {"es": "Sin tipos registrados",    "en": "No types registered"},
    "areas.supervisor": {"es": "Encargado:",               "en": "Supervisor:"},
    # Form titles
    "areas.edit_area":  {"es": "Editar Área",              "en": "Edit Area"},
    "areas.new_area":   {"es": "Nueva Área",               "en": "New Area"},
    "areas.edit_unit":  {"es": "Editar Unidad",            "en": "Edit Unit"},
    "areas.new_unit":   {"es": "Nueva Unidad",             "en": "New Unit"},
    "areas.edit_type":  {"es": "Editar Tipo",              "en": "Edit Type"},
    "areas.new_type":   {"es": "Nuevo Tipo de Usuario",    "en": "New User Type"},
    # Field labels
    "areas.field_area_name":  {"es": "Nombre del área  (máx. {n} caracteres)",            "en": "Area name  (max. {n} characters)"},
    "areas.field_unit_name":  {"es": "Nombre de la unidad académica  (máx. {n} caracteres)", "en": "Academic unit name  (max. {n} characters)"},
    "areas.field_type_name":  {"es": "Nombre del tipo de usuario  (máx. {n} caracteres)", "en": "User type name  (max. {n} characters)"},
    "areas.field_unidad":     {"es": "Unidad académica",                                   "en": "Academic unit"},
    "areas.no_unidad":        {"es": "— Sin unidad —",                                    "en": "— No unit —"},

    # ── Admin: LockerAssignmentScreen (detallado) ────────────────────────────
    "assignment.assigned_label":  {"es": "Locker asignado (para liberar)", "en": "Assigned locker (to release)"},
    "assignment.no_active":       {"es": "Sin asignaciones activas",        "en": "No active assignments"},
    "assignment.no_users":        {"es": "Sin usuarios activos",            "en": "No active users"},
    "assignment.btn_assign":      {"es": "Asignar",                        "en": "Assign"},
    "assignment.btn_release":     {"es": "Liberar locker",                 "en": "Release locker"},
    "assignment.active_section":  {"es": "Asignaciones activas",           "en": "Active assignments"},
    "assignment.manual_open":     {"es": "Abrir locker manualmente",       "en": "Open locker manually"},
    "assignment.no_permission":   {"es": "Tu rol no permite editar asignaciones", "en": "Your role does not allow editing assignments"},
    "assignment.no_active_list":  {"es": "No hay asignaciones activas",    "en": "No active assignments"},
    "assignment.err_select":      {"es": "Selecciona alumno y locker disponibles", "en": "Select a student and available locker"},
    "assignment.err_already":     {"es": "Ese alumno ya tiene asignado ese locker", "en": "That student already has that locker assigned"},
    "assignment.ok_assigned":     {"es": "Locker {n} asignado correctamente", "en": "Locker {n} assigned successfully"},
    "assignment.err_select_release": {"es": "Selecciona un locker asignado para liberar", "en": "Select an assigned locker to release"},
    "assignment.ok_released":     {"es": "Locker {n} liberado correctamente", "en": "Locker {n} released successfully"},
    "assignment.already_free":    {"es": "Ese locker ya no tenía una asignación activa", "en": "That locker had no active assignment"},
    "assignment.opening":         {"es": "Abriendo Locker {n}…",           "en": "Opening Locker {n}…"},
    "assignment.opened_ok":       {"es": "Locker {n} abierto",             "en": "Locker {n} opened"},
    "assignment.open_failed":     {"es": "No se pudo abrir Locker {n}",    "en": "Could not open Locker {n}"},

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
    """Texto del botón de cambio de idioma (idioma destino)."""
    return "🌐 English" if _lang == "es" else "🌐 Español"
