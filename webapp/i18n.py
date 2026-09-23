"""
webapp/i18n.py – Traducción ES / EN del panel web.

Equivalente web de ui/i18n.py (la app de escritorio). El idioma activo vive
en la cookie ``lang`` (la cambia la ruta /lang/<code> desde el botón del nav)
y las plantillas lo usan con:

    {{ tr("nav.inicio") }}                 → texto en el idioma activo
    {{ tr("users.showing", a=1, b=10) }}   → con interpolación
    {{ u.estado | tr_status }}             → estados de BD (activo, inactivo…)
    {{ current_lang() }}                   → "es" | "en"

Autocontenido a propósito: la webapp se despliega sola en Railway y no debe
depender de ui/ (que importa customtkinter).
"""

from __future__ import annotations

from flask import has_request_context, request

LANGS = ("es", "en")
DEFAULT_LANG = "es"
COOKIE_NAME = "lang"

STRINGS: dict[str, dict[str, str]] = {
    # ── Nav / shell (base.html) ──────────────────────────────────────────────
    "app.title":            {"es": "Panel de Control", "en": "Control Panel"},
    "nav.inicio":           {"es": "Inicio", "en": "Home"},
    "nav.usuarios":         {"es": "Usuarios", "en": "Users"},
    "nav.lockers":          {"es": "Lockers", "en": "Lockers"},
    "nav.asignaciones":     {"es": "Asignaciones", "en": "Assignments"},
    "nav.historial":        {"es": "Historial", "en": "History"},
    "nav.recursos":         {"es": "Recursos", "en": "Resources"},
    "nav.catalogos":        {"es": "Catálogos", "en": "Catalogs"},
    "nav.unidades":         {"es": "Unidades académicas", "en": "Academic units"},
    "nav.areas":            {"es": "Áreas", "en": "Areas"},
    "nav.mi_perfil":        {"es": "Mi perfil", "en": "My profile"},
    "nav.cerrar_sesion":    {"es": "Cerrar sesión", "en": "Log out"},
    "nav.open_menu":        {"es": "Abrir menú", "en": "Open menu"},
    "nav.theme_dark":       {"es": "Cambiar a modo oscuro", "en": "Switch to dark mode"},
    "nav.theme_light":      {"es": "Cambiar a modo claro", "en": "Switch to light mode"},
    "nav.lang_switch":      {"es": "Cambiar idioma a inglés", "en": "Switch language to Spanish"},
    # Texto del botón = idioma destino (igual que lang_btn_text() del escritorio)
    "nav.lang_btn":         {"es": "English", "en": "Español"},
    "nav.lang_btn_short":   {"es": "EN", "en": "ES"},

    # ── Comunes ──────────────────────────────────────────────────────────────
    "common.cancel":        {"es": "Cancelar", "en": "Cancel"},
    "common.confirm":       {"es": "Confirmar", "en": "Confirm"},
    "common.save":          {"es": "Guardar", "en": "Save"},
    "common.save_changes":  {"es": "Guardar cambios", "en": "Save changes"},
    "common.create":        {"es": "Crear", "en": "Create"},
    "common.edit":          {"es": "Editar", "en": "Edit"},
    "common.delete":        {"es": "Eliminar", "en": "Delete"},
    "common.activate":      {"es": "Activar", "en": "Activate"},
    "common.deactivate":    {"es": "Desactivar", "en": "Deactivate"},
    "common.search":        {"es": "Buscar", "en": "Search"},
    "common.search_by":     {"es": "Buscar por", "en": "Search by"},
    "common.clear":         {"es": "Limpiar", "en": "Clear"},
    "common.all":           {"es": "Todos", "en": "All"},
    "common.name":          {"es": "Nombre", "en": "Name"},
    "common.matricula":     {"es": "Matrícula", "en": "ID number"},
    "common.unit":          {"es": "Unidad", "en": "Unit"},
    "common.academic_unit": {"es": "Unidad académica", "en": "Academic unit"},
    "common.area":          {"es": "Área", "en": "Area"},
    "common.status":        {"es": "Estado", "en": "Status"},
    "common.type":          {"es": "Tipo", "en": "Type"},
    "common.user":          {"es": "Usuario", "en": "User"},
    "common.locker":        {"es": "Locker", "en": "Locker"},
    "common.since":         {"es": "Desde", "en": "Since"},
    "common.date":          {"es": "Fecha", "en": "Date"},
    "common.time":          {"es": "Hora", "en": "Time"},
    "common.prev":          {"es": "Anterior", "en": "Previous"},
    "common.next":          {"es": "Siguiente", "en": "Next"},
    "common.prev_page":     {"es": "Página anterior", "en": "Previous page"},
    "common.next_page":     {"es": "Página siguiente", "en": "Next page"},
    "common.optional":      {"es": "(opcional)", "en": "(optional)"},

    # ── Estados de BD (filtro tr_status) ─────────────────────────────────────
    "status.activo":        {"es": "Activo", "en": "Active"},
    "status.inactivo":      {"es": "Inactivo", "en": "Inactive"},
    "status.suspendido":    {"es": "Suspendido", "en": "Suspended"},
    "status.mantenimiento": {"es": "Mantenimiento", "en": "Maintenance"},
    "status.vencido":       {"es": "Vencido", "en": "Expired"},
    "status.pendiente":     {"es": "Pendiente", "en": "Pending"},
    "status.registrado":    {"es": "Registrado", "en": "Registered"},
    "status.permitido":     {"es": "Permitido", "en": "Granted"},
    "status.denegado":      {"es": "Denegado", "en": "Denied"},

    # ── Permisos de activación ───────────────────────────────────────────────
    "perm.locker":          {"es": "Locker", "en": "Locker"},
    "perm.recurso":         {"es": "Recurso compartido", "en": "Shared resource"},
    "perm.ambos":           {"es": "Ambos", "en": "Both"},
    "perm.select":          {"es": "Selecciona los permisos", "en": "Select permissions"},

    # ── Login ────────────────────────────────────────────────────────────────
    "login.page_title":     {"es": "Acceso de Administrador", "en": "Administrator Access"},
    "login.heading":        {"es": "Gestión de Acceso Seguro", "en": "Secure Access Management"},
    "login.subtitle":       {"es": "Acceso administrativo con matrícula y PIN", "en": "Administrative access with ID number and PIN"},
    "login.pin":            {"es": "PIN", "en": "PIN"},
    "login.enter":          {"es": "Entrar", "en": "Sign in"},

    # ── Dashboard ────────────────────────────────────────────────────────────
    "dash.eyebrow":         {"es": "PANEL DE ADMINISTRACIÓN", "en": "ADMINISTRATION PANEL"},
    "dash.heading":         {"es": "Centro de Control", "en": "Control Center"},
    "dash.intro":           {"es": "Supervisa el estado de los lockers y gestiona el acceso de los usuarios.",
                             "en": "Monitor locker status and manage user access."},
    "dash.view_users":      {"es": "Ver usuarios", "en": "View users"},
    "dash.new_user":        {"es": "Nuevo usuario", "en": "New user"},
    "dash.summary":         {"es": "RESUMEN", "en": "SUMMARY"},
    "dash.overview":        {"es": "Vista general", "en": "Overview"},
    "dash.cap.users":       {"es": "Usuarios", "en": "Users"},
    "dash.cap.lockers":     {"es": "Lockers", "en": "Lockers"},
    "dash.cap.assignments": {"es": "Asignaciones", "en": "Assignments"},
    "dash.cap.activity":    {"es": "Actividad", "en": "Activity"},
    "dash.stat.users":      {"es": "Usuarios activos", "en": "Active users"},
    "dash.stat.lockers":    {"es": "Lockers activos", "en": "Active lockers"},
    "dash.stat.assignments":{"es": "Asignaciones activas", "en": "Active assignments"},
    "dash.stat.access":     {"es": "Accesos registrados hoy", "en": "Accesses logged today"},
    "dash.monitoring":      {"es": "MONITOREO", "en": "MONITORING"},
    "dash.locker_status":   {"es": "Estado de lockers", "en": "Locker status"},
    "dash.available":       {"es": "Disponible", "en": "Available"},
    "dash.occupied":        {"es": "Ocupado", "en": "Occupied"},
    "dash.maintenance":     {"es": "Mantenimiento", "en": "Maintenance"},
    "dash.in_use":          {"es": "En uso", "en": "In use"},
    "dash.ready":           {"es": "Listo para asignación", "en": "Ready to assign"},
    "dash.free":            {"es": "Libre", "en": "Free"},
    "dash.out_of_service":  {"es": "Locker fuera de servicio", "en": "Locker out of service"},
    "dash.review":          {"es": "Revisar", "en": "Check"},
    "dash.notice_title":    {"es": "{n} usuario(s) esperan registro facial", "en": "{n} user(s) awaiting face registration"},
    "dash.notice_body":     {"es": "Estos usuarios fueron registrados pero todavía no cuentan con un rostro capturado.",
                             "en": "These users are registered but don't have a captured face yet."},
    "dash.notice_cta":      {"es": "Ir a usuarios y capturar rostro", "en": "Go to users and capture face"},

    # ── Usuarios: lista ──────────────────────────────────────────────────────
    "users.heading":        {"es": "Gestión de Usuarios", "en": "User Management"},
    "users.intro":          {"es": "Consulta, busca y administra los usuarios registrados.",
                             "en": "View, search and manage registered users."},
    "users.new":            {"es": "+ Nuevo usuario", "en": "+ New user"},
    "users.search_ph":      {"es": "Escribe para buscar...", "en": "Type to search..."},
    "users.showing":        {"es": "Mostrando <strong>{a}–{b}</strong> de <strong>{total}</strong> usuarios",
                             "en": "Showing <strong>{a}–{b}</strong> of <strong>{total}</strong> users"},
    "users.none_found":     {"es": "No se encontraron usuarios", "en": "No users found"},
    "users.search_label":   {"es": "Búsqueda:", "en": "Search:"},
    "users.col.perms":      {"es": "Permisos", "en": "Permissions"},
    "users.col.face":       {"es": "Rostro", "en": "Face"},
    "users.face_ok":        {"es": "Registrado", "en": "Registered"},
    "users.face_pending":   {"es": "Pendiente", "en": "Pending"},
    "users.none_for":       {"es": "No se encontraron usuarios para", "en": "No users found for"},
    "users.none":           {"es": "No hay usuarios registrados.", "en": "No users registered."},
    "users.pagination":     {"es": "Paginación de usuarios", "en": "User pagination"},

    # ── Usuarios: formulario ─────────────────────────────────────────────────
    "form.edit_title":      {"es": "Editar Usuario", "en": "Edit User"},
    "form.new_title":       {"es": "Registro de Nuevo Usuario", "en": "New User Registration"},
    "form.no_face_1":       {"es": "Este usuario aún no tiene rostro registrado.", "en": "This user doesn't have a registered face yet."},
    "form.no_face_link":    {"es": "Registrar rostro ahora", "en": "Register face now"},
    "form.no_face_2":       {"es": "usando la cámara de este equipo.", "en": "using this device's camera."},
    "form.first_name":      {"es": "Nombre(s)", "en": "First name(s)"},
    "form.last_name1":      {"es": "Apellido paterno", "en": "Paternal surname"},
    "form.last_name2":      {"es": "Apellido materno", "en": "Maternal surname"},
    "form.email":           {"es": "Correo institucional", "en": "Institutional email"},
    "form.phone":           {"es": "Teléfono (opcional)", "en": "Phone (optional)"},
    "form.user_type":       {"es": "Tipo de usuario", "en": "User type"},
    "form.perms":           {"es": "Permisos de activación", "en": "Activation permissions"},
    "form.pin":             {"es": "PIN inicial (4 a 8 dígitos)", "en": "Initial PIN (4 to 8 digits)"},
    "form.actions":         {"es": "Acciones", "en": "Actions"},
    "form.recapture":       {"es": "Volver a capturar rostro", "en": "Recapture face"},
    "form.capture":         {"es": "Registrar rostro", "en": "Register face"},
    "form.new_pin":         {"es": "Generar nuevo PIN", "en": "Generate new PIN"},
    "form.delete_confirm":  {"es": "¿Eliminar este usuario permanentemente? Esta acción no se puede deshacer.",
                             "en": "Delete this user permanently? This action cannot be undone."},
    "form.delete":          {"es": "Eliminar permanentemente", "en": "Delete permanently"},

    # ── Captura facial ───────────────────────────────────────────────────────
    "face.page_title":      {"es": "Registrar rostro", "en": "Register face"},
    "face.heading":         {"es": "Captura de Reconocimiento Facial", "en": "Facial Recognition Capture"},
    "face.intro":           {"es": "Pide a {name} que se coloque frente a la cámara y siga la esfera, la captura es automática.",
                             "en": "Ask {name} to stand in front of the camera and follow the sphere; capture is automatic."},
    "face.searching":       {"es": "Buscando tu rostro…", "en": "Looking for your face…"},
    "face.progress":        {"es": "Progreso", "en": "Progress"},
    "face.count":           {"es": "{done} de {total} poses capturadas", "en": "{done} of {total} poses captured"},
    "face.save":            {"es": "Guardar rostro", "en": "Save face"},
    "face.manual_summary":  {"es": "¿Problemas para que te detecte? Captura manual", "en": "Trouble being detected? Manual capture"},
    "face.manual_btn":      {"es": "Capturar esta pose ahora", "en": "Capture this pose now"},
    "face.pose.frontal":    {"es": "Frontal", "en": "Front"},
    "face.pose.derecha":    {"es": "Derecha", "en": "Right"},
    "face.pose.izquierda":  {"es": "Izquierda", "en": "Left"},
    "face.pose.arriba":     {"es": "Arriba", "en": "Up"},
    "face.instr.frontal":   {"es": "Mira directo a la cámara", "en": "Look straight at the camera"},
    "face.instr.derecha":   {"es": "Gira tu cabeza hacia tu DERECHA", "en": "Turn your head to your RIGHT"},
    "face.instr.izquierda": {"es": "Gira tu cabeza hacia tu IZQUIERDA", "en": "Turn your head to your LEFT"},
    "face.instr.arriba":    {"es": "Levanta un poco la barbilla, mira hacia ARRIBA", "en": "Lift your chin a little, look UP"},
    # Textos que usa el JavaScript de la captura
    "face.js.count":        {"es": "{done} de {total} poses capturadas", "en": "{done} of {total} poses captured"},
    "face.js.all_done":     {"es": "¡Todas las poses capturadas!", "en": "All poses captured!"},
    "face.js.cam_error":    {"es": "No se pudo acceder a la cámara: ", "en": "Could not access the camera: "},
    "face.js.no_detector":  {"es": "No se pudo cargar la detección automática — usa la captura manual de abajo.",
                             "en": "Automatic detection couldn't load — use the manual capture below."},
    "face.js.detector_off": {"es": "Detección no disponible", "en": "Detection unavailable"},
    "face.js.no_face":      {"es": "No detecto tu rostro, acércate y mira a la cámara.", "en": "I can't see your face — come closer and look at the camera."},
    "face.js.calibrating":  {"es": "Calibrando… mantente frente a la cámara.", "en": "Calibrating… stay in front of the camera."},
    "face.js.farther":      {"es": "Aléjate un poco de la cámara", "en": "Move a bit away from the camera"},
    "face.js.closer":       {"es": "Acércate un poco a la cámara", "en": "Move a bit closer to the camera"},
    "face.js.center":       {"es": "Céntrate en el cuadro", "en": "Center yourself in the frame"},
    "face.js.follow":       {"es": "Sigue la esfera hacia la posición indicada", "en": "Follow the sphere to the indicated position"},
    "face.js.hold":         {"es": "¡Perfecto, mantente así!", "en": "Perfect, hold still!"},
    "face.js.capturing":    {"es": "Capturando rostro…", "en": "Capturing face…"},
    "face.js.err_no_face":  {"es": "No se detectó ningún rostro al capturar. Inténtalo de nuevo.", "en": "No face was detected during capture. Try again."},
    "face.js.err_extract":  {"es": "No se pudo procesar el rostro. Intenta de nuevo con mejor luz.", "en": "The face couldn't be processed. Try again with better lighting."},
    "face.js.err_dup":      {"es": "Este rostro ya está registrado a nombre de {name}.", "en": "This face is already registered to {name}."},
    "face.js.other_user":   {"es": "otro usuario", "en": "another user"},
    "face.js.err_generic":  {"es": "No se pudo capturar. Intenta de nuevo.", "en": "Capture failed. Try again."},
    "face.js.err_conn":     {"es": "Error de conexión: ", "en": "Connection error: "},

    # ── Historial ────────────────────────────────────────────────────────────
    "hist.page_title":      {"es": "Historial de Accesos", "en": "Access History"},
    "hist.eyebrow":         {"es": "SEGURIDAD", "en": "SECURITY"},
    "hist.heading":         {"es": "Registro de Accesos del Sistema", "en": "System Access Log"},
    "hist.intro":           {"es": "Consulta y filtra los accesos registrados en el sistema.", "en": "View and filter the accesses logged in the system."},
    "hist.search_ph":       {"es": "Usuario o matrícula...", "en": "User or ID number..."},
    "hist.result":          {"es": "Resultado", "en": "Result"},
    "hist.granted_pl":      {"es": "Permitidos", "en": "Granted"},
    "hist.denied_pl":       {"es": "Denegados", "en": "Denied"},
    "hist.granted":         {"es": "Permitido", "en": "Granted"},
    "hist.denied":          {"es": "Denegado", "en": "Denied"},
    "hist.reason":          {"es": "Motivo", "en": "Reason"},
    "hist.showing":         {"es": "Mostrando <strong>{a}</strong> – <strong>{b}</strong> de <strong>{total}</strong> registros",
                             "en": "Showing <strong>{a}</strong> – <strong>{b}</strong> of <strong>{total}</strong> records"},
    "hist.none":            {"es": "No se encontraron registros", "en": "No records found"},
    "hist.none_hint":       {"es": "Intenta cambiar los filtros o realizar otra búsqueda.", "en": "Try changing the filters or searching again."},
    "hist.pagination":      {"es": "Paginación de registros", "en": "Records pagination"},
    # Motivos (mismas claves que access_log_service.MOTIVO_LABELS)
    "motivo.facial":              {"es": "Facial", "en": "Facial"},
    "motivo.no_reconocido":       {"es": "Rostro no reconocido", "en": "Face not recognized"},
    "motivo.pin":                 {"es": "PIN", "en": "PIN"},
    "motivo.pin_incorrecto":      {"es": "PIN incorrecto", "en": "Incorrect PIN"},
    "motivo.limite_intentos":     {"es": "Exceso de intentos", "en": "Too many attempts"},
    "motivo.limite_intentos_pin": {"es": "Exceso de intentos PIN", "en": "Too many PIN attempts"},
    "motivo.matricula_incorrecta":{"es": "Matrícula incorrecta", "en": "Incorrect ID number"},
    "motivo.sin_asignacion":      {"es": "Sin asignación de locker", "en": "No locker assigned"},
    "motivo.pin_cancelado":       {"es": "PIN cancelado", "en": "PIN cancelled"},
    "motivo.puerta_cerrada":      {"es": "Puerta cerrada", "en": "Door closed"},
    "motivo.puerta_no_cerrada":   {"es": "Puerta no cerrada", "en": "Door not closed"},

    # ── Lockers ──────────────────────────────────────────────────────────────
    "lockers.heading":      {"es": "Gestión de Casilleros", "en": "Locker Management"},
    "lockers.new":          {"es": "Nuevo locker", "en": "New locker"},
    "lockers.delete_confirm": {"es": "¿Eliminar este locker permanentemente?", "en": "Delete this locker permanently?"},
    "lockers.delete":       {"es": "Eliminar locker", "en": "Delete locker"},
    "lockers.protected":    {"es": "Los 4 lockers físicos originales no se pueden eliminar.", "en": "The 4 original physical lockers can't be deleted."},

    # ── Asignaciones ─────────────────────────────────────────────────────────
    "assign.heading":       {"es": "Asignación de Casilleros", "en": "Locker Assignment"},
    "assign.assign_locker": {"es": "Asignar locker", "en": "Assign locker"},
    "assign.available":     {"es": "Locker disponible", "en": "Available locker"},
    "assign.matr":          {"es": "Matr.", "en": "ID"},
    "assign.assign":        {"es": "Asignar", "en": "Assign"},
    "assign.active":        {"es": "Asignaciones activas", "en": "Active assignments"},
    "assign.release_confirm": {"es": "¿Liberar este locker?", "en": "Release this locker?"},
    "assign.release":       {"es": "Liberar", "en": "Release"},
    "assign.none":          {"es": "No hay asignaciones activas.", "en": "No active assignments."},

    # ── Recursos compartidos ─────────────────────────────────────────────────
    "res.page_title":       {"es": "Recursos compartidos", "en": "Shared resources"},
    "res.eyebrow":          {"es": "RECURSO COMPARTIDO", "en": "SHARED RESOURCE"},
    "res.heading":          {"es": "Recursos compartidos", "en": "Shared resources"},
    "res.intro":            {"es": "Activa o desactiva los recursos de uso compartido.",
                             "en": "Turn shared-use resources on or off."},
    "res.name":             {"es": "Recurso {n}", "en": "Resource {n}"},
    "res.desc":             {"es": "Recurso de uso compartido.", "en": "Shared-use resource."},
    "res.active":           {"es": "Activo", "en": "Active"},
    "res.inactive":         {"es": "Inactivo", "en": "Inactive"},
    "res.activate":         {"es": "Activar", "en": "Activate"},
    "res.deactivate":       {"es": "Desactivar", "en": "Deactivate"},
    "res.demo_note":        {"es": "Vista de demostración: el estado se guarda solo en este navegador y todavía no activa el recurso real.",
                             "en": "Demo view: the status is only saved in this browser and doesn't turn on the real resource yet."},
    "res.toggled_on":       {"es": "{name} activado", "en": "{name} activated"},
    "res.toggled_off":      {"es": "{name} desactivado", "en": "{name} deactivated"},

    # ── Catálogos ────────────────────────────────────────────────────────────
    "areas.heading":        {"es": "Gestión de Áreas", "en": "Area Management"},
    "areas.new":            {"es": "Nueva área", "en": "New area"},
    "areas.unit_optional":  {"es": "Unidad académica (opcional)", "en": "Academic unit (optional)"},
    "areas.delete_confirm": {"es": "¿Eliminar esta área permanentemente?", "en": "Delete this area permanently?"},
    "units.page_title":     {"es": "Gestión de Unidades Académicas", "en": "Academic Unit Management"},
    "units.heading":        {"es": "Unidades Académicas", "en": "Academic Units"},
    "units.new":            {"es": "Nueva unidad", "en": "New unit"},
    "units.zone":           {"es": "Zona", "en": "Zone"},
    "units.zone_optional":  {"es": "Zona (opcional)", "en": "Zone (optional)"},
    "units.delete_confirm": {"es": "¿Eliminar esta unidad permanentemente?", "en": "Delete this unit permanently?"},
    "types.heading":        {"es": "Gestión de Roles", "en": "Role Management"},
    "types.new":            {"es": "Nuevo tipo", "en": "New type"},
}


