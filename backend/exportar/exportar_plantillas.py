"""
exportar_plantillas.py
======================
Datos fijos para la exportación de Open APU Studio → OPUS 2010.

Contiene:
  - TIPOSINS_ROWS       : 8 tipos de insumo fijos
  - CONFIG_FIJOS        : campos fijos de CONFIG.DBF
  - FSR_9_ROWS          : 85 registros fijos de [Obra]9.DBF
  - CONFIG_INI_TEMPLATE : contenido de CONFIG.INI
"""

from datetime import date

# ---------------------------------------------------------------------------
# TIPOSINS.DBF  — 8 registros fijos
# ---------------------------------------------------------------------------

from frontend.ventana.tipos_insumo import OPUS_ROWS as TIPOSINS_ROWS

# ---------------------------------------------------------------------------
# CONFIG.DBF  — campos fijos (no vienen del proyecto)
# ---------------------------------------------------------------------------

CONFIG_FIJOS = {
    'CCANTI':      6,
    'VCANTI':      2,
    'VPRECI':      2,
    'TCAMBIO':     1.0,
    'MONEXT':      'DOLARES',
    'SIMBEXT':     'USD',
    'CVSLETRA':    False,
    'CLIENTE':     '',
    'AUTOR':       '',
    'FSDI':        1.0,
    'TFCONTRATO':  1,
    'TFDESGLOSE':  1,
    'TFESTIMA':    1,
    'TFDESGLOES':  1,
    'TFRESPONSA':  1,
    'TFDOCSALMA':  1,
    'TFDESDOCSA':  1,
    'TFDESDOCEN':  1,
    'TFEDOALMA':   1,
    'TFDESEDOAL':  1,
    'TFACTIVIDA':  4,
    'TFCARACTER':  1,
    'VERSION':     2010.05,
    'PRESICION':   6,
    'BUSCA':       '',
    'CLAVE':       '',
    'FECHAVA':     None,
    'TIPOPRESAL':  2,
    'NIVELSAL':    0,
    'CONCOMPRAS':  True,
    'TFREQS':      1,
    'TFREQSDET':   1,
    'TFORDENES':   1,
    'TFDESGLADI':  1,
    'TFDESGLOOC':  1,
    'TFESTIMAOC':  1,
}

# ---------------------------------------------------------------------------
# [Obra]C.DBF  — bloques de campos fijos (títulos, niveles, fórmulas, etc.)
# ---------------------------------------------------------------------------

