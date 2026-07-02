"""
repos/
======
Repositorios de acceso a datos — Open APU Studio.

Cada archivo agrupa repositorios por dominio funcional:
    base.py        — RepoBase (clase raíz)
    proyecto.py    — ProyectoRepo, SobrecostosRepo
    presupuesto.py — NodoRepo (capítulos y conceptos del árbol)
    insumos.py     — InsumoRepo
    apu.py         — ApuMatricesRepo, ApuResumenTotalesRepo
    recalculo.py   — RecalculoRepo
    catalogos.py   — FamiliaRepo, SubfamiliaRepo, NotaRepo
    explosion.py   — ExplosionRepo

Todos los imports externos siguen usando:
    from backend.database.repos import InsumoRepo
sin necesitar saber en qué archivo interno vive cada clase.
"""

from .base        import RepoBase
from .proyecto    import ProyectoRepo, SobrecostosRepo
from .presupuesto import NodoRepo, ESTADO_COLOR, ESTADO_NOMBRE
from .insumos     import InsumoRepo
from .apu         import ApuMatricesRepo, ApuResumenTotalesRepo
from .recalculo   import RecalculoRepo
from .catalogos   import FamiliaRepo, SubfamiliaRepo, NotaRepo
from .explosion   import ExplosionRepo

__all__ = [
    "RepoBase",
    "ProyectoRepo", "SobrecostosRepo",
    "NodoRepo", "ESTADO_COLOR", "ESTADO_NOMBRE",
    "InsumoRepo",
    "ApuMatricesRepo", "ApuResumenTotalesRepo",
    "RecalculoRepo",
    "FamiliaRepo", "SubfamiliaRepo", "NotaRepo",
    "ExplosionRepo",
]
