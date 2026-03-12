# -*- coding: utf-8 -*-
"""Replaces emoji characters with Linux-safe text across all UI files."""

files = [
    'ui/admin/dashboard.py',
    'ui/admin/users_catalog.py',
    'ui/admin/lockers_catalog.py',
    'ui/admin/areas_catalog.py',
    'ui/admin/register_user.py',
    'ui/locker_screen/standby_screen.py',
    'ui/locker_screen/user_display.py',
]

replacements = [
    # Theme toggle buttons
    ('"🌙"', '"Noche"'),
    ('"☀️"', '"Dia"'),
    # Header labels
    ('"🛡  Super Admin"', '"Super Admin"'),
    ('"🔒  Lockers"', '"Lockers"'),
    ('"📍  Catálogos"', '"Catálogos"'),
    ('"👤  Usuarios"', '"Usuarios"'),
    # Catalog card icons
    ('"icon":   "👤"', '"icon":   "USR"'),
    ('"icon":   "🔒"', '"icon":   "LCK"'),
    ('"icon":   "📍"', '"icon":   "ZNA"'),
    ('"icon":   "🏛️"', '"icon":   "UND"'),
    ('"icon":   "🏷️"', '"icon":   "TIP"'),
    ('"icon":   "📋"', '"icon":   "HST"'),
    # Buttons
    ('"➕  Registrar Usuario"', '"+  Registrar Usuario"'),
    ('"💾  Guardar"', '"Guardar"'),
    ('"💾  Crear Locker"', '"Crear Locker"'),
    ('"💾  Guardar estado"', '"Guardar estado"'),
    ('"🗑  Inhabilitar"', '"Inhabilitar"'),
    ('"✏️  Editar"', '"Editar"'),
    ('"✖  Cancelar"', '"Cancelar"'),
    ('"📸  Capturar"', '"Capturar"'),
    ('"💾  Registrar"', '"Registrar"'),
    ('"🏠  Volver al dashboard"', '"Volver al inicio"'),
    ('"➕  Registrar otro usuario"', '"+  Registrar otro usuario"'),
    ('text="➕"', 'text="+"'),
    # Status / info text
    ('"✅  Perfil facial capturado"', '"(OK) Perfil facial capturado"'),
    ('"⚠️  OpenCV no instalado', '"(!) OpenCV no instalado'),
    ('"⚠️  Cámara no disponible"', '"(!) Cámara no disponible"'),
    ('"⚠️  No se detectó rostro"', '"(!) No se detectó rostro"'),
    ('"⚠️  No se pudo extraer el perfil"', '"(!) No se pudo extraer el perfil"'),
    ('"⚠️  OpenCV no disponible"', '"(!) OpenCV no disponible"'),
    ('"✓  Rostro detectado', '"Rostro detectado'),
    ('text="Perfil frontal listo  📸"', 'text="Perfil frontal listo"'),
    # User/locker display
    ('"✓"', '"OK"'),
    ('"✅"', '"[OK]"'),
    ('f"✅ {n} perfil', 'f"[OK] {n} perfil'),
    ('"⚠️  Sin rostro registrado"', '"(!) Sin rostro registrado"'),
    ('"⚠️  Hay lockers', '"(!) Hay lockers'),
    ('f"❌  Error al registrar', 'f"Error al registrar'),
    ('f"✅ {asign', 'f"[OK] {asign'),
    # Standby icon
    ('"🎓"', '""'),
    # Step 5 big icon
    ('"✅"', '"[OK]"'),
]

for path in files:
    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()
        new = content
        for old, rep in replacements:
            new = new.replace(old, rep)
        if new != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new)
            print(f'Updated: {path}')
        else:
            print(f'No change: {path}')
    except FileNotFoundError:
        print(f'Not found: {path}')

print('Done.')
