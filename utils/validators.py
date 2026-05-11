"""
Field-level validation utilities for the admin panel.

All validate_* functions return None on success, or a str error message on failure.
"""
from __future__ import annotations

import re

# ── Regex patterns ────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_NAME_RE  = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿÁÉÍÓÚáéíóúÑñÜü\s'\-\.]+$")

# ── Límites de caracteres (reflejan las restricciones en init_db.sql) ─────────
MAX_NOMBRE      = 100
MAX_APELLIDO    = 100
MAX_EMAIL       = 100
MAX_TEL         = 20
MIN_MAT_DIGITS  = 5
MAX_MAT_DIGITS  = 10   # matrícula INTEGER → no más de 10 dígitos seguros
MAX_AREA_NOMBRE = 30
MAX_UNIDAD_NOMBRE = 100
MAX_ZONA        = 100
MAX_TIPO_NOMBRE = 60


# ── Validadores de campos de usuario ─────────────────────────────────────────

def validate_name(value: str, field: str = "Campo", max_len: int = MAX_NOMBRE) -> str | None:
    """Valida un nombre propio: letras, espacios, guiones y acentos."""
    if len(value) < 2:
        return f"{field}: mínimo 2 caracteres"
    if len(value) > max_len:
        return f"{field}: máximo {max_len} caracteres"
    if not _NAME_RE.match(value):
        return f"{field}: solo letras, espacios y guiones"
    return None


def validate_matricula(value: str) -> str | None:
    """Valida una matrícula numérica."""
    if not value.isdigit():
        return "La matrícula solo debe contener números"
    if len(value) < MIN_MAT_DIGITS:
        return f"La matrícula debe tener al menos {MIN_MAT_DIGITS} dígitos"
    if len(value) > MAX_MAT_DIGITS:
        return f"La matrícula no puede exceder {MAX_MAT_DIGITS} dígitos"
    return None


def validate_email(value: str) -> str | None:
    """
    Valida que el correo tenga formato correcto.
    Acepta dominios institucionales/académicos (ej: @ucol.mx, @alumnos.ucol.mx)
    y correos comunes (gmail.com, hotmail.com, etc.) sin consultar DNS.
    """
    if len(value) > MAX_EMAIL:
        return f"El correo no puede exceder {MAX_EMAIL} caracteres"
    if not _EMAIL_RE.match(value):
        return "Formato de correo inválido  (ej: usuario@ucol.mx)"
    return None


def validate_tel(value: str) -> str | None:
    """Campo opcional — solo valida si hay contenido."""
    if not value:
        return None
    clean = re.sub(r"[\s\-\+\(\)]", "", value)
    if not clean.isdigit():
        return "Teléfono: solo números y los símbolos  +  -  (  )  espacio"
    if len(clean) < 10:
        return "Teléfono: mínimo 10 dígitos"
    if len(clean) > 15:
        return "Teléfono: máximo 15 dígitos"
    return None


# ── Validadores de catálogos ──────────────────────────────────────────────────

def validate_area_nombre(value: str) -> str | None:
    if len(value) < 2:
        return "Nombre del área: mínimo 2 caracteres"
    if len(value) > MAX_AREA_NOMBRE:
        return f"Nombre del área: máximo {MAX_AREA_NOMBRE} caracteres"
    return None


def validate_unidad_nombre(value: str) -> str | None:
    if len(value) < 2:
        return "Nombre de la unidad: mínimo 2 caracteres"
    if len(value) > MAX_UNIDAD_NOMBRE:
        return f"Nombre de la unidad: máximo {MAX_UNIDAD_NOMBRE} caracteres"
    return None


def validate_zona(value: str) -> str | None:
    """Campo opcional."""
    if not value:
        return None
    if len(value) > MAX_ZONA:
        return f"Zona: máximo {MAX_ZONA} caracteres"
    return None


def validate_tipo_nombre(value: str) -> str | None:
    if len(value) < 2:
        return "Nombre del tipo: mínimo 2 caracteres"
    if len(value) > MAX_TIPO_NOMBRE:
        return f"Nombre del tipo: máximo {MAX_TIPO_NOMBRE} caracteres"
    return None


# ── Utilidad para limitar longitud de StringVar ───────────────────────────────

def limit_var(var, max_len: int) -> None:
    """
    Asocia un trace a un tk.StringVar que recorta la entrada al límite indicado.
    Llamar una vez tras crear la variable.
    """
    def _truncate(*_):
        v = var.get()
        if len(v) > max_len:
            var.set(v[:max_len])
    var.trace_add("write", _truncate)
