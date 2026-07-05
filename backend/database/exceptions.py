"""
exceptions.py
=============
Excepciones propias de la capa de datos de Open APU Studio.

Antes de esto, ValidationError vivía suelta en schema_registry.py (sin
heredar de nada en particular) y DataServiceError/RepositoryError/
ConflictError vivían en services/data_service.py — dos jerarquías que no
se tocaban entre sí pese a estar documentadas aquí como una sola desde el
principio (ver docs/ARQUITECTURA_SERVICIOS.md §6.3). Este módulo es ahora
la única fuente de verdad; schema_registry.py y data_service.py importan
de aquí en vez de definir sus propias clases.

Jerarquía:
    DataServiceError            — base, para capturar "cualquier error de escritura"
    ├── ValidationError         — un campo no pasó las reglas de SchemaRegistry
    ├── RepositoryError         — falló el repo (SQL, integridad, etc.)
    └── ConflictError           — conflicto de concurrencia (registro
                                   modificado por otro proceso)

Uso típico desde la UI:
    try:
        self._api.insumo_actualizar_precio(insumo_id, precio)
    except ValidationError as e:
        QMessageBox.warning(self, "Dato inválido", str(e))
    except DataServiceError as e:
        QMessageBox.critical(self, "Error al guardar", str(e))
"""


class DataServiceError(Exception):
    """Base para errores del servicio de datos."""


class ValidationError(DataServiceError):
    """Validación de SchemaRegistry fallida."""


class RepositoryError(DataServiceError):
    """Error en operación de repositorio (SQL, integridad, etc.)."""


class ConflictError(DataServiceError):
    """Conflicto de concurrencia (registro modificado por otro proceso)."""
