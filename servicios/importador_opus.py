import os
import re
from pathlib import Path
from collections import defaultdict

from dbfread import DBF

from db.conexion import DatabaseManager
from db.repos.insumos import InsumoRepo
from db.repos.partidas import PartidaRepo
from db.repos.conceptos import ConceptoRepo
from db.repos.apu import ApuComponenteRepo, ApuResumenRepo, AuxiliarRepo


def _prefijo_proyecto(ruta_carpeta):
    nombres = [f.name for f in Path(ruta_carpeta).glob("*EGP.DBF")]
    if not nombres:
        return None
    return nombres[0][:-7]


def _f(val):
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _s(val):
    if val is None:
        return ""
    return str(val).strip()


def importar_opus(ruta_carpeta, db_path):
    prefijo = _prefijo_proyecto(ruta_carpeta)
    if not prefijo:
        raise ValueError(f"No se encontraron archivos OPUS (*EGP.DBF) en {ruta_carpeta}")

    db = DatabaseManager.abrir(db_path)
    insumo_repo = InsumoRepo(db.conn)
    partida_repo = PartidaRepo(db.conn)
    concepto_repo = ConceptoRepo(db.conn)
    apu_comp_repo = ApuComponenteRepo(db.conn)
    apu_res_repo = ApuResumenRepo(db.conn)
    aux_repo = AuxiliarRepo(db.conn)

    # ── 1. Leer EGP: catálogo de insumos ──
    ruta_egp = os.path.join(ruta_carpeta, f"{prefijo}EGP.DBF")
    egp = list(DBF(ruta_egp, encoding="latin-1"))
    egp_map = {}

    for r in egp:
        clave = _s(r["NOMBRE"])
        egp_map[clave] = r
        insumo_repo.insertar({
            "clave": clave,
            "tipo": r["PREFIJO"] or 0,
            "unidad": _s(r.get("UNIDAD", "")),
            "precio": _f(r.get("PRECIO", 0)),
            "descripcion": _s(r.get("DESCRIPCIO", "")),
            "descripcion_corta": _s(r.get("DESCCORTA", "")),
            "es_basico": 1 if _s(r.get("BASICO", "")).upper() == "S" else 0,
            "fecha_precio": _s(r.get("FECHA", "")),
            "costo_materiales": _f(r.get("MATERIALES", 0)),
            "costo_mano_obra": _f(r.get("MANO_DEO", 0)),
            "costo_herramienta": _f(r.get("HERRAMIENT", 0)),
            "costo_equipo": _f(r.get("EQUIPO", 0)),
            "costo_auxiliares": _f(r.get("AUXILIARES", 0)),
        })

    # ── 2. Leer EGF: conceptos + componentes APU ──
    ruta_egf = os.path.join(ruta_carpeta, f"{prefijo}EGF.DBF")
    egf = list(DBF(ruta_egf, encoding="latin-1"))

    egf_pref16 = [r for r in egf if r["PREF"] == 16]
    egf_pref32 = [r for r in egf if r["PREF"] == 32]

    partida_repo.limpiar()
    concepto_repo.limpiar()
    apu_comp_repo.limpiar()

    # Ordenar conceptos por CLAVENUM
    egf_pref16.sort(key=lambda r: (r["CLAVENUM"] or 0))

    # Agrupar por capítulo (CLAVENUM // 100)
    capitulos = defaultdict(list)
    for r in egf_pref16:
        cap = int(r["CLAVENUM"] // 100) if r["CLAVENUM"] else 0
        capitulos[cap].append(r)

    orden_partida = 0
    for cap in sorted(capitulos):
        items = capitulos[cap]
        orden_partida += 1

        if cap == 0:
            nom_partida = "Generales"
        else:
            nom_partida = f"Capítulo {cap}"

        partida_id = partida_repo.insertar({
            "clave": str(cap),
            "nombre": nom_partida,
            "orden": orden_partida,
            "nivel": 0,
        })

        for i, r in enumerate(items):
            clave = _s(r["NOMBRE"])
            egp_rec = egp_map.get(clave, {})
            desc = _s(egp_rec.get("DESCCORTA", "")) if egp_rec else ""
            if not desc:
                desc = _s(egp_rec.get("DESCRIPCIO", "")) if egp_rec else ""
            unid = _s(egp_rec.get("UNIDAD", "")) if egp_rec else ""
            cant = _f(r.get("NOELE", 1))
            pu = _f(r.get("COSTO", 0))
            imp = _f(r.get("IMPORTE", 0))

            concepto_repo.insertar({
                "partida_id": partida_id,
                "clave": clave,
                "orden": i + 1,
                "cantidad": cant,
                "precio_unitario": pu,
                "importe": imp if imp else cant * pu,
                "unidad": unid,
                "descripcion": desc,
            })

    # ── 3. Componentes APU (EGF PREF=32) ──
    for r in egf_pref32:
        apu_comp_repo.insertar({
            "concepto_clave": _s(r.get("NOMBRE", "")),
            "insumo_clave": _s(r.get("COMPONENTE", "")),
            "tipo_insumo": r.get("PREFCOMP", 0) or 0,
            "rendimiento": _f(r.get("RENDTO", 0)),
            "num_elementos": _f(r.get("NOELE", 1)),
            "cantidad_total": _f(r.get("CANTIDAD", 0)),
            "precio_unitario": _f(r.get("COSTO", 0)),
            "importe": _f(r.get("TOTALMN", 0)),
            "formula": _s(r.get("EXPRESION", "")),
        })

    # ── 4. EGN: APU resumen ──
    ruta_egn = os.path.join(ruta_carpeta, f"{prefijo}EGN.DBF")
    egn = list(DBF(ruta_egn, encoding="latin-1"))
    apu_res_repo.limpiar()

    for r in egn:
        apu_res_repo.insertar({
            "concepto_clave": _s(r["NOMBRE"]),
            "total_materiales": _f(r.get("MM", 0)),
            "total_mano_obra": _f(r.get("OO", 0)),
            "total_herramienta": _f(r.get("HH", 0)),
            "total_equipo": _f(r.get("EE", 0)),
            "total_auxiliares": _f(r.get("AA", 0)),
            "total_subcontratos": _f(r.get("SUBCONT", 0)),
            "indirectos": _f(r.get("INDIRECTOS", 0)),
            "financiamiento": _f(r.get("FINANCIA", 0)),
            "utilidad": _f(r.get("UTILIDAD", 0)),
            "precio_venta": _f(r.get("PP", 0)),
        })

    # ── 5. EGX: Auxiliares ──
    ruta_egx = os.path.join(ruta_carpeta, f"{prefijo}EGX.DBF")
    egx = list(DBF(ruta_egx, encoding="latin-1"))
    aux_repo.limpiar()

    for r in egx:
        aux_repo.insertar({
            "insumo_clave": _s(r["NOMBRE"]),
            "tipo": r.get("PREFIJO", 0) or 0,
            "cantidad": _f(r.get("CANTIDAD", 0)),
            "precio": _f(r.get("PRECIO", 0)),
            "importe": _f(r.get("MONTO", 0)),
        })

    # ── 6. EGZ: Configuración del proyecto ──
    ruta_egz = os.path.join(ruta_carpeta, f"{prefijo}EGZ.DBF")
    if os.path.exists(ruta_egz):
        egz = list(DBF(ruta_egz, encoding="latin-1"))
        if egz:
            r = egz[0]
            db.conn.execute(
                "INSERT OR REPLACE INTO proyecto_config (proyecto_id, horas_dia, tasa_seguro, tasa_interes) VALUES (1, ?, ?, ?)",
                [_f(r.get("HORASDIA", 8)), _f(r.get("SEGURO", 0)), _f(r.get("TASA_INTER", 0))]
            )
            db.conn.commit()

    # ── 7. EGI: Indirectos ──
    ruta_egi = os.path.join(ruta_carpeta, f"{prefijo}EGI.DBF")
    if os.path.exists(ruta_egi):
        egi = list(DBF(ruta_egi, encoding="latin-1"))
        db.conn.execute("DELETE FROM indirectos WHERE proyecto_id = 1")
        for r in egi:
            db.conn.execute(
                "INSERT INTO indirectos (proyecto_id, renglon, variable, descripcion, formula, se_suma, se_imprime) VALUES (1, ?, ?, ?, ?, ?, ?)",
                [_f(r.get("RENGLON", 0)), _s(r.get("VAR", "")), _s(r.get("DESC1", "")),
                 _s(r.get("FORMULA", "")), 1 if r.get("SE_SUMA") else 0, 1 if r.get("SE_IMPR") else 0]
            )
        db.conn.commit()

    # ── 8. Metadatos del proyecto ──
    db.conn.execute(
        "INSERT OR REPLACE INTO proyectos (id, nombre, clave_opus) VALUES (1, ?, ?)",
        [f"Proyecto {prefijo}", prefijo]
    )
    db.conn.commit()

    db.close()

    return {
        "insumos": len(egp),
        "conceptos": len(egf_pref16),
        "apu_componentes": len(egf_pref32),
        "apu_resumen": len(egn),
        "auxiliares": len(egx),
        "capitulos": len(capitulos),
    }
