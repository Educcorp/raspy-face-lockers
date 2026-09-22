#!/usr/bin/env python3
"""
Script para aplicar la migración de permisoActivacion.
Uso: python3 apply_migration.py
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

# Cargar configuración
from webapp.db import cursor

def apply_migration():
    """Aplica la migración SQL"""
    migration_file = Path(__file__).parent / "webapp" / "migrations" / "add_permiso_activacion.sql"
    
    if not migration_file.exists():
        print(f"❌ Archivo de migración no encontrado: {migration_file}")
        return False
    
    try:
        print(f"📋 Leyendo migración: {migration_file}")
        with open(migration_file, 'r') as f:
            sql_content = f.read()
        
        print("🔄 Ejecutando migración...")
        with cursor() as cur:
            # Ejecutar el SQL completo
            cur.execute(sql_content)
        
        print("✅ Migración aplicada exitosamente!")
        
        # Verificar que la columna se creó
        print("\n📊 Verificando columna permisoactivacion...")
        with cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'usuarios' AND column_name = 'permisoactivacion'
            """)
            result = cur.fetchone()
            if result:
                print(f"   ✓ Columna: {result['column_name']}")
                print(f"   ✓ Tipo: {result['data_type']}")
                print(f"   ✓ Nulable: {'No' if result['is_nullable'] == 'NO' else 'Sí'}")
                print(f"   ✓ Valor por defecto: {result['column_default']}")
                return True
            else:
                print("❌ No se encontró la columna permisoactivacion")
                return False
    
    except Exception as e:
        print(f"❌ Error al aplicar la migración:")
        print(f"   {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    # Asegurar que estamos en el contexto de la app Flask
    from flask import Flask
    from webapp.app import create_app
    
    app = create_app()
    with app.app_context():
        success = apply_migration()
        sys.exit(0 if success else 1)
