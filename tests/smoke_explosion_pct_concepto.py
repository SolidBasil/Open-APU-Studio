"""
smoke_explosion_pct_concepto.py
=================================
Prueba de humo de la corrección del Hallazgo 4: la unidad "(%)CONCEPTO"
no estaba en _PCT_TIPO_DESTINO (backend/database/repos/explosion.py), así
que caía al default (tipo_id 2 = Mano de Obra) — mientras que
recalculo.py ya agrupaba '(%)SUBC' y '(%)CONCEPTO' juntos como
subcontrato (tipo_id 32). Un insumo con unidad "(%)CONCEPTO" se
calculaba como subcontrato en el costo real, pero se reportaba como
mano de obra en la explosión de insumos.

Cubre:
    - _parse_unidad_pct("(%)CONCEPTO") ahora resuelve a tipo_id 32,
      igual que "(%)SUBC" (incluye el caso de recalculo.py: mismo bucket)
    - sufijos ya existentes (MO, SUBC, etc.) no cambiaron
    - _postprocesar() calcula pct_base contra el bucket correcto
      (subcontratos, no mano de obra) para un insumo (%)CONCEPTO

Uso:
    python3 tests/smoke_explosion_pct_concepto.py
"""
import os
import sys

import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.repos.explosion import ExplosionRepo, _parse_unidad_pct


def main():
    # ── _parse_unidad_pct: el caso puntual del hallazgo ────────────────
    es_pct, sufijo, tipo_destino = _parse_unidad_pct("(%)CONCEPTO")
    assert es_pct is True
    assert sufijo == "CONCEPTO"
    assert tipo_destino == 32, f"(%)CONCEPTO debía resolver a tipo_id 32 (subcontrato), dio {tipo_destino}"
    print("OK: (%)CONCEPTO resuelve a tipo_id 32 (subcontrato), no 2 (mano de obra)")

    # ── Debe coincidir exactamente con (%)SUBC (mismo bucket) ──────────
    _, _, tipo_subc = _parse_unidad_pct("(%)SUBC")
    assert tipo_destino == tipo_subc, \
        f"(%)CONCEPTO y (%)SUBC deben caer en el mismo bucket: {tipo_destino} vs {tipo_subc}"
    print("OK: (%)CONCEPTO cae en el mismo bucket que (%)SUBC (32) — consistente con recalculo.py")

    # ── Regresión: sufijos ya existentes sin cambios ────────────────────
    casos = {
        "(%)MO": 2, "(%)MA": 1, "(%)MAT": 1,
        "(%)EQ": 8, "(%)AUX": 16, "(%)SUBC": 32, "(%)FL": 64, "(%)TR": 128,
    }
    for unidad, esperado in casos.items():
        _, _, td = _parse_unidad_pct(unidad)
        assert td == esperado, f"{unidad}: esperaba tipo_id {esperado}, dio {td}"
    print(f"OK: los {len(casos)} sufijos preexistentes no cambiaron")

    # ── Unidad no porcentual: sin cambios ───────────────────────────────
    es_pct, sufijo, tipo_destino = _parse_unidad_pct("m2")
    assert es_pct is False and sufijo is None and tipo_destino is None
    print("OK: unidades no porcentuales siguen sin marcarse como % ")

    # ── _postprocesar(): el bucket correcto también aplica end-to-end ──
    repo = ExplosionRepo(sqlite3.connect(":memory:"))  # no toca self._conn/self._db en _postprocesar
    filas = [
        {"tipo_id": 32, "tipo_orden": 1, "total": 1000.0, "unidad": "lote"},   # subcontrato base
        {"tipo_id": 2,  "tipo_orden": 2, "total": 500.0,  "unidad": "jornal"}, # mano de obra base
        {"tipo_id": 16, "tipo_orden": 3, "total": 100.0,  "unidad": "(%)CONCEPTO"},  # el insumo en cuestión (categoría propia distinta del bucket base)
    ]
    resultado, total_global = repo._postprocesar(filas, tipos_set={2, 16, 32})
    fila_pct = [f for f in resultado if f["unidad"] == "(%)CONCEPTO"][0]
    # pct_base = total del insumo % / base del tipo_destino (32=subcontrato=1000, no 2=mano de obra=500)
    assert fila_pct["pct_sufijo"] == "CONCEPTO"
    assert abs(fila_pct["pct_base"] - (100.0 / 1000.0)) < 1e-9, \
        f"pct_base debía calcularse contra el bucket de subcontratos (1000), dio {fila_pct['pct_base']}"
    print(f"OK: _postprocesar() calculó pct_base={fila_pct['pct_base']:.4f} contra el bucket correcto (subcontratos)")

    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 4 PASARON")


if __name__ == "__main__":
    main()
