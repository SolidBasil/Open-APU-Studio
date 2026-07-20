"""
exportar.py
===========
Exportación de Open APU Studio → formato DBF de OPUS 2010.

Clase principal: Exportador
  .exportar(carpeta_destino, db_path, proyecto_id, ruta_opus=None)
  .resumen(db_path, proyecto_id) → dict
"""

import dbf
import sqlite3
import json
from datetime import date
from pathlib import Path

from backend.database.repos import (
    ProyectoRepo, NodoRepo, InsumoRepo,
    ApuMatricesRepo, RecalculoRepo,
)
from backend.exportar.exportar_plantillas import (
    TIPOSINS_ROWS, CONFIG_FIJOS, C_FIJOS, FSR_9_ROWS, CONFIG_INI_TEMPLATE,
)
from backend.exportar import cdx as _cdx_mod

_SCHEMAS_PATH = Path(__file__).parent / 'schemas_opus.json'
_CP = 'cp1252'
_FOR = '.NOT. DELETED()'

# ---------------------------------------------------------------------------
# CDX tags por tabla — expresiones FoxPro exactas extraídas del original
# ---------------------------------------------------------------------------
_CDX_TAGS = {
    '': [   # [Obra].DBF (catálogo)
        {'key_expr': 'ID',              'key_len': 10},
        {'key_expr': 'SISTEMA',         'key_len': 80},
        {'key_expr': 'SISTEMA+NOMBRE',  'key_len': 100},
    ],
    '0': [
        {'key_expr': 'STR(ID,10,0)+STR(SIGUE,10,0)',  'key_len': 20},
        {'key_expr': 'STR(SIGUE,10,0)+STR(ID,10,0)',  'key_len': 20},
        {'key_expr': 'STR(DIFEIDS,10,0)',              'key_len': 10},
    ],
    '1': [
        {'key_expr': 'STR(PRE_IDUNI,10)',                  'key_len': 10},
        {'key_expr': 'STR(PRE_IDPAD,10) + STR(PRE_ID,10)', 'key_len': 20},
        {'key_expr': 'STR(PRE_ID,10)',                     'key_len': 10},
        {'key_expr': 'PRE_VIS+STR(PRE_ID,10)',             'key_len': 11},
        {'key_expr': 'STR(PRE_IDAUX,10)',                  'key_len': 10},
        {'key_expr': 'PRE_COM',                            'key_len': 20},
    ],
    '3': [
        {'key_expr': 'STR(ID, 10, 0)',               'key_len': 10},
        {'key_expr': 'STR(IDUNICO, 10, 0)',           'key_len': 10},
        {'key_expr': 'VISTO + STR(ID, 10, 0)',        'key_len': 11},
        {'key_expr': 'NIVEL + STR(ID, 10, 0)',        'key_len': 11},
        {'key_expr': 'STR(PRE_IDUN,10,0)',            'key_len': 10},
        {'key_expr': 'NOMBRE',                        'key_len': 20},
        {'key_expr': 'STR(POSX,7,0)+STR(POSY,7,0)',  'key_len': 14},
        {'key_expr': 'STR(FRENTE,7,0)+STR(ID, 10, 0)', 'key_len': 17},
        {'key_expr': 'TIPOREN+STR(ID, 10, 0)',        'key_len': 11},
        {'key_expr': 'WBS',                           'key_len': 20},
    ],
    '5': [
        {'key_expr': 'NOMBRE+COMPONE',                        'key_len': 80},
        {'key_expr': 'COMPONE',                               'key_len': 40},
        {'key_expr': 'UNIPOR',                                'key_len':  1},
        {'key_expr': 'NOMBRE + STR(PREFCOMP,5,0) + COMPONE', 'key_len': 85},
    ],
    '8': [
        {'key_expr': 'STR(FSR_TIP,1)+FSR_CLV', 'key_len': 21},
    ],
    '9': [
        {'key_expr': 'FFSR_REN', 'key_len': 8},
        {'key_expr': 'FFSR_CLV', 'key_len': 6},
    ],
    'A': [
        {'key_expr': 'STR(IDUNI,10,0)',   'key_len': 10},
        {'key_expr': 'FAMILIA + NOMBRE', 'key_len': 40},
        {'key_expr': 'NOMBRE',           'key_len': 20},
        {'key_expr': 'IDUNI',            'key_len':  8},
    ],
    'D': [
        {'key_expr': 'WBS', 'key_len': 25},
    ],
    'F': [
        {'key_expr': 'NOMBRE+STR(CLAVENUM,11,0)',                    'key_len': 51},
        {'key_expr': 'NOMBRE+STR(PREFCOMP,5,0)+STR(CLAVENUM,11,0)', 'key_len': 56},
        {'key_expr': 'NOMBRE + COMPONENTE + STR(CLAVENUM,11,0)',     'key_len': 91},
        {'key_expr': 'COMPONENTE+NOMBRE',                            'key_len': 80},
    ],
    'H': [
        {'key_expr': 'NOMBRE + DTOS(NFECHA)',    'key_len': 28},
        {'key_expr': 'DTOS(NFECHA) + NOMBRE',   'key_len': 28},
        {'key_expr': 'STR(NNUMESC,2,0) + NOMBRE', 'key_len': 22},
        {'key_expr': 'NOMBRE + STR(NNUMESC,2,0)', 'key_len': 22},
    ],
    'I': [
        {'key_expr': 'STR(RENGLON,3,0)',                   'key_len':  3},
        {'key_expr': 'VAR',                                'key_len': 15},
        {'key_expr': 'IIF(SE_SUMA,"Y","N") + STR(RENGLON,3,0)', 'key_len': 4},
    ],
    'J': [
        {'key_expr': 'NOMBRE', 'key_len': 20},
    ],
    'N': [
        {'key_expr': 'NOMBRE', 'key_len': 20},
    ],
    'P': [
        {'key_expr': 'NOMBRE',                           'key_len': 40},
        {'key_expr': 'STR(PREFIJO,5,0)+NOMBRE',          'key_len': 45},
        {'key_expr': 'MARCA1',                           'key_len':  1},
        {'key_expr': 'MARCA2',                           'key_len':  1},
        {'key_expr': 'MARCA3',                           'key_len':  1},
        {'key_expr': 'FSR_MINIMO',                       'key_len':  1},
        {'key_expr': 'MARCA4',                           'key_len':  1},
        {'key_expr': 'CLAVEUSUAR',                       'key_len': 30},
        {'key_expr': 'STR(PREFIJO,5,0)+CLAVEUSUAR',      'key_len': 35},
        {'key_expr': 'MARCA5 +STR(PREFIJO,5,0) + NOMBRE','key_len': 46},
        {'key_expr': 'UPPER(DESCCORTA)',                 'key_len': 30},
        {'key_expr': 'CLV_BDOPUS',                       'key_len': 15},
        {'key_expr': 'CLV_PROVEE',                       'key_len': 25},
    ],
    'R': [
        {'key_expr': 'STR(ID, 10, 0)',               'key_len': 10},
        {'key_expr': 'STR(IDUNICO, 10, 0)',           'key_len': 10},
        {'key_expr': 'VISTO + STR(ID, 10, 0)',        'key_len': 11},
        {'key_expr': 'NIVEL + STR(ID, 10, 0)',        'key_len': 11},
        {'key_expr': 'STR(IND_PREF,5,0) + STR(ID,10,0)', 'key_len': 15},
    ],
    'W': [
        {'key_expr': 'RES_NUM', 'key_len': 4},
    ],
    'X': [
        {'key_expr': 'ESTOTAL+NOMBRE',                          'key_len': 41},
        {'key_expr': 'STR(PREFIJO,5,0)+ESTOTAL+STR(MONTO,20,6)','key_len': 26},
        {'key_expr': 'STR(9-VAL(ESTOTAL),1)+STR(MONTO,20,6)',   'key_len': 21},
        {'key_expr': 'ESTOTAL+CLAVEUSUAR',                      'key_len': 31},
        {'key_expr': 'UNIPOR',                                  'key_len': 10},
        {'key_expr': 'STR(PREFIJO,5,0)+ESTOTAL+NOMBRE',         'key_len': 46},
        {'key_expr': 'EXP_GRUPO+ESTOTAL+NOMBRE',               'key_len': 46},
        {'key_expr': 'AJUSTA+STR(MONTO,20,6)',                  'key_len': 21},
    ],
    'FRENTES': [
        {'key_expr': 'no', 'key_len': 3},
    ],
    'TIPOSINS': [
        {'key_expr': 'STR(prefijo,5,0)', 'key_len': 5},
    ],
}