C_FIJOS = {
    # Títulos
    'TITDIR':    'Costo Directo',
    'TITSAL':    'Total Salarios Base',
    'TITMOI':    'Mano de Obra en Indirectos',
    'TITGRA':    'Total Salario Gravable de SAR e INF',
    'TITIND':    'Indirectos',
    'TITIND2':   'Indirectos de Campo',
    'TITSUB1':   'Subtotal',
    'TITSUB2':   'Subtotal',
    'TITSUB3':   'Subtotal',
    'TITSUB4':   'Subtotal',
    'TITSUB5':   'Subtotal',
    'TITFIN':    'Financiamiento',
    'TITUTI':    'Utilidad',
    'TITSAR':    'SAR',
    'TITINF':    'INFONAVIT',
    'TITCAD':    'Cargos Adicionales',
    'TITOTR':    'Otro porcentaje',
    'TITIVA':    'Impuesto',
    'TITPBASEM': 'Costo base',
    'TITPBASEO': 'Sal. Base',
    'TITPBASEH': 'Costo base',
    'TITPBASEE': 'Costo base',
    'TITPBASEA': 'Costo base',
    'TITPBASEC': 'Costo base',
    'TITADM':    'Flete',
    'TITADO':    'Viáticos',
    'TITADH':    'Flete',
    'TITADE':    'Flete',
    'TITADA':    'Flete',
    'TITADC':    'Flete',
    'TITBEM':    'Derechos',
    'TITBEO':    'Presta.',
    'TITBEH':    'Derechos',
    'TITBEE':    'Derechos',
    'TITBEA':    'Derechos',
    'TITBEC':    'Derechos',
    'TITCFM':    'Mermas',
    'TITCFO':    'Otros',
    'TITCFH':    'Mermas',
    'TITCFE':    'Mermas',
    'TITCFA':    'Mermas',
    'TITCFC':    'Mermas',
    'TITOTM':    'Costo unitario',
    'TITOTO':    'Sal. Real',
    'TITOTH':    'Costo unitario',
    'TITOTE':    'Costo unitario',
    'TITOTA':    'Costo unitario',
    'TITOTC':    'Costo unitario',
    # Niveles
    'LEYNIV1':   'Capítulo',
    'LEYNIV2':   'Subcapítulo',
    'LEYNIV3':   'Nivel 3',
    'LEYNIV4':   'Nivel 4',
    'LEYNIV5':   'Nivel 5',
    'LEYNIV6':   'Nivel 6',
    'LEYNIV7':   'Nivel 7',
    'LEYNIV8':   'Nivel 8',
    'LEYNIV9':   'Nivel 9',
    'LEYCON':    'Concepto',
    # Fórmulas (MN)
    'FORMUMATN': 'PBASEMN+A+B+C',
    'FORMUMOBN': 'PBASEMN+A+B+C',
    'FORMUHERN': 'PBASEMN+A+B+C',
    'FORMUEQUN': 'PBASEMN+A+B+C',
    'FORMUAUXN': 'PBASEMN+A+B+C',
    'FORMUCONN': 'PBASEMN+A+B+C',
    # Fórmulas (ME)
    'FORMUMATE': 'PBASEME+D+E+F',
    'FORMUMOBE': 'PBASEME+D+E+F',
    'FORMUHERE': 'PBASEME+D+E+F',
    'FORMUEQUE': 'PBASEME+D+E+F',
    'FORMUAUXE': 'PBASEME+D+E+F',
    'FORMUCONE': 'PBASEME+D+E+F',
    # Moneda
    'LEYREMMN':  'M.N.',
    'LEYCVSMN':  '/100',
    'LEYREMME':  '',
    'ABREVMN':   'M.N.',
    'ABREVME':   'M.E.',
    # Permisos
    'PONDIR':    True,
    'PONSAL':    False,
    'PONMOI':    False,
    'PONGRA':    False,
    'PONPMOI':   False,
    'PONIND':    True,
    'PONIND2':   True,
    'PONSUB1':   True,
    'PONFIN':    True,
    'PONSUB2':   True,
    'PONUTI':    True,
    'PONSUB3':   False,
    'PONSAR':    False,
    'PONINF':    False,
    'PONSUB4':   False,
    'PONCAD':    True,
    'PONSUB5':   False,
    'PONOTR':    True,
    # Equipo
    'INAC_DEP':  80.0,  'INAC_INV':  100.0, 'INAC_SEG':  100.0,
    'INAC_MAN':  80.0,  'INAC_ALM':  100.0, 'INAC_OTR':  0.0,
    'INAC_COM':  0.0,   'INAC_LUB':  0.0,   'INAC_LLA':  0.0,
    'INAC_OPE':  100.0, 'INAC_OTRIN':0.0,
    'ESPE_DEP':  80.0,  'ESPE_INV':  100.0, 'ESPE_SEG':  100.0,
    'ESPE_MAN':  100.0, 'ESPE_ALM':  0.0,   'ESPE_OTR':  0.0,
    'ESPE_COM':  30.0,  'ESPE_LUB':  30.0,  'ESPE_LLA':  0.0,
    'ESPE_OPE':  100.0, 'ESPE_OTRIN':0.0,
    # Anchos de nivel
    'ANCNIV1':   1,  'ANCNIV2':   1,  'ANCNIV3':   1,
    'ANCNIV4':   2,  'ANCNIV5':   2,  'ANCNIV6':   0,
    'ANCNIV7':   0,  'ANCNIV8':   0,  'ANCNIV9':   0,
    'ANCNIVA1':  1,  'ANCNIVA2':  0,  'ANCNIVA3':  0,
    'ANCNIVA4':  0,  'ANCNIVA5':  0,  'ANCNIVA6':  0,
    'ANCNIVA7':  0,  'ANCNIVA8':  0,  'ANCNIVA9':  0,
    # Colores
    'COLNIV1':   117440512, 'COLNIV2':   128,       'COLNIV3':   50331903,
    'COLNIV4':   8388608,   'COLNIV5':   32768,     'COLNIV6':   32896,
    'COLNIV7':   8388736,   'COLNIV8':   159416448, 'COLNIV9':   8421376,
    'COLCON':    117440512,
    # ID Formatos
    'IDFORHP':   2,  'IDFOREST':  2,  'IDFORXEST': 2,
    'IDFORACT':  6,  'IDFORSUM':  3,
    # Banderas
    'CVSLETRA':   False,
    'REGLA5':     True,
    'PORINDEST':  True,
    'ENOEM':      False,
    'YAFEN96':    True,
    'VERSION':    '2010.05',
    # FSR
    'FGRAVSAR':   1.29013,
    'FSRMIN':     0.0,
    'FSRSUP':     0.0,
    # Varios
    'TIPOIND':    1,
    'DECPORCE':   2,
    'CDURACION':  '36.5c',
    'ESCALAHIST': 1,
    'TIPCAM':     1.0,
    'LEYMONEXT':  'DOLARES',
    'SIMMONEXT':  'USD$',
}

# ---------------------------------------------------------------------------
# [Obra]9.DBF  — 85 registros fijos (FSR formatos)
# Extraídos de D60JALISCOT9.DBF con extraer_schemas.py
# ---------------------------------------------------------------------------

