"""
core.py
=======
Lógica de negocio pura para Open APU Studio.
No sabe nada de presentación (sin HTML, sin PyQt, sin Flask) ni de SQL.

Fase 4 (ver docs/ARQUITECTURA_SERVICIOS.md): este módulo se redujo a solo
las dos funciones que no tienen hogar natural en un repositorio, porque
no leen la base de datos — son transformaciones puras sobre datos ya en
memoria:
    generar_hash(descripcion)  → hash de deduplicación de insumos
    flatten(nodes)             → aplana un árbol ya construido

Todo lo que antes vivía aquí y sí hacía SQL se movió a los repos:
    build_budget_tree() → NodoRepo.arbol()
    get_proyecto()      → ProyectoRepo.obtener()
    get_apu()           → ApuMatricesRepo.con_detalle()
    validar()           → DiagnosticoRepo.resumen_integridad()
    count_nodes(), count_concepts(), total_obra() → sin uso en ningún
        lugar del proyecto; se eliminaron en vez de migrarse (código muerto).
"""

import hashlib


# =============================================================================
# HASH DE DESCRIPCIÓN
# =============================================================================

def generar_hash(descripcion: str) -> str:
    """
    Genera un hash corto y estable a partir de la descripción de un insumo.

    Normalización antes de hashear:
        - strip()
        - uppercase
        - colapso de espacios múltiples a uno solo

    Algoritmo: SHA-256 → primeros 5 bytes → Base36 → 8 caracteres con padding.

    Con 40 bits (2^40 ≈ 1.1 billón de valores) la probabilidad de colisión
    en un catálogo de 10,000 insumos es ~0.0045 %. En caso de colisión, el
    repo lanza IntegrityError que la capa de servicio convierte en mensaje
    claro para el usuario.

    Ejemplos:
        "Acero de refuerzo fy=4200"  →  "2KR8NM4P"
        "ACERO DE REFUERZO FY=4200"  →  "2KR8NM4P"  (mismo hash)
        "  Acero  de refuerzo "      →  "2KR8NM4P"  (mismo hash)
    """
    if not descripcion:
        raise ValueError("La descripción no puede estar vacía para generar un hash.")

    normalizada = " ".join(descripcion.upper().split())
    digest      = hashlib.sha256(normalizada.encode("utf-8")).digest()
    n           = int.from_bytes(digest[:5], "big")

    chars  = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = []
    while n:
        result.append(chars[n % 36])
        n //= 36

    return "".join(reversed(result)).zfill(8)


# =============================================================================
# ÁRBOL: APLANADO
# =============================================================================

def flatten(nodes: list[dict]) -> list[dict]:
    """
    Aplana un árbol (ya construido por NodoRepo.arbol()) en una lista
    ordenada por WBS. Útil para exportar a Excel o para vistas tabulares.
    Cada nodo conserva su campo 'hijos' pero no está anidado.
    """
    resultado = []
    for n in nodes:
        resultado.append(n)
        resultado.extend(flatten(n.get("hijos", [])))
    return resultado
