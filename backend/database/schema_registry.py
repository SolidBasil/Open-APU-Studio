"""
schema_registry.py
==================
Sistema de validación por tipos de campo, definido en Python.

Las reglas viven en Python, no se inspeccionan PRAGMA table_info().
Cambiar de motor de BD (ej. PostgreSQL) no rompe la validación.

Uso:
    registry = SchemaRegistry()
    registry.validate("insumos", {"costo_final": -5})  # lanza ValidationError
"""

from __future__ import annotations

from backend.database.exceptions import ValidationError  # noqa: F401 — re-exportado:
# el código que hace `from backend.database.schema_registry import ValidationError`
# sigue funcionando; la definición real vive en exceptions.py (Fase 4b).

# Tasa de IVA por defecto en México. Coincide con schema.sql
# (columna proyectos.iva_porcentaje DEFAULT 16.0) — si la tasa cambia,
# este es el único lugar en Python que hay que tocar; antes estaba
# repetido como número mágico en exportar.py, latex.py (x2) e importar.py.
IVA_PORCENTAJE_DEFAULT = 16.0


# ── Field types ────────────────────────────────────────────────────

class FloatField:
    def __init__(self, min: float | None = None, max: float | None = None,
                 required: bool = False):
        self.min = min
        self.max = max
        self.required = required

    def validate(self, valor):
        if valor is None:
            if self.required:
                raise ValidationError("Campo requerido")
            return
        if not isinstance(valor, (int, float)):
            raise ValidationError(f"Se esperaba número, se recibió {type(valor).__name__}")
        if self.min is not None and valor < self.min:
            raise ValidationError(f"Valor {valor} menor que el mínimo {self.min}")
        if self.max is not None and valor > self.max:
            raise ValidationError(f"Valor {valor} mayor que el máximo {self.max}")


class IntField:
    def __init__(self, min: int | None = None, max: int | None = None,
                 required: bool = False):
        self.min = min
        self.max = max
        self.required = required

    def validate(self, valor):
        if valor is None:
            if self.required:
                raise ValidationError("Campo requerido")
            return
        if not isinstance(valor, int) or isinstance(valor, bool):
            raise ValidationError(f"Se esperaba entero, se recibió {type(valor).__name__}")
        if self.min is not None and valor < self.min:
            raise ValidationError(f"Valor {valor} menor que el mínimo {self.min}")
        if self.max is not None and valor > self.max:
            raise ValidationError(f"Valor {valor} mayor que el máximo {self.max}")


class StringField:
    def __init__(self, choices: tuple | list | None = None,
                 max_length: int | None = None, required: bool = False):
        self.choices = tuple(choices) if choices else None
        self.max_length = max_length
        self.required = required

    def validate(self, valor):
        if valor is None:
            if self.required:
                raise ValidationError("Campo requerido")
            return
        if not isinstance(valor, str):
            raise ValidationError(f"Se esperaba texto, se recibió {type(valor).__name__}")
        if self.choices and valor not in self.choices:
            raise ValidationError(f"Valor '{valor}' no está en {self.choices}")
        if self.max_length and len(valor) > self.max_length:
            raise ValidationError(f"Texto excede {self.max_length} caracteres")


class BoolField:
    def __init__(self, required: bool = False):
        self.required = required

    def validate(self, valor):
        if valor is None:
            if self.required:
                raise ValidationError("Campo requerido")
            return
        if not isinstance(valor, int) or isinstance(valor, bool):
            raise ValidationError(f"Se esperaba entero (0/1), se recibió {type(valor).__name__}")


# ── SchemaRegistry ─────────────────────────────────────────────────

class SchemaRegistry:
    """Reglas de validación por tabla y campo."""

    _rules: dict[str, dict[str, FloatField | IntField | StringField | BoolField]] = {
        "insumos": {
            "costo_final": FloatField(min=0),
            "costo_mn": FloatField(min=0),
            "costo_directo": FloatField(min=0),
            "descripcion": StringField(required=True),
            "unidad": StringField(),
            "es_compuesto": BoolField(),
        },
        "estructura_presupuesto": {
            "cantidad": FloatField(min=0),
            "total": FloatField(),
            "tipo": StringField(choices=("capitulo", "concepto")),
            "descripcion": StringField(),
        },
        "apu_matrices": {
            "valor": FloatField(min=0),
            "operador": StringField(choices=("*", "/")),
            "precio": FloatField(min=0),
        },
        "factores_sobrecosto": {
            "pct_indirectos_campo": FloatField(min=0, max=100),
            "pct_indirectos_oficina": FloatField(min=0, max=100),
            "pct_financiamiento": FloatField(min=0, max=100),
            "pct_utilidad": FloatField(min=0, max=100),
            "pct_cargos_adicionales": FloatField(min=0, max=100),
        },
        "familias": {
            "nombre": StringField(required=True),
        },
        "subfamilias": {
            "familia_id": IntField(min=1),
            "nombre": StringField(required=True),
        },
        "proyectos": {
            "nombre": StringField(required=True),
            "iva_porcentaje": FloatField(min=0, max=100),
            "horas_dia": FloatField(min=0),
            "tasa_seguro": FloatField(min=0, max=100),
            "tasa_interes": FloatField(min=0, max=100),
            "tipo_cambio": FloatField(min=0),
            "duracion_obra_dias": IntField(min=0),
            "obra_latitud": FloatField(min=-90, max=90),
            "obra_longitud": FloatField(min=-180, max=180),
        },
        "variables_formula": {
            "proyecto_id": IntField(min=1),
            "nombre": StringField(required=True),
            "expresion": StringField(),
            "descripcion": StringField(),
        },
        "indirectos": {
            "tipo": StringField(choices=("campo", "oficina")),
            "periodo_dias": FloatField(min=0),
            "importe": FloatField(min=0),
            "pct_participacion": FloatField(min=0, max=100),
            "total": FloatField(),
        },
    }

    def validate(self, tabla: str, campos: dict) -> None:
        """Valida cada campo del dict contra las reglas de la tabla."""
        reglas = self._rules.get(tabla, {})
        for campo, valor in campos.items():
            if campo in reglas:
                reglas[campo].validate(valor)