class Exportador:
    """Exporta un proyecto SQLite al formato de carpeta de obra OPUS 2010."""

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @staticmethod
    def resumen(db_path, proyecto_id: int) -> dict:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        proy    = ProyectoRepo(conn).buscar(proyecto_id)
        nodos   = NodoRepo(conn).todos(proyecto_id)
        insumos = InsumoRepo(conn).todos(proyecto_id)
        hojas      = [n for n in nodos if n['tipo'] == 'concepto']
        capitulos  = [n for n in nodos if n['tipo'] == 'capitulo']
        basicos    = [i for i in insumos if not i.get('es_compuesto')]
        compuestos = [i for i in insumos if i.get('es_compuesto')]
        conn.close()
        return {
            'nombre':     proy['nombre'] if proy else '(sin proyecto)',
            'clave_opus': proy.get('clave_opus', '') if proy else '',
            'total_obra': proy['total_obra'] if proy else 0,
            'nodos':      len(nodos),
            'hojas':      len(hojas),
            'capitulos':  len(capitulos),
            'insumos':    len(insumos),
            'basicos':    len(basicos),
            'compuestos': len(compuestos),
        }

    @staticmethod
    def exportar(carpeta_destino, db_path, proyecto_id: int,
                 ruta_opus=None, progress_cb=None) -> dict:
        exp = Exportador(db_path, proyecto_id, carpeta_destino, ruta_opus, progress_cb)
        return exp._run()

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def __init__(self, db_path, proyecto_id, carpeta_destino, ruta_opus, progress_cb):
        self._db_path   = Path(db_path)
        self._pid       = proyecto_id
        self._destino   = Path(carpeta_destino)
        self._ruta_opus = Path(ruta_opus) if ruta_opus else None
        self._cb        = progress_cb
        self._log       = []
        self._errores   = []

        with open(_SCHEMAS_PATH, encoding='utf-8') as f:
            self._schemas = json.load(f)

        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row

        self._proy_repo = ProyectoRepo(self._conn)
        self._nodo_repo = NodoRepo(self._conn)
        self._ins_repo  = InsumoRepo(self._conn)
        self._apu_repo  = ApuMatricesRepo(self._conn)
        self._rc_repo   = RecalculoRepo(self._conn)

        self._proy  = self._proy_repo.buscar(proyecto_id)
        # ponytail: config se fusionó en proyectos — ya no hay tabla separada
        self._clave = (self._proy.get('clave_opus') or 'OBRA').upper()

    def _run(self):
        self._destino.mkdir(parents=True, exist_ok=True)
        pasos = [
            ('Tablas estáticas',       self._fase0_estaticas),
            ('Config + C.DBF',         self._fase1_config),
            ('Insumos → P.DBF',        self._fase2_insumos),
            ('Presupuesto → 1+A.DBF',  self._fase3_presupuesto),
            ('APU → F+N.DBF',          self._fase4_apu),
            ('Derivados → 5+X.DBF',    self._fase5_derivados),
            ('FSR → 8+9+Z.DBF',        self._fase7_fsr),
            ('Tablas vacías + aux',    self._fase8_vacias),
            ('OBRA.DBF',               self._fase9_obra_dbf),
        ]
        for i, (nombre, fn) in enumerate(pasos):
            self._progress(i, len(pasos), nombre)
            try:
                fn()
            except Exception as e:
                import traceback
                self._errores.append(f'[{nombre}] {e}\n{traceback.format_exc()}')
        self._progress(len(pasos), len(pasos), 'Completado')
        self._conn.close()
        return {'log': self._log, 'errores': self._errores}

    def _progress(self, step, total, msg):
        if self._cb:
            self._cb(step, total, msg)

    # ── Helpers DBF ──────────────────────────────────────────────────

    def _estructura(self, tabla_key: str) -> str:
        campos = self._schemas[tabla_key]
        partes = []
        for c in campos:
            t, l, d, n = c['type'], c['length'], c['decimal'], c['name']
            if t == 'M':
                partes.append(f'{n} M')
            elif t == 'L':
                partes.append(f'{n} L')
            elif t == 'D':
                partes.append(f'{n} D')
            elif t == 'N' and d > 0:
                partes.append(f'{n} N({l},{d})')
            elif t == 'N':
                partes.append(f'{n} N({l},0)')
            else:
                partes.append(f'{n} C({max(l, 1)})')
        return '; '.join(partes)

    def _crear_tabla(self, ruta: Path, schema_key: str,
                     registros: list, cdx_sufijo: str | None = None) -> int:
        """Crea DBF + CDX. cdx_sufijo=None → sin CDX; '' → CDX con clave ''."""
        estructura = self._estructura(schema_key)
        t = dbf.Table(str(ruta), estructura, codepage=_CP)
        t.open(mode=dbf.READ_WRITE)
        campos_dbf = set(t.field_names)
        n = 0
        for rec in registros:
            fila = {}
            for k, v in rec.items():
                ku = k.upper()
                if ku not in campos_dbf:
                    continue
                fila[ku] = self._limpiar(v, ku, t)
            try:
                t.append(fila)
                n += 1
            except Exception as e:
                self._errores.append(f'  append {ruta.name}: {e}')
        t.close()
        self._parchear_cabecera(ruta)

        # CDX
        if cdx_sufijo is not None:
            self._crear_cdx(ruta, cdx_sufijo, registros)

        self._log.append(f'{ruta.name}: {n} reg')
        return n

    def _limpiar(self, v, campo, tabla):
        if v is None:
            return v
        if isinstance(v, str):
            try:
                fi = tabla.field_info(campo.upper())
                return v[:fi.length]
            except Exception:
                return v[:254]
        return v

    def _parchear_cabecera(self, ruta: Path):
        """Ajusta cabecera DBF para compatibilidad OPUS: versión 0x03, lang=0x00."""
        with open(ruta, 'r+b') as f:
            hdr = bytearray(f.read(32))
            if len(hdr) < 32:
                return
            hdr[0]  = 0x03   # dBASE III+
            hdr[29] = 0x00   # language driver ID neutral
            f.seek(0)
            f.write(bytes(hdr))
        # FPT block size 512 si existe
        fpt = ruta.with_suffix('.FPT')
        if not fpt.exists():
            fpt = ruta.with_suffix('.fpt')
        if fpt.exists():
            with open(fpt, 'r+b') as f:
                fpt_hdr = bytearray(f.read(8))
                if len(fpt_hdr) >= 8:
                    import struct
                    struct.pack_into('>H', fpt_hdr, 6, 512)
                    f.seek(0)
                    f.write(bytes(fpt_hdr))

    def _crear_cdx(self, ruta: Path, sufijo: str, registros: list):
        """Genera el .CDX usando cdx.make_cdx con los tags definidos en _CDX_TAGS."""
        tags = _CDX_TAGS.get(sufijo)
        if not tags:
            return
        cdx_path = ruta.with_suffix('.CDX')
        try:
            t = dbf.Table(str(ruta), codepage=_CP)
            t.open(mode=dbf.READ_ONLY)
            records = list(t)
            _cdx_mod.make_cdx(ruta, cdx_path, tags, records, t)
            t.close()
        except Exception as e:
            self._errores.append(f'  CDX {ruta.name}: {e}')

    def _ruta(self, sufijo: str = '') -> Path:
        return self._destino / f'{self._clave}{sufijo}.DBF'

    def _crear_tabla_vacia(self, schema_key: str, sufijo: str):
        ruta = self._ruta(sufijo)
        self._crear_tabla(ruta, schema_key, [], cdx_sufijo=sufijo if sufijo in _CDX_TAGS else None)

    # ── FASE 0 ───────────────────────────────────────────────────────

    def _fase0_estaticas(self):
        # TIPOSINS
        ruta_ti = self._destino / 'TIPOSINS.DBF'
        self._crear_tabla(ruta_ti, 'TIPOSINS', TIPOSINS_ROWS, cdx_sufijo='TIPOSINS')

        # FRENTES (vacío)
        ruta_fr = self._destino / 'FRENTES.DBF'
        self._crear_tabla(ruta_fr, 'FRENTES', [], cdx_sufijo='FRENTES')

        # CONFIG.DBF
        proy = self._proy
        hoy  = date.today()
        fecha_cfg = hoy

        cfg_rec = {**CONFIG_FIJOS}
        cfg_rec.update({
            'IMPUESTO':   float(proy.get('iva_porcentaje') or 16.0),
            'MONEDA':     (proy.get('moneda_nombre') or 'PESOS')[:20],
            'SIMBOLO':    (proy.get('moneda_simbolo') or '$')[:4],
            'LEYIMPUEST': (proy.get('iva_nombre') or 'IVA')[:40],
            'FECHA':      fecha_cfg,
            'DIRCATGEN':  str(self._destino)[:100],
            'CLAVEOBRA':  self._clave[:20],
            'UFECHAMOD':  hoy,
        })
        # CONFIG no tiene CDX
        self._crear_tabla(self._destino / 'CONFIG.DBF', 'CONFIG', [cfg_rec])

    # ── FASE 1 ───────────────────────────────────────────────────────

    def _fase1_config(self):
        # CONFIG.INI
        (self._destino / 'CONFIG.INI').write_text(CONFIG_INI_TEMPLATE, encoding='cp1252')
        self._log.append('CONFIG.INI: ok')

        # .ODB vacío
        (self._destino / f'{self._clave}.ODB').touch()

        # [Obra].DBF — catálogo (vacío)
        self._crear_tabla(self._ruta(''), '1', [], cdx_sufijo='')

        # [Obra]C.DBF — no tiene CDX
        proy = self._proy

        def _fecha(campo):
            v = proy.get(campo)
            if not v:
                return None
            try:
                return date.fromisoformat(str(v)[:10])
            except Exception:
                return None

        total = float(proy.get('total_obra') or 0)
        c_rec = {**C_FIJOS}
        c_rec.update({
            'OBRDES':    (proy.get('descripcion') or '')[:200],
            'OBRUBI':    (proy.get('obra_domicilio') or '')[:100],
            'OBRFEC':    _fecha('licitacion_fecha'),
            'OBRCOS':    total,
            'OBRMOGRA':  0.0,
            'OBRPRE':    total,
            'OBRPIND':   0.0,
            'OBRPUTI':   0.0,
            'OBRFINI':   _fecha('fecha_inicio'),
            'OBRFTER':   _fecha('fecha_termino'),
            'LEYMONNAC': (proy.get('moneda_nombre') or 'PESOS')[:20],
            'SIMMONNAC': (proy.get('moneda_simbolo') or '$')[:4],
        })
        self._crear_tabla(self._ruta('C'), 'C', [c_rec])

    # ── FASE 2: Insumos → P.DBF ──────────────────────────────────────

    def _fase2_insumos(self):
        insumos = self._ins_repo.todos(self._pid)

        # ponytail: resúmenes calculados al vuelo en memoria
        resumenes = self._rc_repo.calcular_todos_resumenes(self._pid)
        res_map = {abs(mid): r for mid, r in resumenes.items() if mid < 0}

        registros = []
        for ins in insumos:
            costo  = float(ins.get('costo_final') or 0)
            unidad = (ins.get('unidad') or '').strip()
            clave  = (ins.get('clave_opus') or '').strip()

            # OPUS valida: longitud clave 1-20, unidad requerida para no-categoría
            if not clave or len(clave) > 20:
                continue
            if not unidad and costo != 0:
                continue  # omitir insumos sin unidad que no son categorías

            # PREFIJO según tipo y naturaleza
            if costo == 0 and not unidad:
                prefijo = 512   # categoría agrupadora
            else:
                prefijo = int(ins.get('tipo_id') or 1)

            resumen  = res_map.get(ins['id'])
            mat  = float(resumen.get('materiales', 0)) if resumen else 0.0
            mo   = float(resumen.get('mano_obra', 0)) if resumen else 0.0
            herr = float(resumen.get('herramienta', 0)) if resumen else 0.0
            equ  = float(resumen.get('equipo', 0)) if resumen else 0.0
            aux  = float(resumen.get('auxiliares', 0)) if resumen else 0.0

            fecha_precio = None
            fp = ins.get('fecha_precio')
            if fp:
                try:
                    fecha_precio = date.fromisoformat(str(fp)[:10])
                except Exception:
                    pass

            costo_mn = float(ins.get('costo_mn') or costo)
            costo_me = float(ins.get('costo_me') or 0)

            registros.append({
                'PREFIJO':    prefijo,
                'NOMBRE':     clave[:20],
                'UNIDAD':     unidad[:8],
                'BASICO':     '',
                'FSR_MINIMO': '',
                'PRECIO':     costo,
                'FSR':        1.0,
                'FECHA':      fecha_precio,
                'MATERIALES': mat,
                'MANO_DEO':   mo,
                'HERRAMIENT': herr,
                'EQUIPO':     equ,
                'MARCA1': '', 'MARCA2': '', 'MARCA3': '',
                'MARCA4': '', 'MARCA5': '', 'MARCA6': '',
                'DESCRIPCIO': (ins.get('descripcion') or ''),
                'COMENTARIO': '',
                'CLAVEUSUAR': (ins.get('clave_usuario') or '')[:30],
                'ARCHIFOTO':  '',
                'ACUMULADOR': 0.0,
                'SAL_BASE':   mo if ins.get('tipo_id') == 2 else 0.0,
                'PUNIT':      costo,
                'AUXILIARES': aux,
                'DESCCORTA':  (ins.get('descripcion_corta') or '')[:30],
                'TOTALMN':    costo_mn,
                'TOTALME':    costo_me,
                'CATFSR':     'FSROTR',
                'ELE_GRUPO':  (ins.get('familia_nombre') or '')[:20],
                'ELE_REFBAS': '',
                'ELE_RELBAS': 0.0,
                'PUNITMN':    costo_mn,
                'PUNITME':    costo_me,
                'SAL_GRA':    0.0,
                'PBASEMN':    costo_mn,
                'A': 0.0, 'B': 0.0, 'C': 0.0,
                'PBASEME':    costo_me,
                'D': 0.0, 'E': 0.0, 'F': 0.0,
                'PESO':       float(ins.get('peso_kg') or 0),
                'CTD_MOB':    0.0,
                'WBS':        '',
                'WBS1':       '',
                'CLV_BDOPUS': '',
                'CLV_PROVEE': '',
                'PERSE':      False,
                'PORGEN':     False,
            })

        self._crear_tabla(self._ruta('P'), 'P', registros, cdx_sufijo='P')

    # ── FASE 3: Presupuesto → 1.DBF + A.DBF ─────────────────────────

    def _fase3_presupuesto(self):
        nodos = self._nodo_repo.todos(self._pid)

        # Nodos con APU (para PRE_VIS='N' en hojas sin APU)
        cur = self._conn.cursor()
        nodos_con_apu = {
            row[0] for row in cur.execute(
                'SELECT DISTINCT matriz_id FROM apu_matrices WHERE matriz_id > 0'
            )
        }

        id_a_iduni: dict[int, int] = {}
        registros_1 = []

        # Raíz ficticia
        total_obra = float(self._proy.get('total_obra') or 0)
        registros_1.append({
            'PRE_ID': 0, 'PRE_IDUNI': 0, 'PRE_TIP': 1, 'PRE_NIVEL': 0,
            'PRE_IDPAD': -1, 'PRE_VIS': 'S', 'PRE_SIGNO': '+',
            'PRE_IDAUX': 0, 'PRE_ESCOL': False, 'PRE_COM': '',
            'PRE_EXP': '', 'PRE_VOL': 1.0, 'PRE_PRE': total_obra,
            'PRE_PMN': total_obra, 'PRE_PME': 0.0, 'PRE_VPE': 0.0,
            'PRE_IMP': 0.0, 'PRE_WBS': '', 'PRE_CAR1': '',
            'PRE_CAR2': '', 'PRE_CAR3': '', 'IDPROP': 0,
            'PRE_PAQ': False, 'PRE_ACUPRO': 0.0, 'MEMOCAD': '', 'REPROG': 0,
        })

        nodos_ordenados = sorted(nodos, key=lambda n: (n.get('wbs') or ''))
        padre_ids = {n['padre_id'] for n in nodos if n.get('padre_id') is not None}

        pre_id_counter = 10
        iduni_counter  = 1

        for nodo in nodos_ordenados:
            nid       = nodo['id']
            pre_id    = pre_id_counter
            pre_iduni = iduni_counter
            id_a_iduni[nid] = pre_iduni

            padre_sqlite = nodo.get('padre_id')
            pre_idpad = 0 if padre_sqlite is None else id_a_iduni.get(padre_sqlite, 0)

            es_capitulo = nodo['tipo'] == 'capitulo'
            tiene_hijos = nid in padre_ids

            # PRE_VIS: 'S' si tiene hijos (capítulo) o si es concepto con APU
            if es_capitulo:
                vis = 'S' if tiene_hijos else 'N'
            else:
                vis = 'S' if nid in nodos_con_apu else 'N'

            # PRE_PRE: para capitulos = subtotal; para conceptos = precio_unitario
            # importe = cantidad * precio_unitario (campo GENERATED en SQLite)
            pu       = float(nodo.get('precio_unitario') or 0)
            cantidad = float(nodo.get('cantidad') or 0)
            subtotal = float(nodo.get('total') or 0)

            pre_pre = subtotal if es_capitulo else pu
            pre_vol = 1.0     if es_capitulo else cantidad
            pre_imp = 0.0     if es_capitulo else (cantidad * pu)

            registros_1.append({
                'PRE_ID':    pre_id,
                'PRE_IDUNI': pre_iduni,
                'PRE_TIP':   1 if es_capitulo else 0,
                'PRE_NIVEL': int(nodo.get('nivel') or 1),
                'PRE_IDPAD': pre_idpad,
                'PRE_VIS':   vis,
                'PRE_SIGNO': '+',
                'PRE_IDAUX': 0,
                'PRE_ESCOL': False,
                'PRE_COM':   (nodo.get('clave_opus') or '')[:20],
                'PRE_EXP':   (nodo.get('descripcion') or ''),
                'PRE_VOL':   pre_vol,
                'PRE_PRE':   pre_pre,
                'PRE_PMN':   pre_pre,
                'PRE_PME':   0.0,
                'PRE_VPE':   0.0,
                'PRE_IMP':   pre_imp,
                'PRE_WBS':   (nodo.get('wbs') or '')[:20],
                'PRE_CAR1':  '', 'PRE_CAR2': '', 'PRE_CAR3': '',
                'IDPROP':    0,
                'PRE_PAQ':   False,
                'PRE_ACUPRO':0.0,
                'MEMOCAD':   '',
                'REPROG':    0,
            })
            pre_id_counter  += 10
            iduni_counter   += 1

        self._crear_tabla(self._ruta('1'), '1', registros_1, cdx_sufijo='1')

        # A.DBF — precios unitarios por concepto
        registros_a = [{
            'IDUNI': 0, 'FAMILIA': '', 'COSTODIR': total_obra,
            'PRECIO': total_obra, 'UNIDAD': '', 'NOMBRE': '',
            'DESC': '', 'PRE_WBS': '', 'PRECIOMN': total_obra,
            'PRECIOME': 0.0, 'DESCCORTA': '',
        }]
        for nodo in nodos_ordenados:
            if nodo['tipo'] != 'concepto':
                continue
            pu = float(nodo.get('precio_unitario') or 0)
            cd = float(nodo.get('total') or (float(nodo.get('cantidad') or 0) * pu))
            registros_a.append({
                'IDUNI':    id_a_iduni.get(nodo['id'], 0),
                'FAMILIA':  '',
                'COSTODIR': cd,
                'PRECIO':   pu,
                'UNIDAD':   (nodo.get('unidad') or '')[:8],
                'NOMBRE':   (nodo.get('clave_opus') or '')[:20],
                'DESC':     (nodo.get('descripcion') or ''),
                'PRE_WBS':  (nodo.get('wbs') or '')[:20],
                'PRECIOMN': pu,
                'PRECIOME': 0.0,
                'DESCCORTA':(nodo.get('descripcion_corta') or '')[:30],
            })

        self._crear_tabla(self._ruta('A'), 'A', registros_a, cdx_sufijo='A')
        self._id_a_iduni = id_a_iduni

    # ── FASE 4: APU → F.DBF + N.DBF ──────────────────────────────────

    def _fase4_apu(self):
        nodos   = self._nodo_repo.todos(self._pid)
        insumos = {i['id']: i for i in self._ins_repo.todos(self._pid)}
        # ponytail: precalcular todos los resúmenes en memoria
        resumenes = self._rc_repo.calcular_todos_resumenes(self._pid)

        registros_f = []
        registros_n = []
        matrices_vistas: set = set()

        def _add_f(nombre_parent, pref_parent, componentes):
            for orden, comp in enumerate(componentes, start=1):
                ins = insumos.get(comp['insumo_id'])
                if not ins:
                    continue
                clave_ins  = (ins.get('clave_opus') or '')[:20]
                prefcomp   = int(ins.get('tipo_id') or 1)
                is_div   = comp.get('operador', '*') == '/'
                valor    = float(comp.get('valor') or 0)
                precio   = float(comp.get('precio') or 0)
                importe  = precio / (valor or 1.0) if is_div else valor * precio
                registros_f.append({
                    'PREF':       pref_parent,
                    'NOMBRE':     nombre_parent[:20],
                    'PREFCOMP':   prefcomp,
                    'COMPONENTE': clave_ins,
                    'CLAVENUM':   orden * 100,
                    'NOELE':      1.0,
                    'RENDTO':     (valor or 1.0) if is_div else 1.0,
                    'CANTIDAD':   1.0 if is_div else valor,
                    'EXPRESION':  str(comp.get('formula') or (1.0 if is_div else valor)),
                    'COSTO':      precio,
                    'TOTALMN':    importe,
                    'TOTALME':    0.0,
                    'CAMPOREND':  chr(1),
                    'TIPOCH':     '',
                    'IMPORTE':    importe,
                    'IMPORTEMN':  importe,
                    'IMPORTEME':  0.0,
                    'EXPRESIONM': 0.0,
                    'EXPRESIONO': 0.0,
                    'TIPOREND':   '2',
                    'CAMPORENDM': chr(1),
                    'CAMPORENDO': chr(1),
                    'DARENDIM':   False,
                    'MEMOCAD':    '',
                    'MARCAAJU':   True,
                    'CVEEROG':    '',
                })

        def _add_n(nombre, resumen):
            if not resumen:
                return
            mm = float(resumen.get('materiales') or 0)
            oo = float(resumen.get('mano_obra') or 0)
            hh = float(resumen.get('herramienta') or 0)
            ee = float(resumen.get('equipo') or 0)
            aa = float(resumen.get('auxiliares') or 0)
            sc = float(resumen.get('subcontratos') or 0)
            registros_n.append({
                'NOMBRE':    nombre[:20],
                'MM': mm, 'OO': oo, 'HH': hh, 'EE': ee, 'AA': aa,
                'SUBCONT':   sc,
                'ACARREOS':  0.0,
                'DESTAJOS':  0.0,
                'INDIRECTOS': 0.0,
                'FINANCIA':  0.0,
                'UTILIDAD':  0.0,
                'OTROS':     0.0,
                'RENDMTO':   0.0,
                'PP':        mm + oo + hh + ee + aa + sc,
                'INDIRECTO2':0.0,
                'SINPORCE':  '',
            })

        # Conceptos EP (matriz_id > 0)
        for nodo in nodos:
            mid  = nodo['id']
            comp = self._apu_repo.por_matriz(mid)
            if not comp:
                continue
            nombre = (nodo.get('clave_opus') or '')
            _add_f(nombre, 32, comp)
            if mid not in matrices_vistas:
                matrices_vistas.add(mid)
                _add_n(nombre, resumenes.get(mid))

        # Insumos compuestos (matriz_id < 0)
        cur = self._conn.cursor()
        for (ins_id,) in cur.execute(
            'SELECT DISTINCT ABS(matriz_id) FROM apu_matrices WHERE matriz_id < 0'
        ):
            ins_parent = insumos.get(ins_id)
            if not ins_parent:
                continue
            comp = self._apu_repo.por_matriz(-ins_id)
            if not comp:
                continue
            nombre = (ins_parent.get('clave_opus') or '')
            pref   = int(ins_parent.get('tipo_id') or 32)
            _add_f(nombre, pref, comp)
            key = -ins_id
            if key not in matrices_vistas:
                matrices_vistas.add(key)
                _add_n(nombre, resumenes.get(-ins_id))

        self._crear_tabla(self._ruta('F'), 'F', registros_f, cdx_sufijo='F')
        self._crear_tabla(self._ruta('N'), 'N', registros_n, cdx_sufijo='N')

    # ── FASE 5: Derivados → 5.DBF + X.DBF ────────────────────────────

    def _fase5_derivados(self):
        insumos = {i['id']: i for i in self._ins_repo.todos(self._pid)}
        cur = self._conn.cursor()

        # 5.DBF — composición básicos
        registros_5 = []
        for (ins_id,) in cur.execute(
            'SELECT DISTINCT ABS(matriz_id) FROM apu_matrices WHERE matriz_id < 0'
        ):
            ins_parent = insumos.get(ins_id)
            if not ins_parent:
                continue
            for comp in self._apu_repo.por_matriz(-ins_id):
                ins_comp = insumos.get(comp['insumo_id'])
                if not ins_comp:
                    continue
                valor    = float(comp.get('valor') or 0)
                precio   = float(ins_comp.get('costo_final') or 0)
                importe  = valor * precio
                registros_5.append({
                    'PREFIJO':  int(ins_parent.get('tipo_id') or 1),
                    'NOMBRE':   (ins_parent.get('clave_opus') or '')[:20],
                    'PREFCOMP': int(ins_comp.get('tipo_id') or 1),
                    'COMPONE':  (ins_comp.get('clave_opus') or '')[:20],
                    'UNIPOR':   0,
                    'CANTIDAD': valor,
                    'PRECIO':   precio,
                    'MONTO':    importe,
                    'CANCONC':  valor,
                    'PRECIOMN': precio,
                    'PRECIOME': 0.0,
                    'MONTOMN':  importe,
                    'MONTOME':  0.0,
                })
        self._crear_tabla(self._ruta('5'), '5', registros_5, cdx_sufijo='5')

        # X.DBF — explosión primer nivel
        nodos = [n for n in self._nodo_repo.todos(self._pid) if n['tipo'] == 'concepto']
        registros_x = []
        for nodo in nodos:
            cant_nodo = float(nodo.get('cantidad') or 0)
            for comp in self._apu_repo.por_matriz(nodo['id']):
                ins = insumos.get(comp['insumo_id'])
                if not ins:
                    continue
                is_div   = comp.get('operador', '*') == '/'
                valor    = float(comp.get('valor') or 0)
                cantidad = (1.0 if is_div else valor) * cant_nodo
                precio   = float(ins.get('costo_final') or 0)
                registros_x.append({
                    'PREFIJO':    int(ins.get('tipo_id') or 1),
                    'NOMBRE':     (ins.get('clave_opus') or '')[:20],
                    'CLAVEUSUAR': '',
                    'UNIPOR':     0,
                    'CANTIDAD':   cantidad,
                    'PRECIO':     precio,
                    'MONTO':      cantidad * precio,
                    'ESTOTAL':    '3',
                    'EXP_GRUPO':  (ins.get('familia_nombre') or '')[:20],
                    'PESO':       0.0,
                    'AJUSTA':     '',
                    'MONT_SINAJ': cantidad * precio,
                })
        self._crear_tabla(self._ruta('X'), 'X', registros_x, cdx_sufijo='X')

    # ── FASE 7: FSR ───────────────────────────────────────────────────

    def _fase7_fsr(self):
        # 8.DBF — 1 registro FSR
        fsr_rec = {
            'FSR_TIP': 0, 'FSR_CLV': 'JOR8HR', 'FSR_DES': 'Factor de Salario Real FSR',
            'FSR_SABA': 100.0, 'FSR_SAMI': 1.0, 'FSR_PPVAC': 25.0, 'FSR_PPDOM': 0.0,
            'FSR_DPCAL': 365.25, 'FSR_DPAGU': 15.0, 'FSR_DPPVA': 1.5, 'FSR_DPPDO': 0.0,
            'FSR_DPHEX': 0.0, 'FSR_DPOT1': 0.0, 'FSR_FSI': 1.3182, 'FSR_SABC': 1.81895,
            'FSR_IMGM': 1.05, 'FSR_IMPE': 0.7, 'FSR_IMEX': 0.0, 'FSR_IMRTR': 7.58875,
            'FSR_IMENF': 5.35365, 'FSR_IMINV': 1.75, 'FSR_IMCE': 3.15, 'FSR_IMGUA': 1.0,
            'FSR_IMIMS': 0.2974, 'FSR_IMNOM': 0.0, 'FSR_IMSAR': 2.0, 'FSR_IMINF': 5.0,
            'FSR_IMOT2': 0.0, 'FSR_DEIMS': 74.74, 'FSR_DEGUA': 3.815, 'FSR_DENOM': 0.0,
            'FSR_DESAR': 7.63, 'FSR_DEINF': 19.075, 'FSR_DEOT2': 0.0, 'FSR_DNDOM': 0.0,
            'FSR_DNSEP': 52.18, 'FSR_DNFES': 7.17, 'FSR_DNDCO': 0.0, 'FSR_DNSIN': 1.0,
            'FSR_DNVAC': 6.0, 'FSR_DVAC': 6.0, 'FSR_DNPER': 0.45, 'FSR_DNCLI': 3.85,
            'FSR_DNARR': 0.0, 'FSR_DNGUA': 0.0, 'FSR_DNOT3': 5.0, 'FSR_DNLA': 75.65,
            'FSR_DLA': 289.6, 'FSR_DPA': 381.75, 'FSR_DEA': 105.26, 'FSR_DCA': 486.76,
            'FSR_FSR': 1.77912, 'FSR_CALC': True, 'FSR_FSBC': 1.04517, 'FSR_SACAL': 1.74034,
            'AA': 20.4, 'AB': 1.1, 'AC': 0.204, 'AD': 0.0, 'AE': 0.01273, 'AF': 0.0191,
            'AG': 0.03183, 'AH': 0.01819, 'AI': 0.03638, 'AJ': 0.0573, 'AK': 0.13804,
            'AL': 0.51757, 'AM': 0.09095, 'AN': 0.0, 'AO': 0.0, 'AP': 0.60852,
            'AQ': 0.34966, 'AR': 1.0, 'AS': 25.0, 'AT': 1.0, 'AU': 0.0, 'AV': 2010.0,
            'AW': 57.46, 'AX': 20040101.0, 'AY': 25.0, 'AZ': 25.0, 'BA': 25.0,
            'BB': 0.0, 'BC': 8.0, 'BD': 0.0, 'BE': 1.1875, 'BF': 0.0, 'BG': 0.0,
            'BH': 0.46092,
        }
        self._crear_tabla(self._ruta('8'), '8', [fsr_rec], cdx_sufijo='8')
        # 9.DBF
        self._crear_tabla(self._ruta('9'), '9', FSR_9_ROWS, cdx_sufijo='9')
        # Z.DBF — sin CDX
        z_rec = {
            'ANCNIVI1': 1, 'ANCNIVI2': 1, 'ANCNIVI3': 2,
            'INAC_CAPI': 0.0, 'ESPE_CAPI': 0.0, 'TIPODEPEN': 0,
            'INAC_PIEZ': 0.0, 'ESPE_PIEZ': 0.0, 'FHPKW': 0.746,
            'HORASDIA': 24, 'MINSDIA': 0, 'HINIDIA': 0, 'MINIDIA': 0,
            'HORAENFECH': '', 'DURENDT': False,
            'CPO_FSBSG': 'FSR_FSI', 'CFARG': False, 'CPO_FPIMSS': '',
            'VARFINPPP': '', 'SEGURO': 0.0, 'TASA_INTER': 0.0,
            'IDFORESCPR': 0,
        }
        self._crear_tabla(self._ruta('Z'), 'Z', [z_rec])  # sin CDX

    # ── FASE 8: Tablas vacías + auxiliares ────────────────────────────

    def _fase8_vacias(self):
        vacias = {
            '0': '0', '3': '3', 'D': 'D', 'H': 'H',
            'J': 'J', 'R': 'R', 'W': 'W',
        }
        for schema_k, sufijo in vacias.items():
            try:
                self._crear_tabla_vacia(schema_k, sufijo)
            except Exception as e:
                self._errores.append(f'  tabla vacía {sufijo}: {e}')

        # Archivos V/U/FMP (vacíos)
        for ext in ['.DCD', '.DCI', '.FDD', '.FDI', '.FED', '.FEI', '.FID']:
            (self._destino / f'{self._clave}V{ext}').touch()
        for ext in ['.UTD', '.UTI', '.UTV']:
            (self._destino / f'{self._clave}U{ext}').touch()
        (self._destino / f'{self._clave}.FMP').touch()
        self._log.append('Archivos aux: ok')

    # ── FASE 9: OBRA.DBF ─────────────────────────────────────────────

    def _fase9_obra_dbf(self):
        if not self._ruta_opus:
            self._log.append('OBRA.DBF: omitido (ruta_opus no configurada)')
            return
        obra_path = Path(self._ruta_opus) / 'OBRA.DBF'
        if not obra_path.exists():
            self._errores.append(f'OBRA.DBF no encontrado en {self._ruta_opus}')
            return
        try:
            t = dbf.Table(str(obra_path), codepage=_CP)
            t.open(mode=dbf.READ_WRITE)
            existe = any(
                (rec['OBRA'].strip() if 'OBRA' in t.field_names else '') == self._clave
                for rec in t
            )
            if not existe:
                t.append({
                    'OBRA':       self._clave[:10],
                    'DIRECTORIO': str(self._destino)[:100],
                })
                self._log.append(f'OBRA.DBF: {self._clave} registrada')
            else:
                self._log.append(f'OBRA.DBF: {self._clave} ya existía')
            t.close()
        except Exception as e:
            self._errores.append(f'OBRA.DBF: {e}')