def get_lang() -> str:
    """Idioma activo según la cookie (``es`` por defecto)."""
    if has_request_context():
        lang = request.cookies.get(COOKIE_NAME, DEFAULT_LANG)
        if lang in LANGS:
            return lang
    return DEFAULT_LANG


def t(key: str, **kwargs) -> str:
    """Texto de ``key`` en el idioma activo (cae a español y luego a la key)."""
    entry = STRINGS.get(key, {})
    text = entry.get(get_lang(), entry.get(DEFAULT_LANG, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def tr_status(value) -> str:
    """Traduce un estado de BD (activo, inactivo, mantenimiento…). Si no se
    conoce, lo devuelve capitalizado tal cual."""
    raw = str(value or "").strip()
    key = f"status.{raw.lower()}"
    if key in STRINGS:
        return t(key)
    return raw.capitalize() if raw else "—"


def tr_motivo(value, fallback: str | None = None) -> str:
    """Traduce el motivo de un acceso (facial, pin_incorrecto…)."""
    key = f"motivo.{value}"
    if key in STRINGS:
        return t(key)
    return fallback or (str(value) if value else "—")


def init_app(app) -> None:
    """Registra ``tr``, ``tr_status``, ``tr_motivo`` y ``current_lang`` en Jinja."""
    app.jinja_env.globals["tr"] = t
    app.jinja_env.globals["current_lang"] = get_lang
    app.jinja_env.filters["tr_status"] = tr_status
    app.jinja_env.filters["tr_motivo"] = tr_motivo