FSR_9_ROWS = [
    {'FFSR_REN': 570,  'FFSR_CLV': '',          'FFSR_DES': 'De cuotas del IMSS',                                  'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': False, 'MARCA4': False, 'FFSR_VAL': 0.0,     'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Obligaciones obrero patronales LSS e INFONAVIT'},
    {'FFSR_REN': 110,  'FFSR_CLV': 'FSR_DNVAC', 'FFSR_DES': 'Días de vacaciones para calcular prima vacacional',   'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 6.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 76, 78,79, 81 Ley Federal del Trabajo'},
    {'FFSR_REN': 120,  'FFSR_CLV': 'FSR_PPVAC', 'FFSR_DES': 'Prima vacacional',                                    'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 25.0,    'FFSR_UNI': '%',      'FFSR_IOP': False, 'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 80 Ley Federal del Trabajo'},
    {'FFSR_REN': 130,  'FFSR_CLV': 'FSR_DNDOM', 'FFSR_DES': 'Días para el cálculo de prima dominical',             'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 0.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 71 Ley Federal del Trabajo'},
    {'FFSR_REN': 140,  'FFSR_CLV': 'FSR_PPDOM', 'FFSR_DES': 'Porcentaje para prima dominical',                     'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 0.0,     'FFSR_UNI': '%',      'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 71 Ley Federal del Trabajo'},
    {'FFSR_REN': 990,  'FFSR_CLV': '',          'FFSR_DES': 'Del TP/TL y del FSR',                                  'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': False, 'FFSR_VAL': 0.0,     'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 80,   'FFSR_CLV': 'FSR_DPCAL', 'FFSR_DES': 'Días Calendario   (DC)',                               'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 365.25,  'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 90,   'FFSR_CLV': 'FSR_DPAGU', 'FFSR_DES': 'Días Aguinaldo',                                       'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 15.0,    'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 87 Ley Federal del Trabajo'},
    {'FFSR_REN': 500,  'FFSR_CLV': 'FSR_DPPVA', 'FFSR_DES': 'Prima vacacional',                                     'FFSR_FOR': 'FSR_PPVAC/100*FSR_DNVAC', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 1.5,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 80 Ley Federal del Trabajo'},
    {'FFSR_REN': 510,  'FFSR_CLV': 'FSR_DPPDO', 'FFSR_DES': 'Prima Dominical',                                      'FFSR_FOR': 'FSR_PPDOM/100*FSR_DNDOM', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 0.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 71 Ley Federal del Trabajo'},
    {'FFSR_REN': 515,  'FFSR_CLV': 'FSR_DPHEX', 'FFSR_DES': 'Días equivalentes por horas extras al año',            'FFSR_FOR': '(BF*2+BG*3)/24*FSR_DPCAL', 'MARCA1': True, 'MARCA2': None, 'MARCA3': None, 'MARCA4': True, 'FFSR_VAL': 0.0,    'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 61, 66 y 68 Ley Federal del Trabajo'},
    {'FFSR_REN': 150,  'FFSR_CLV': 'FSR_DPOT1', 'FFSR_DES': 'Otros',                                                'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 0.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 520,  'FFSR_CLV': 'FSR_DPA',   'FFSR_DES': 'SUMA de días pagados',                                 'FFSR_FOR': 'FSR_DPCAL+FSR_DPAGU+FSR_DPPVA+FSR_DPPDO+FSR_DPHEX+FSR_DPOT1', 'MARCA1': True, 'MARCA2': None, 'MARCA3': None, 'MARCA4': True, 'FFSR_VAL': 381.75, 'FFSR_UNI': 'días', 'FFSR_IOP': None, 'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Días Trabajados realmente pagados (Tp)'},
    {'FFSR_REN': 160,  'FFSR_CLV': 'FSR_DNSEP', 'FFSR_DES': 'Días de Descanso (Ley Federal del Trabajo)',           'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 52.18,   'FFSR_UNI': 'días',   'FFSR_IOP': False, 'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 69 y 73 Ley Federl del Trabajo'},
    {'FFSR_REN': 170,  'FFSR_CLV': 'FSR_DNFES', 'FFSR_DES': 'Festivos oficiales (Ley Federal del Trabajo)',         'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 7.17,    'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 74 Ley Federal del Trabajo'},
    {'FFSR_REN': 180,  'FFSR_CLV': 'FSR_DNDCO', 'FFSR_DES': 'Días no laborables según contrato colectivo',         'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 0.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 190,  'FFSR_CLV': 'FSR_DNSIN', 'FFSR_DES': 'Días Sindicato',                                       'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 1.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 490,  'FFSR_CLV': 'FSR_DVAC',  'FFSR_DES': 'Vacaciones',                                           'FFSR_FOR': 'FSR_DNVAC', 'MARCA1': True, 'MARCA2': None, 'MARCA3': None, 'MARCA4': True, 'FFSR_VAL': 6.0, 'FFSR_UNI': 'días', 'FFSR_IOP': None, 'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 76, 78,79, 81 Ley Federal del Trabajo'},
    {'FFSR_REN': 200,  'FFSR_CLV': 'FSR_DNPER', 'FFSR_DES': 'Enfermedad no profesional',                            'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 0.45,    'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Ley Federal del Trabajo y Ley del Seguro Social'},
    {'FFSR_REN': 210,  'FFSR_CLV': 'FSR_DNCLI', 'FFSR_DES': 'Condiciones Climat. (Lluvias y otros) Contr. Colec',  'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 3.85,    'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 220,  'FFSR_CLV': 'FSR_DNARR', 'FFSR_DES': 'En Horas Inactivas por Arrastre',                     'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 0.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 230,  'FFSR_CLV': 'FSR_DNGUA', 'FFSR_DES': 'Días no trabajados por Guardia',                      'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 0.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 240,  'FFSR_CLV': 'FSR_DNOT3', 'FFSR_DES': 'Otros Días no trabajados por costumbre',              'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 5.0,     'FFSR_UNI': 'días',   'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 530,  'FFSR_CLV': 'FSR_DNLA',  'FFSR_DES': 'SUMA de días no laborados',                            'FFSR_FOR': 'FSR_DNSEP+FSR_DNFES+FSR_DNDCO+FSR_DNSIN+FSR_DVAC+FSR_DNPER+FSR_DNCLI+FSR_DNARR+FSR_DNGUA+FSR_DNOT3', 'MARCA1': True, 'MARCA2': None, 'MARCA3': None, 'MARCA4': True, 'FFSR_VAL': 75.65, 'FFSR_UNI': 'días', 'FFSR_IOP': None, 'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 540,  'FFSR_CLV': 'FSR_DLA',   'FFSR_DES': 'Días  realmente laborados  (TL = DC - DNLA)',          'FFSR_FOR': 'FSR_DPCAL-FSR_DNLA', 'MARCA1': True, 'MARCA2': None, 'MARCA3': None, 'MARCA4': True, 'FFSR_VAL': 289.6, 'FFSR_UNI': 'días', 'FFSR_IOP': True, 'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Dias Trabajados realmente laborados (Tl)'},
    {'FFSR_REN': 630,  'FFSR_CLV': 'FSR_IMINV', 'FFSR_DES': 'Invalidez y vida',                                    'FFSR_FOR': '1.75+IIF(FSR_SACAL>FSR_SAMI,0,0.625)', 'MARCA1': True, 'MARCA2': None, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 1.75, 'FFSR_UNI': '%', 'FFSR_IOP': True, 'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 147  LSS y 97 LFT'},
    {'FFSR_REN': 350,  'FFSR_CLV': 'FSR_IMRTR', 'FFSR_DES': 'Riesgos de trabajo',                                  'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 7.58875, 'FFSR_UNI': '%',      'FFSR_IOP': None,  'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 72 y 73 LSS'},
    {'FFSR_REN': 920,  'FFSR_CLV': 'FSR_IMIMS', 'FFSR_DES': 'Factor de cuota patronal del IMSS = IMSS/SND',        'FFSR_FOR': 'AL/FSR_SACAL', 'MARCA1': True, 'MARCA2': True, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 0.2974, 'FFSR_UNI': 'factor', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'N', 'COMENTARIO': 'Ley del IMSS'},
    {'FFSR_REN': 320,  'FFSR_CLV': 'FSR_IMGUA', 'FFSR_DES': 'Guarderias',                                          'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 1.0,     'FFSR_UNI': '%',      'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 211 LSS'},
    {'FFSR_REN': 400,  'FFSR_CLV': 'FSR_IMNOM', 'FFSR_DES': 'Impuesto Nómina',                                     'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 0.0,     'FFSR_UNI': '%',      'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 330,  'FFSR_CLV': 'FSR_IMSAR', 'FFSR_DES': 'Retiro',                                              'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 2.0,     'FFSR_UNI': '%',      'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 168 fracc. I LSS'},
    {'FFSR_REN': 390,  'FFSR_CLV': 'FSR_IMINF', 'FFSR_DES': 'Impuesto INFONAVIT',                                  'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 5.0,     'FFSR_UNI': '%',      'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 29-II LINFONAVIT'},
    {'FFSR_REN': 410,  'FFSR_CLV': 'FSR_IMOT2', 'FFSR_DES': 'Otros impuestos',                                     'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 0.0,     'FFSR_UNI': '%',      'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 1100, 'FFSR_CLV': 'FSR_FSR',   'FFSR_DES': 'FSR = Ps (Tp/Tl) + Tp/Tl',                            'FFSR_FOR': 'BH+FSR_FSI', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': True, 'FFSR_VAL': 1.77912, 'FFSR_UNI': '', 'FFSR_IOP': True, 'DECIMALES': 5, 'DEUSUARIO': 'N', 'COMENTARIO': 'Art.160 y 161 Reglamento de la Ley de Obra Pública y Servicios Relacionadas con las Mismas'},
    {'FFSR_REN': 475,  'FFSR_CLV': 'FSR_SAMI',  'FFSR_DES': 'Salario Mínimo General (D.F.)',                        'FFSR_FOR': 'IIF(AT=1,1,AW)', 'MARCA1': True, 'MARCA2': False, 'MARCA3': None, 'MARCA4': None, 'FFSR_VAL': 1.0, 'FFSR_UNI': '', 'FFSR_IOP': False, 'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 90 Ley Fed. del Trabajo - Comisión Nacional de Salarios Mínimos'},
    {'FFSR_REN': 40,   'FFSR_CLV': 'FSR_SABA',  'FFSR_DES': 'Salario Nominal (SN)',                                 'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 100.0,   'FFSR_UNI': '$',      'FFSR_IOP': False, 'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 82 Ley Federal del Trabajo'},
    {'FFSR_REN': 560,  'FFSR_CLV': 'FSR_SABC',  'FFSR_DES': 'Salario Base de Cotización (SB = FSBC * SN)',          'FFSR_FOR': 'FSR_SACAL * FSR_FSBC', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': True, 'FFSR_VAL': 1.81895, 'FFSR_UNI': '', 'FFSR_IOP': True, 'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Salario nominal con Factor de Empresa'},
    {'FFSR_REN': 620,  'FFSR_CLV': 'FSR_IMGM',  'FFSR_DES': 'Gastos medicos. Pensionados (Patrón-Obrero)',          'FFSR_FOR': '1.05+IIF(FSR_SACAL>FSR_SAMI,0,0.375)', 'MARCA1': True, 'MARCA2': None, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 1.05, 'FFSR_UNI': '%', 'FFSR_IOP': True, 'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 25  LSS (Prest. en especie) y 97 LFT'},
    {'FFSR_REN': 610,  'FFSR_CLV': 'FSR_IMPE',  'FFSR_DES': 'Prestaciones en dinero (Patron+obrero)',               'FFSR_FOR': '.7+IIF(FSR_SACAL>FSR_SAMI,0,0.25)', 'MARCA1': True, 'MARCA2': None, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 0.7, 'FFSR_UNI': '%', 'FFSR_IOP': True, 'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 107  LSS y 97 LFT'},
    {'FFSR_REN': 640,  'FFSR_CLV': 'FSR_IMCE',  'FFSR_DES': 'Cesantía en edad avanzada y vejez',                   'FFSR_FOR': '3.15+IIF(FSR_SACAL>FSR_SAMI,0,1.125)', 'MARCA1': True, 'MARCA2': None, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 3.15, 'FFSR_UNI': '%', 'FFSR_IOP': True, 'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 168 fracc. II LSS y 97 LFT'},
    {'FFSR_REN': 0,    'FFSR_CLV': '',          'FFSR_DES': 'DATOS BASICOS',                                        'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': True,  'FFSR_VAL': 0.0,     'FFSR_UNI': '',       'FFSR_IOP': False, 'DECIMALES': 2, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 550,  'FFSR_CLV': 'FSR_FSBC',  'FFSR_DES': '(FSBC = DPA/DPCAL)',                                   'FFSR_FOR': 'FSR_DPA/FSR_DPCAL', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': True, 'FFSR_VAL': 1.04517, 'FFSR_UNI': '', 'FFSR_IOP': True, 'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Factor para SBC'},
    {'FFSR_REN': 480,  'FFSR_CLV': 'FSR_SACAL', 'FFSR_DES': 'Salario Nominal por jornada (SND)',                   'FFSR_FOR': 'IIF(AT=1,FSR_SABA*(1+BG/IIF(BB=0,8,IIF(BB=1,7.5,7)))/AW,FSR_SABA*(1+BG/IIF(BB=0,8,IIF(BB=1,7.5,7))))', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': False, 'FFSR_VAL': 1.74034, 'FFSR_UNI': '', 'FFSR_IOP': False, 'DECIMALES': 5, 'DEUSUARIO': ' ', 'COMENTARIO': 'Art. 82 y 83 Ley Federal del Trabajo'},
    {'FFSR_REN': 580,  'FFSR_CLV': 'AA',        'FFSR_DES': 'Porcentaje sobre salario mínimo para cuota fija',     'FFSR_FOR': 'IIF(AV=2003,17.15,IIF(AV=2004,17.80,IIF(AV=2005,18.45,IIF(AV=2006,19.10,IIF(AV=2007,19.75,20.40)))))', 'MARCA1': True, 'MARCA2': None, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 20.4, 'FFSR_UNI': '%', 'FFSR_IOP': None, 'DECIMALES': 2, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 106 Fracc. I LSS'},
    {'FFSR_REN': 590,  'FFSR_CLV': 'AB',        'FFSR_DES': 'Porcentaje para Excedente a 3 SMGDF',                 'FFSR_FOR': 'IIF(AV=2003,3.55,IIF(AV=2004,3.06,IIF(AV=2005,2.57,IIF(AV=2006,2.08,IIF(AV=2007,1.59,1.10)))))', 'MARCA1': True, 'MARCA2': None, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 1.1, 'FFSR_UNI': '%', 'FFSR_IOP': None, 'DECIMALES': 2, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 106 Fracc. II LSS'},
    {'FFSR_REN': 980,  'FFSR_CLV': 'AQ',        'FFSR_DES': 'Obligaciones patronales entre SN',                    'FFSR_FOR': 'AP/FSR_SACAL', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': True, 'FFSR_VAL': 0.34966, 'FFSR_UNI': '', 'FFSR_IOP': True, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art.160 y 161 Reglamento de la Ley de Obra Pública y Servicios Relacionadas con las Mismas'},
    {'FFSR_REN': 970,  'FFSR_CLV': 'AP',        'FFSR_DES': 'Obligaciones patronales (IOP)',                        'FFSR_FOR': 'AL+AM+AN+AO', 'MARCA1': True, 'MARCA2': True, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 0.60852, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'IMSS e INFONAVIT'},
    {'FFSR_REN': 820,  'FFSR_CLV': 'AC',        'FFSR_DES': 'Enfermedad y maternidad. Cuota fija especie',         'FFSR_FOR': 'AA/100*FSR_SAMI', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.204, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 106 Fracc. I LSS'},
    {'FFSR_REN': 830,  'FFSR_CLV': 'AD',        'FFSR_DES': 'Enferm.-matern. Exc. a 3 S.M.D.F. especie',          'FFSR_FOR': 'IIF(FSR_SABC<BA,AB/100*AU, AB/100*BA)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.0, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 106 Fracc. II LSS'},
    {'FFSR_REN': 840,  'FFSR_CLV': 'AE',        'FFSR_DES': 'Enfermedad y maternidad. Prestaciones en dinero',    'FFSR_FOR': 'IIF(FSR_SABC<BA,FSR_IMPE/100*FSR_SABC, FSR_IMPE/100*BA)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.01273, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 107  LSS'},
    {'FFSR_REN': 850,  'FFSR_CLV': 'AF',        'FFSR_DES': 'Enfermedad y maternidad gastos médicos pensionados', 'FFSR_FOR': 'IIF(FSR_SABC<BA,FSR_IMGM/100*FSR_SABC, FSR_IMGM/100*BA)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.0191, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 25  LSS (Prest. en especie)'},
    {'FFSR_REN': 860,  'FFSR_CLV': 'AG',        'FFSR_DES': 'Invalidez y vida',                                    'FFSR_FOR': 'IIF(FSR_SABC<AY,FSR_IMINV/100*FSR_SABC, FSR_IMINV/100*AY)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.03183, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 147  LSS'},
    {'FFSR_REN': 870,  'FFSR_CLV': 'AH',        'FFSR_DES': 'Guarderías',                                          'FFSR_FOR': 'IIF(FSR_SABC<BA,FSR_IMGUA/100*FSR_SABC, FSR_IMGUA/100*BA)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.01819, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 211  LSS'},
    {'FFSR_REN': 880,  'FFSR_CLV': 'AI',        'FFSR_DES': 'Retiro',                                              'FFSR_FOR': 'IIF(FSR_SABC<BA,FSR_IMSAR/100*FSR_SABC, FSR_IMSAR/100*BA)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.03638, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 168 fracc. I LSS'},
    {'FFSR_REN': 890,  'FFSR_CLV': 'AJ',        'FFSR_DES': 'Cesantía en edad avanzada y vejez',                   'FFSR_FOR': 'IIF(FSR_SABC<AY,FSR_IMCE/100*FSR_SABC, FSR_IMCE/100*AY)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.0573, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 168 fracc. II LSS'},
    {'FFSR_REN': 900,  'FFSR_CLV': 'AK',        'FFSR_DES': 'Riesgos de trabajo',                                  'FFSR_FOR': 'IIF(FSR_SABC<BA,FSR_IMRTR/100*FSR_SABC, FSR_IMRTR/100*BA)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.13804, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 73 LSS'},
    {'FFSR_REN': 950,  'FFSR_CLV': 'AN',        'FFSR_DES': 'Impuesto sobre Nómina',                               'FFSR_FOR': 'FSR_IMNOM/100*FSR_SABC', 'MARCA1': True, 'MARCA2': True, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 0.0, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': ''},
    {'FFSR_REN': 940,  'FFSR_CLV': 'AM',        'FFSR_DES': 'INFONAVIT',                                           'FFSR_FOR': 'IIF(FSR_SABC<AZ,FSR_IMINF/100*FSR_SABC,FSR_IMINF/100*AZ)', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.09095, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 29-II LINFONAVIT'},
    {'FFSR_REN': 960,  'FFSR_CLV': 'AO',        'FFSR_DES': 'Otros impuestos',                                     'FFSR_FOR': 'FSR_IMOT2/100*FSR_SABC', 'MARCA1': True, 'MARCA2': True, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 0.0, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': ''},
    {'FFSR_REN': 910,  'FFSR_CLV': 'AL',        'FFSR_DES': 'Cuota patronal del IMSS',                             'FFSR_FOR': 'AC+AD+AE+AF+AG+AH+AI+AJ+AK', 'MARCA1': True, 'MARCA2': True, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.51757, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Ley del IMSS'},
    {'FFSR_REN': 20,   'FFSR_CLV': 'AT',        'FFSR_DES': 'Desea el cálculo: Por Factores=1, Por dinero=0',      'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 1.0,     'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': 1, 'DEUSUARIO': 'S', 'COMENTARIO': 'Capture 0 ó 1 según sea el caso'},
    {'FFSR_REN': 30,   'FFSR_CLV': 'AW',        'FFSR_DES': 'Salario Mínimo General (Distrito Federal) CNSM',      'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 57.46,   'FFSR_UNI': '$',      'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 90 Ley Fed. del Trabajo - Comisión Nacional de Salarios Mínimos'},
    {'FFSR_REN': 600,  'FFSR_CLV': 'AU',        'FFSR_DES': 'Excedente de 3 SMGDF',                                'FFSR_FOR': 'IIF(FSR_SABC<=3*FSR_SAMI,0,FSR_SABC-3*FSR_SAMI)', 'MARCA1': True, 'MARCA2': None, 'MARCA3': True, 'MARCA4': None, 'FFSR_VAL': 0.0, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 106 fracc. II y 19° Transitorio 2° Párrafo'},
    {'FFSR_REN': 50,   'FFSR_CLV': 'AV',        'FFSR_DES': 'Año (AAAA)',                                          'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 2010.0,  'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': 0, 'DEUSUARIO': 'S', 'COMENTARIO': 'Para cuota de Enfermedad y Maternidad y para Invalidez y Vida'},
    {'FFSR_REN': 660,  'FFSR_CLV': 'AY',        'FFSR_DES': 'Límite de prest. Inv., vida, cesantía y vejez',       'FFSR_FOR': 'AS*FSR_SAMI', 'MARCA1': True, 'MARCA2': None, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 25.0, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 147 y 148 LSS'},
    {'FFSR_REN': 930,  'FFSR_CLV': 'AZ',        'FFSR_DES': 'Limite de Aportaciones INFONAVIT',                    'FFSR_FOR': 'AY', 'MARCA1': True, 'MARCA2': None, 'MARCA3': None, 'MARCA4': None, 'FFSR_VAL': 25.0, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 0, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 29 de INFONAVIT'},
    {'FFSR_REN': 650,  'FFSR_CLV': 'BA',        'FFSR_DES': 'Límite de prest. patronales general',                 'FFSR_FOR': '25*FSR_SAMI', 'MARCA1': False, 'MARCA2': None, 'MARCA3': False, 'MARCA4': None, 'FFSR_VAL': 25.0, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 28 LSS'},
    {'FFSR_REN': 10,   'FFSR_CLV': '',          'FFSR_DES': 'De concurso',                                          'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': False, 'FFSR_VAL': None,    'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': None, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 70,   'FFSR_CLV': '',          'FFSR_DES': 'Para el cálculo de días pagados',                      'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': False, 'FFSR_VAL': None,    'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': None, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 250,  'FFSR_CLV': '',          'FFSR_DES': 'Para el calculo de cuotas del IMSS',                   'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': False, 'FFSR_VAL': None,    'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': None, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 380,  'FFSR_CLV': '',          'FFSR_DES': 'Para otros impuestos',                                  'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': False, 'FFSR_VAL': None,    'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': None, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 430,  'FFSR_CLV': '',          'FFSR_DES': 'CALCULO',                                              'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': False, 'FFSR_VAL': None,    'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': None, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 440,  'FFSR_CLV': '',          'FFSR_DES': 'De datos básicos a utilizar',                           'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': False, 'MARCA3': None,  'MARCA4': False, 'FFSR_VAL': None,    'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': None, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 485,  'FFSR_CLV': '',          'FFSR_DES': 'De días realmente pagados y SBC',                       'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': None,    'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': None, 'DEUSUARIO': ' ', 'COMENTARIO': ''},
    {'FFSR_REN': 545,  'FFSR_CLV': 'FSR_FSI',  'FFSR_DES': 'TP/TL',                                                'FFSR_FOR': 'FSR_DPA/FSR_DLA', 'MARCA1': True, 'MARCA2': None, 'MARCA3': True, 'MARCA4': True, 'FFSR_VAL': 1.3182, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Factor de Empresa'},
    {'FFSR_REN': 65,   'FFSR_CLV': 'BB',        'FFSR_DES': 'Jornada de trabajo: Diurna =0, mixta=1, nocturna=2',  'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 0.0,     'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': 0, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 61 LFT'},
    {'FFSR_REN': 67,   'FFSR_CLV': 'BC',        'FFSR_DES': 'Jornada de trabajo',                                   'FFSR_FOR': '', 'MARCA1': False, 'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 8.0,     'FFSR_UNI': 'horas',  'FFSR_IOP': None,  'DECIMALES': 2, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 61, 66 y 68 Ley Federal del Trabajo'},
    {'FFSR_REN': 455,  'FFSR_CLV': 'BD',        'FFSR_DES': 'Cantidad de horas extras por jornada',                 'FFSR_FOR': 'IIF(BB=0,BC-8,IIF(BB=1,BC-7.5,BC-7))', 'MARCA1': False, 'MARCA2': None, 'MARCA3': None, 'MARCA4': None, 'FFSR_VAL': 0.0, 'FFSR_UNI': 'horas', 'FFSR_IOP': None, 'DECIMALES': 4, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 61 LFT'},
    {'FFSR_REN': 460,  'FFSR_CLV': 'BE',        'FFSR_DES': 'Máximas horasextra dobles considerando 9horas/sem.',   'FFSR_FOR': 'IIF(BB=0,1.1875,IIF(BB=1,1.2,1.214286))', 'MARCA1': False, 'MARCA2': None, 'MARCA3': None, 'MARCA4': None, 'FFSR_VAL': 1.1875, 'FFSR_UNI': 'horas', 'FFSR_IOP': None, 'DECIMALES': 4, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 66 LFT'},
    {'FFSR_REN': 465,  'FFSR_CLV': 'BF',        'FFSR_DES': 'Cantidad de horas extras a pagar dobles',              'FFSR_FOR': 'IIF(BE>BD,BD,BE)', 'MARCA1': False, 'MARCA2': None, 'MARCA3': None, 'MARCA4': None, 'FFSR_VAL': 0.0, 'FFSR_UNI': 'horas/jor', 'FFSR_IOP': None, 'DECIMALES': 4, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 61 LFT'},
    {'FFSR_REN': 470,  'FFSR_CLV': 'BG',        'FFSR_DES': 'Cantidad de horas extras a pagar triples',             'FFSR_FOR': 'BD-BF', 'MARCA1': False, 'MARCA2': None, 'MARCA3': None, 'MARCA4': None, 'FFSR_VAL': 0.0, 'FFSR_UNI': 'horas/jor', 'FFSR_IOP': None, 'DECIMALES': 4, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 61 LFT'},
    {'FFSR_REN': 925,  'FFSR_CLV': '',          'FFSR_DES': 'De INFONAVIT y otras cuotas',                           'FFSR_FOR': '', 'MARCA1': True,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': None,    'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': ''},
    {'FFSR_REN': 1045, 'FFSR_CLV': 'BH',        'FFSR_DES': 'Ps(Tp/Tl)',                                            'FFSR_FOR': 'AQ*FSR_FSI', 'MARCA1': False, 'MARCA2': None, 'MARCA3': None, 'MARCA4': None, 'FFSR_VAL': 0.46092, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art.160 y 161 Reglamento de la Ley de Obra Pública y Servicios Relacionadas con las Mismas'},
    {'FFSR_REN': 655,  'FFSR_CLV': 'AS',        'FFSR_DES': 'Lím. prest. Inv., vida, cesantía y vejez, cant.',      'FFSR_FOR': 'IIF(AV=2003,20,IIF(AV=2004,21,IIF(AV=2005,22,IIF(AV=2006,23,IIF(( AV=2007 .AND.  AR=1),24,25)))))', 'MARCA1': None, 'MARCA2': None, 'MARCA3': None, 'MARCA4': None, 'FFSR_VAL': 25.0, 'FFSR_UNI': '', 'FFSR_IOP': None, 'DECIMALES': 5, 'DEUSUARIO': 'S', 'COMENTARIO': 'Art. 147 y 148 LSS'},
    {'FFSR_REN': 57,   'FFSR_CLV': 'AR',        'FFSR_DES': 'Semestre: enero a junio=1,  julio a diciembre=2',      'FFSR_FOR': '', 'MARCA1': None,  'MARCA2': None,  'MARCA3': None,  'MARCA4': None,  'FFSR_VAL': 1.0,     'FFSR_UNI': '',       'FFSR_IOP': None,  'DECIMALES': 0, 'DEUSUARIO': 'S', 'COMENTARIO': ''},
]

# ---------------------------------------------------------------------------
# CONFIG.INI template
# ---------------------------------------------------------------------------

CONFIG_INI_TEMPLATE = """\
[Explosión]
Recalcular=1
CalcExConSel=0,0,0,0,0,10,0,1,1,1,1,1,1,1,1,0,5,2
[Vista Actividades]
Recalcular=1
[Vista Suministros]
Recalcular=1
[Formato Vistas]
Archivo DFMV=C:\\OPUSCMS\\normal.FED
"""
