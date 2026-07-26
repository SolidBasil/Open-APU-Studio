# Graph Report - .  (2026-07-24)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2154 nodes · 4043 edges · 139 communities (120 shown, 19 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 311 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `97a2887f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ToolbarMixin
- NodoRepo
- latex.py
- Api
- DataService
- Database
- SidebarEstructura
- lector_dxf.py
- servidor.py
- RepoBase
- TablaInsumos
- cdx.py
- DialogoConfigImpresion
- backend/formulas.py
- ApiCliente
- VisorCadWidget
- Rutas
- DiagnosticoRepo
- ._http
- PanelesMixin
- Pt2
- importar.py
- TreeTableWidget
- GeneradorMixin
- InformesMixin
- _Delegate
- Exportador
- HistorialRepo
- Viewport3D
- icono
- GeneradorRepo
- auto_quantify.py
- undo_stack.py
- HandlersMixin
- InsumoDialog
- PestañaExplosion
- RecalculoRepo
- GestionProyectosMixin
- widgets/base.py
- TablaApuDetalle
- ValidationError
- schema.sql
- .recalcular_proyecto
- _BackendHTTP
- FiltroNombres
- VentanaPrincipal
- ApuMatricesRepo
- ventana.py
- TablaArbol
- ExplosionRepo
- EditarDescripcionDialog
- _TarjetaCheck
- PanelCapas
- DialogoSeleccionarInsumo
- QVBoxLayout
- DialogoAjustes
- ._header_context_menu_catalogo
- DialogoExplosion
- ApuMixin
- ._get_active_table
- ._show_all
- ._paste
- TablaGenerador
- Path
- .db_proyecto
- ._apply_layer_visibility
- CalibrationDialog
- mixins/generador.py
- toolbar.py
- ._build_generadores_lateral
- .keyPressEvent
- importar excel/importar_amazona.py
- Config
- ._open_sidebar_tab
- RastreoMixin
- ._cut
- _TarjetaRadio
- TablaExplosion
- ._abrir
- _TransactionContext
- export_canvas_to_pdf
- _num
- ._agregar_nodo
- ._focus_or_open_tab
- widgets/apu.py
- EventBus
- VariableFormulaRepo
- PresupuestoPopup
- ProjectDialog
- ._get_move_context
- .insumo_ids_con_apu
- .apu_actualizar_valor
- busqueda_texto.py
- _ExploradorTree
- ._celdas
- ._apply_column_modes
- WebSocketClient
- ConnectionManager
- IndirectoRepo
- dialogs.py
- ._fit_transform
- ._obtener_o_crear_generador
- .filter_rows
- ._abrir_indirectos_dlg
- _fmt
- ._build_col_calculo
- .insert
- .guardar
- ._build_col_tipos
- SchemaRegistry
- .insumo_actualizar_precio
- .insumo_actualizar_descripcion
- ._on_abrir_proyecto
- ._on_nuevo_insumo_panel
- _editable_cols_arbol
- .poblar
- ._collect_expanded_ids
- draw_tree_connectors
- opencode.json
- ._on_desplegar_nivel
- .insumos_sin_uso
- backend/__init__.py
- frontend/__init__.py
- .set_entities
- ._on_gen_total_actualizado
- mixins/__init__.py
- ._on_copy_toolbar
- ._prev_tab
- QLabel
- QMenu
- QTreeWidget

## God Nodes (most connected - your core abstractions)
1. `Api` - 91 edges
2. `TreeTableWidget` - 89 edges
3. `HandlersMixin` - 58 edges
4. `DataService` - 57 edges
5. `NodoRepo` - 55 edges
6. `ProyectoRecalculado` - 53 edges
7. `icono()` - 45 edges
8. `RecalculoRepo` - 43 edges
9. `GeneradorMixin` - 43 edges
10. `VisorCadWidget` - 42 edges

## Surprising Connections (you probably didn't know these)
- `buscar_insumo_hash()` --calls--> `generar_hash()`  [INFERRED]
  server/servidor.py → backend/database/core.py
- `DiagDialogsMixin` --uses--> `Rutas`  [INFERRED]
  frontend/ventana/mixins/diag_dialogs.py → backend/database/db.py
- `GeneradorMixin` --uses--> `Rutas`  [INFERRED]
  frontend/ventana/mixins/generador.py → backend/database/db.py
- `GestionProyectosMixin` --uses--> `Rutas`  [INFERRED]
  frontend/ventana/mixins/gestion_proyectos.py → backend/database/db.py
- `InformesMixin` --uses--> `Rutas`  [INFERRED]
  frontend/ventana/mixins/informes.py → backend/database/db.py

## Import Cycles
- None detected.

## Communities (139 total, 19 thin omitted)

### Community 0 - "ToolbarMixin"
Cohesion: 0.05
Nodes (25): QWidget, Mixin de toolbar — se mezcla en VentanaPrincipal.      Nota: `self` siempre es, Crea fila de botones de pestañas (PROYECTO, INICIO, …, HERRAMIENTAS) conmutables, Crea barra de búsqueda con QLineEdit y menú contextual de columnas., Menú contextual de la barra de búsqueda: checkboxes por columna.         Solo m, Activa/desactiva una columna del filtro de búsqueda., Crea el QStackedWidget y reserva una página vacía por cada tab en _TOOLBAR_CFG., Construye (una sola vez) la página de toolbar para tab_name. (+17 more)

### Community 1 - "NodoRepo"
Cohesion: 0.04
Nodes (30): NodoRepo, Recalcula wbs y nivel de TODO el árbol del proyecto en una sola         pasada,, Acceso a estructura_presupuesto: capítulos y conceptos del presupuesto.     El á, Siguiente valor de 'orden' libre entre los hijos activos de         padre_id (o, Abre un hueco de 'hueco' posiciones justo DESPUÉS de         orden_referencia en, Calcula el nuevo orden de una lista de hermanos tras mover un         subconjunt, Devuelve todos los nodos activos del presupuesto (es_extra=0 por defecto)., Ids de los hermanos activos de padre_id, ordenados (orden, id)         — mismo c (+22 more)

### Community 2 - "latex.py"
Cohesion: 0.06
Nodes (36): _ancho_tabla_cm(), _anchos_a_cm(), _aplanar_a_arbol(), _build_conceptos(), _campo_nivel(), _campo_precio_unitario(), _campo_total(), escape_tex() (+28 more)

### Community 3 - "Api"
Cohesion: 0.04
Nodes (23): Api, Guarda los factores, calcula factor_total y recalcula en cascada.         Devue, Lista indirectos del proyecto, opcionalmente filtrados por tipo., Actualiza un indirecto existente., Inserta un indirecto nuevo. Devuelve el id., Elimina (soft-delete) un indirecto., Recalcula el campo 'total' de todos los indirectos del proyecto., Carga items de plantilla que no existan ya. Devuelve cuántos insertó. (+15 more)

### Community 4 - "DataService"
Cohesion: 0.10
Nodes (32): ApuComponenteActualizado, ConceptoActualizado, Evento, FactoresSobrecostoActualizados, GeneradorActualizado, InsumoActualizado, NodoEliminado, NodoInsertado (+24 more)

### Community 5 - "Database"
Cohesion: 0.08
Nodes (26): Database, db.py ===== Gestión de la conexión SQLite, carpeta de datos del usuario y aplica, Gestiona la conexión SQLite activa de un proyecto.      Cada instancia controla, Ruta del archivo .db abierto (solo lectura)., FamiliaRepo, Devuelve todas las familias activas ordenadas por nombre., Busca una familia por su ID., Devuelve las subfamilias activas de una familia. (+18 more)

### Community 6 - "SidebarEstructura"
Cohesion: 0.08
Nodes (29): _a_numero(), cargar_hoja(), CH(), Col, eliminar_fila(), guardar_fila(), HojaBinding, Connection (+21 more)

### Community 7 - "lector_dxf.py"
Cohesion: 0.09
Nodes (38): _build_aci_table(), _compute_extents(), _detect_units(), _dispatch_entity(), DxfEntity, DxfLayer, DxfParseResult, _edge_path_vertices() (+30 more)

### Community 8 - "servidor.py"
Cohesion: 0.07
Nodes (29): InsumoRepo, Conjunto de ids de insumos compuestos (tienen APU propio)., Actualiza unidad para múltiples insumos en un solo execute.         cambios: lis, Devuelve todos los insumos activos de un proyecto con sus joins.         Orden:, Devuelve los insumos de un tipo específico (clave textual).         Orden: básic, Busca un insumo por su ID., Busca un insumo por su hash dentro de un proyecto.         Útil para detectar du, Catálogo de insumos del proyecto: materiales, MO, equipo, etc.     JOIN con tipo (+21 more)

### Community 9 - "RepoBase"
Cohesion: 0.08
Nodes (20): apu.py Repositorios de matrices APU — subtotales se calculan al vuelo., base.py ======= Clase base para todos los repositorios — Open APU Studio.  Escri, Inicializa el repositorio.          Acepta Database (nuevo) o conn (legacy, depr, SELECT → primera fila como dict, o None., SELECT → lista de dicts., SELECT genérico por id usando self.TABLA. Los repos específicos         pueden s, Soft-delete genérico. No hace commit., RepoBase (+12 more)

### Community 10 - "TablaInsumos"
Cohesion: 0.08
Nodes (20): _num_opcional(), Formatea un número que puede ser NULL. NULL -> '' (no '0.00', que     daría a e, Tabla plana del catálogo de insumos (sin jerarquía)., paste_col_fn de la columna Tipo (4): el texto pegado debe         coincidir (si, paste_col_fn de la columna Familia (5): busca por nombre entre         las fami, Crea un insumo nuevo cuando el pegado trae más filas de las que         hay en, Construye los valores de columna para un insumo. Compartido por         poblar(, Pinta el icono SVG real (Lucide) de la columna Tipo — reemplaza         el viej (+12 more)

### Community 11 - "cdx.py"
Cohesion: 0.09
Nodes (32): _bits_for(), build_btree(), build_compact_leaf(), build_interior(), CdxBuilder, _ceil_div(), _clamp(), _empty_tag_tree() (+24 more)

### Community 12 - "DialogoConfigImpresion"
Cohesion: 0.10
Nodes (15): Abre el diálogo de configuración de impresión (márgenes,         orientación y a, PersonalizarColumnasDialog, QDialog, Agrupa las columnas por categoría preservando el orden de aparición         en, Filtra filas por nombre de columna; oculta categorías vacías., Diálogo genérico: elegir qué columnas son favoritas (aparecen en el     menú rá, Persiste el set de favoritas. No-op si la tabla no define _CATALOGO_KEY., DialogoConfigImpresion (+7 more)

### Community 13 - "backend/formulas.py"
Cohesion: 0.12
Nodes (27): _envolver_math(), ErrorFormula, EvalDecimal, evaluar_formula(), _mensaje_error(), nombres_referenciados(), _normalizar(), Exception (+19 more)

### Community 14 - "ApiCliente"
Cohesion: 0.11
Nodes (4): ApiCliente, Any, api_cliente.py ============== Cliente HTTP para el servidor de Open APU Studio., Cliente HTTP delgado que replica la interfaz de api.py.      Args:         base_

### Community 15 - "VisorCadWidget"
Cohesion: 0.12
Nodes (10): Mueve los items de preview a la lista persistente (sobreviven al zoom/pan)., Elimina los items de medición persistentes de la escena., Cierra el polígono y muestra área + perímetro., Visor CAD con pan, zoom, capas y herramientas de medición.      Rendering delega, VisorCadWidget, QGraphicsItem, QGraphicsView, QMouseEvent (+2 more)

### Community 16 - "Rutas"
Cohesion: 0.11
Nodes (30): Centraliza todas las rutas de datos del usuario.     Crea las carpetas si no exi, Rutas, DataServiceError, Exception, Base para errores del servicio de datos., Error en operación de repositorio (SQL, integridad, etc.)., RepositoryError, Any (+22 more)

### Community 17 - "DiagnosticoRepo"
Cohesion: 0.07
Nodes (17): DiagnosticoRepo, Insumos cuya unidad es un alias (case o abreviatura) de una estándar., Conteos básicos del proyecto para el diálogo de información., Insumos cuyo hash no coincide con el hash generado desde su descripción., Aplica una lista de (id, desc, old_hash, new_hash) como UPDATE batch., Nodos del presupuesto cuyo padre_id apunta a un id que no existe., Capítulos cuyo total no coincide (±$1) con la suma de sus hijos directos., Componentes APU con valor = 0 (cantidad cero). (+9 more)

### Community 18 - "._http"
Cohesion: 0.06
Nodes (16): Devuelve el cliente HTTP, arrancando el servidor bajo demanda., Deshace la última operación del usuario (SRV-10)., Rehace la última operación deshecha (SRV-10)., Devuelve el árbol del presupuesto (es_extra=0) o extra (es_extra=1)., Devuelve el total de un nodo del presupuesto., Actualiza la descripción de un agrupador (capítulo)., Devuelve los ids de todos los conceptos activos del proyecto., Lista plana de todos los conceptos con clave, descripción, unidad, cantidad, tot (+8 more)

### Community 19 - "PanelesMixin"
Cohesion: 0.08
Nodes (17): PanelesMixin, QWidget, Crea el QTabWidget central., Construye el árbol jerárquico del presupuesto., Árbol de conceptos fuera de presupuesto (es_extra=1)., Suma de totales de nodos raíz (es_extra=0|1)., Agrega agrupador en el árbol extra., Agrega concepto en el árbol extra. (+9 more)

### Community 20 - "Pt2"
Cohesion: 0.12
Nodes (28): aggregate_entities(), GroupAggregate, agregacion.py ============= Agregación de mediciones para selecciones múltiples, Σ measurements para un grupo de entidades.      Reglas:       - LWPOLYLINE cerra, calculate_area(), calculate_distance(), calculate_perimeter(), format_measurement() (+20 more)

### Community 21 - "importar.py"
Cohesion: 0.11
Nodes (27): generar_hash(), core.py ======= Lógica de negocio pura para Open APU Studio. No sabe nada de pre, Genera un hash corto y estable a partir de la descripción de un insumo.      Nor, _arbol_clasico(), _arbol_numerico(), _detectar(), _f(), importar() (+19 more)

### Community 22 - "TreeTableWidget"
Cohesion: 0.09
Nodes (13): Columnas que pueden incluirse en la búsqueda: (índice, etiqueta).         Se us, Columnas donde se filtra. None = buscar en todas., Cambia las columnas de búsqueda. None = buscar en todas., Genera clave de orden según posición en el árbol (índices desde raíz)., Aplica el estilo estándar (cursiva, gris) a una fila placeholder         tipo ", Suscribe este widget al EventBus del proyecto abierto según         EVENTOS_SUS, Retira las suscripciones hechas por conectar_eventos().         Idempotente: no, Índices de columna marcados como imprimibles (se incluyen en el         reporte (+5 more)

### Community 23 - "GeneradorMixin"
Cohesion: 0.09
Nodes (11): GeneradorMixin, Vuelve a mostrar el árbol del presupuesto., Mixin de generadores de obra — se mezcla en VentanaPrincipal., Abre un archivo DXF y lo carga en el visor., Cambia la herramienta activa del visor CAD., Inicia el flujo de calibración de dos clics., Ajusta la vista para mostrar todas las entidades., Maneja clics en el visor CAD (referencia visual / medición). (+3 more)

### Community 24 - "InformesMixin"
Cohesion: 0.11
Nodes (19): Carpeta donde se guardan los .tex y .pdf generados., compilar_pdf(), Path, Reemplaza todos los marcadores <<campo>> con los valores de `datos`., Ejecuta pdflatex (2 pasadas) sobre un .tex existente.     Retorna ruta al .pdf o, Genera el presupuesto en .tex y/o .pdf.      Uso desde handlers.py (flujo origin, Renderiza la plantilla y escribe el .tex en filepath., Genera el .tex y (por defecto) compila a .pdf. Retorna ruta del archivo. (+11 more)

### Community 25 - "_Delegate"
Cohesion: 0.10
Nodes (14): _Delegate, Delegado que controla qué celda es editable según columna y, opcionalmente,, Devuelve el set de columnas editables para un item concreto., Pinta la celda normal y, si su fila está en corte pendiente,         agrega un, Dibuja el borde punteado de corte pendiente para (item, columna)         si cor, Crea editor solo si la celda es editable para ese tipo de nodo., Cierra popup primero, luego confirma y cierra el editor., Cierra el editor QComboBox confirmando el valor seleccionado. (+6 more)

### Community 26 - "Exportador"
Cohesion: 0.16
Nodes (6): Exportador, Path, Exporta un proyecto SQLite al formato de carpeta de obra OPUS 2010., Crea DBF + CDX. cdx_sufijo=None → sin CDX; '' → CDX con clave ''., Ajusta cabecera DBF para compatibilidad OPUS: versión 0x03, lang=0x00., Genera el .CDX usando cdx.make_cdx con los tags definidos en _CDX_TAGS.

### Community 27 - "HistorialRepo"
Cohesion: 0.08
Nodes (13): HistorialRepo, Lee el valor actual de un campo específico de una tabla., Registra un cambio en historial. Llamar ANTES del commit.          sesion: UUID, Devuelve la sesion UUID del último cambio NO deshecho de este usuario., Devuelve la sesion UUID del PRIMER cambio deshecho (FIFO: primero deshecho = pri, Marca una sesión como deshecha (para poder rehacerla después)., Des-marca una sesión deshecha (al rehacerla)., Borra sesiones deshechas (nueva escritura invalida el redo stack). (+5 more)

### Community 28 - "Viewport3D"
Cohesion: 0.13
Nodes (13): QWidget, viewport3d.py — Viewport 3D para modelos estructurales =========================, Superpone la forma deformada (escalada) sobre la geometría original.          Ar, Diagrama genérico de fuerza interna sobre la estructura.          Dibuja polilín, Dibuja las reacciones de apoyo como flechas en los nudos restringidos., Guarda una captura de la vista 3D actual (PNG/JPG) en `ruta`.          Returns:, Dibuja elementos estructurales como tubos 3D.          Args:             element, Dibuja nodos como esferas, con apoyos en color distinto.          Args: (+5 more)

### Community 29 - "icono"
Cohesion: 0.15
Nodes (19): _colored_icon(), _fallback_icon(), get_default_tint(), icono(), QIcon, iconos.py ========= Registry central de iconos SVG.  Soporta dos conjuntos:   -, Retorna el tint por defecto actual., Resuelve la ruta del SVG según el conjunto activo.      Retorna (ruta, set_real) (+11 more)

### Community 30 - "GeneradorRepo"
Cohesion: 0.10
Nodes (8): GeneradorRepo, Any, Devuelve los concepto_id que cambian al reasignar un generador:         el viejo, Generadores vinculados a un concepto, o sueltos si concepto_id es None., subtotal = veces × (largo o 1) × (ancho o 1) × (alto o 1), Recalcula generadores.cantidad_total = SUM(subtotal) de renglones activos., Recalcula estructura_presupuesto.cantidad = SUM(cantidad_total) de         todos, Generadores vinculados a un concepto, o sueltos si concepto_id es None.

### Community 31 - "auto_quantify.py"
Cohesion: 0.13
Nodes (19): _arc_sweep(), _ellipse_radii(), LayerQuantity, _pick_primary(), quantify_by_layer(), quantity_for(), auto_quantify.py ================ Cuantificación automática por capa de entidade, Cantidad de una capa bajo una medida explícita. (+11 more)

### Community 32 - "undo_stack.py"
Cohesion: 0.17
Nodes (17): AnnotationSnapshot, can_redo(), can_undo(), empty_undo_state(), pop_redo(), pop_undo(), push_undo(), undo_stack.py ============= Pila de undo/redo lineal para mutaciones de anotacio (+9 more)

### Community 33 - "HandlersMixin"
Cohesion: 0.10
Nodes (11): HandlersMixin, Colapsa el árbol del widget activo mostrando solo las raíces., Colapsa el árbol mostrando solo los agrupadores., Expande completamente el árbol del widget activo., Mixin de handlers — se mezcla en VentanaPrincipal.      Nota: `self` siempre e, Avanza a la siguiente pestaña cíclicamente., Alterna entre pantalla completa y el modo anterior.          showNormal() por, Agrupa los QTreeWidgetItem seleccionados por el id de su padre         real (No (+3 more)

### Community 34 - "InsumoDialog"
Cohesion: 0.13
Nodes (9): InsumoDialog, _parse_float(), Convierte texto a float o None si es cero., Diálogo para crear o editar un insumo.      Uso (crear):         dlg = InsumoDia, Pre-puebla los campos desde la BD (modo edición)., Recarga subfamilias al cambiar la familia seleccionada., Habilita/deshabilita los campos de precio según es_compuesto., Muestra advertencia si la unidad no está en el catálogo estándar. (+1 more)

### Community 35 - "PestañaExplosion"
Cohesion: 0.12
Nodes (11): Construye y muestra la pestaña de explosión de insumos., PestañaExplosion, Pestaña completa: encabezado informativo + TablaExplosion., Pestaña completa: encabezado + tabla + conexiones a APU y rastreo., Doble clic en fila -> abre APU del insumo, ignorando subtotales y total., Menú contextual -> Copiar/Cortar/Pegar + Rastrear uso para el insumo bajo el cur, Encabezado con nivel, cantidad de conceptos y tipos seleccionados., Delega copia al portapapeles a la tabla interna. (+3 more)

### Community 36 - "RecalculoRepo"
Cohesion: 0.15
Nodes (10): Calcula el resumen de un APU específico al vuelo (para UI/exportar)., Calcula todos los resúmenes del proyecto en memoria., Copia insumos.costo_directo → apu_matrices.precio, aplicando         factor_fsr, Calcula subtotales por tipo de costo para todas las matrices del         proyect, Recalcula en cascada todo el presupuesto de un proyecto:          1. Sincroniza, Copia el costo_directo del resumen de cada insumo compuesto a su         costo_f, Aplica FSR y sobrecostos: costo_final = costo_directo * factor_fsr * factor_tota, Totales de conceptos = cantidad × costo_final del insumo vinculado.          Reu (+2 more)

### Community 37 - "GestionProyectosMixin"
Cohesion: 0.15
Nodes (10): GestionProyectosMixin, Detiene el servidor embebido y el cliente WS (SRV-13)., Ensambla EventBus → RepositoryRegistry → DataService → Api para         el proye, Mixin de lifecycle de proyectos — se mezcla en VentanaPrincipal., Devuelve la URL del servidor, arrancándolo bajo demanda (lazy)., Abre formulario vacío; al guardar se crea el .db con el nombre indicado., Cierra el proyecto actual con confirmación., Arranca el cliente WebSocket para recibir eventos en vivo (SRV-05). (+2 more)

### Community 38 - "widgets/base.py"
Cohesion: 0.15
Nodes (15): ajustes.py ========== Diálogo de configuración general de Open APU Studio.  Secc, crear_footer_dialogo(), crear_header_dialogo(), _limpiar_celda_excel(), _menu_icon(), _parsear_portapapeles(), QFrame, base.py ======= Widget base reutilizable: TreeTableWidget con conectores visua (+7 more)

### Community 39 - "TablaApuDetalle"
Cohesion: 0.13
Nodes (9): Árbol de componentes de un APU (concepto o insumo compuesto).      A diferenci, Repuebla filas + total desde un resultado ya consultado         (api.apu()), pr, Vuelve a consultar la fuente de verdad y repuebla. Solo tiene         efecto un, Refresco compartido para ApuComponenteActualizado, InsumoActualizado         y, Muestra solo filas cuyo tipo_id coincide; si tipo_id es None, muestra todas., Doble clic: Descripción → selector de insumo (como en presupuesto); P.U. → sub-A, Persiste edición: Precio (col 4), Operador (col 5) o Valor como fórmula (col 6)., Revierte el texto de un item al valor real de la DB tras error de validación. (+1 more)

### Community 40 - "ValidationError"
Cohesion: 0.17
Nodes (8): exceptions.py ============= Excepciones propias de la capa de datos de Open APU, Validación de SchemaRegistry fallida., ValidationError, BoolField, FloatField, IntField, schema_registry.py ================== Sistema de validación por tipos de campo,, StringField

### Community 41 - "schema.sql"
Cohesion: 0.27
Nodes (17): apu_matrices, estructura_presupuesto, factores_fsr, factores_sobrecosto, familias, generador_renglones, generadores, historial (+9 more)

### Community 42 - ".recalcular_proyecto"
Cohesion: 0.11
Nodes (9): Reasigna un concepto a otro insumo del catálogo.          Cambia el insumo_id, Elimina (soft-delete) un nodo del presupuesto y recalcula en cascada., Inserta un nodo nuevo en el presupuesto (o extra) y recalcula.          Args:, Actualiza el operador (* o /) de un componente APU y recalcula en cascada., Inserta un nuevo componente en el APU de una matriz y recalcula., Reasigna el insumo de un componente dentro de un APU.          Cambia el insum, Recalcula en cascada todo el presupuesto del proyecto abierto:         costo de, Actualiza costo_mn y costo_me de un insumo y recalcula en cascada.          co (+1 more)

### Community 43 - "_BackendHTTP"
Cohesion: 0.12
Nodes (6): _BackendHTTP, _BackendLocal, Implementación local (SQLite directo vía DataService/repos)., Implementación vía servidor embebido (ApiCliente)., Connection, Path

### Community 44 - "FiltroNombres"
Cohesion: 0.15
Nodes (9): entity_display_name(), FiltroNombres, QWidget, filtro_nombres.py ================= Filtro de nombres de entidades para el visor, Rebuild name groups from entities., Nombre legible de una entidad para el filtro., Filtro de nombres de entidades., Path (+1 more)

### Community 45 - "VentanaPrincipal"
Cohesion: 0.17
Nodes (9): Lee valor de configuración por clave; devuelve default si no existe., Ventana principal de Open APU Studio.      La lógica está distribuida en mixins:, Ensambla el layout vertical: tab bar + toolbar + splitter (sidebar | contenido)., VentanaPrincipal, main(), main.py ======= Punto de entrada de Open APU Studio., Punto de entrada: inicializa QApplication, aplica tema, crea y muestra la ventan, QApplication (+1 more)

### Community 46 - "ApuMatricesRepo"
Cohesion: 0.12
Nodes (9): ApuMatricesRepo, Resuelve proyecto_id desde matriz_id (positivo=árbol, negativo=compuesto)., Devuelve los componentes del APU de una matriz (concepto o compuesto)., Conceptos del árbol cuyo insumo es compuesto (es_compuesto=1)., Filas en apu_matrices para un matriz_id dado., Mueve todos los componentes de apu_matrices de origen a destino., Borra todos los componentes de apu_matrices de un matriz_id., Devuelve el APU completo de una matriz (concepto o insumo compuesto):         co (+1 more)

### Community 47 - "ventana.py"
Cohesion: 0.14
Nodes (9): apu_mixins.py ============= Mixin de pestañas APU: desglose, edición inline, nav, ExplosionMixin, explosion_mixins.py ==================== Mixin de explosión de insumos, explosió, Mixin de explosión — se mezcla en VentanaPrincipal., Agrega una fila de componente APU al árbol., Pestaña de factores de sobrecosto del proyecto., Guarda los factores, recalcula y refresca el presupuesto., Construye árbol expandible con APU de cada concepto.          Sin conectores jer (+1 more)

### Community 48 - "TablaArbol"
Cohesion: 0.12
Nodes (9): Árbol jerárquico del presupuesto.     Capítulos se muestran con color según niv, Columnas imprimibles en orden visual + ancho actual, traducidas a         los no, Click en la fila vacía final → crea un concepto nuevo., Conecta las señales estándar de este árbol a los métodos de         `target` que, IDs de concepto (estructura_presupuesto) implicados en la         selección act, IDs (estructura_presupuesto) de las filas seleccionadas en el         árbol tal, Restaura expansión: expande los que estaban abiertos, colapsa los demás., TablaArbol (+1 more)

### Community 49 - "ExplosionRepo"
Cohesion: 0.18
Nodes (10): ExplosionRepo, _parse_unidad_pct(), explosion.py Repositorio de explosión de insumos (tres niveles de cálculo)., Retorna (es_porcentaje, sufijo, tipo_id_destino).      Si unidad empieza con '(%, Calcula la explosión de insumos para un conjunto de conceptos.      Niveles:, Niveles 'primer_nivel' o 'compuesto': resuelve por SQL agregado., Devuelve (filas, total_global).         filas — lista de dicts con tipo_id, tipo, Cantidad efectiva desde una fila de apu_matrices.          Si operador='*' → la (+2 more)

### Community 50 - "EditarDescripcionDialog"
Cohesion: 0.13
Nodes (10): EditarDescripcionDialog, EditarPrecioDialog, QDialog, Diálogo modal para editar la descripción de un insumo.      Muestra la descripci, Actualiza el label de preview del hash en tiempo real., Valida que el campo no esté vacío antes de aceptar., Devuelve la descripción ingresada por el usuario., Diálogo modal para editar el precio de un insumo.      Uso:         dlg = Editar (+2 more)

### Community 51 - "_TarjetaCheck"
Cohesion: 0.13
Nodes (9): Devuelve el valor asociado a esta tarjeta (nivel de cálculo)., Fila simple: QCheckBox + icono + nombre, sin bordes extra., Fila con QCheckBox + icono + nombre para filtrar por tipo de insumo., ID del tipo de insumo (1=Materiales, 2=MO, 4=Herramienta, ...)., True si el checkbox está marcado., Alterna el checkbox al hacer clic en el widget completo., Alterna entre seleccionar/deseleccionar todos los tipos y actualiza texto del bo, Valida selección (mínimo 1 tipo), captura nivel y tipos_ids, y acepta el diálogo (+1 more)

### Community 52 - "PanelCapas"
Cohesion: 0.20
Nodes (6): _color_icon(), PanelCapas, QIcon, QWidget, panel_capas.py ============== Selector de capas del visor CAD, como dropdown com, Selector de capas en formato dropdown, con filtro y toggles.

### Community 53 - "DialogoSeleccionarInsumo"
Cohesion: 0.21
Nodes (6): Selecciona insumo y lo agrega como componente al APU., DialogoSeleccionarInsumo, Diálogo modal para buscar y seleccionar un insumo del catálogo.      Tiene barra, Carga todos los insumos del proyecto en la tabla., Abre el diálogo de nuevo insumo; recarga la lista si se creó uno., Abre el diálogo de edición para el insumo seleccionado.

### Community 54 - "QVBoxLayout"
Cohesion: 0.19
Nodes (6): DiagDialogsMixin, diag_dialogs.py ================ Mixin de diálogos de diagnóstico: depurar catál, Mixin de diagnóstico — se mezcla en VentanaPrincipal., Recalcula en cascada todo el presupuesto., Abre popup de cálculo de sobrecostos., QVBoxLayout

### Community 55 - "DialogoAjustes"
Cohesion: 0.31
Nodes (5): DialogoAjustes, QDialog, QFrame, QWidget, Ventana de configuración general de la aplicación.

### Community 56 - "._header_context_menu_catalogo"
Cohesion: 0.17
Nodes (6): Hook: subclases agregan acciones extra al menú contextual., Guarda estado del header en config.json como base64., Índices de columna marcados como favoritos (aparecen en el menú         rápido), Menú contextual sobre cabecera para mostrar/ocultar columnas.          Si la t, Al ocultar una columna, la saca de _search_cols para que la         búsqueda no, QMenu

### Community 57 - "DialogoExplosion"
Cohesion: 0.18
Nodes (11): DialogoExplosion, QDialog, QFrame, QWidget, Línea vertical separadora para layouts de dos columnas., Ventana de configuración de la explosión de insumos.      Layout de dos columnas, Diálogo modal para elegir nivel de desglose y tipos de insumo a explotar., Ensambla layout vertical: banner + dos columnas + pie. (+3 more)

### Community 58 - "ApuMixin"
Cohesion: 0.20
Nodes (8): ApuMixin, Mixin de APU — se mezcla en VentanaPrincipal., Doble clic en el árbol de presupuesto.          Col 7 (P.U.) → abre APU del conc, Pestaña de desglose APU: componentes de un concepto o insumo compuesto., Abre el APU de un concepto del árbol de presupuesto., Detecta si la columna contiene 'PU' o 'PRECIO'., Abre el APU de un insumo compuesto del catálogo., Punto único que arma o enfoca la pestaña de un APU ya resuelto.          Si ya h

### Community 59 - "._get_active_table"
Cohesion: 0.14
Nodes (7): Retorna el TreeTableWidget activo o None., Menú contextual con checkboxes de columnas visibles., Restaura anchos y visibilidad de columnas a sus valores por defecto., Elimina los elementos seleccionados (nodos del árbol o filas de insumos)., Selecciona todas las filas visibles del widget activo., Activa edición en la celda actual (equivalente a F2)., Abre APU del ítem seleccionado (equivalente a doble clic en P.U.).

### Community 60 - "._show_all"
Cohesion: 0.14
Nodes (7): Muestra todos los items (quita cualquier ocultación) recursivamente., Colapsa todo mostrando solo el primer nivel (raíces)., Muestra solo nodos con hijos (agrupadores), oculta hojas., Muestra todos los nodos expandidos completamente., Expande items hasta profundidad N (recorrido manual del árbol).         depth=0, Expande item y sus hijos recursivamente hasta max_depth.         Reemplaza a ex, Recursivamente oculta nodos hoja (sin hijos).

### Community 61 - "._paste"
Cohesion: 0.19
Nodes (7): True si item es la fila placeholder de 'agregar nueva fila'         (marcada co, Columnas editables para un item concreto — respeta editable_cols_fn         cua, Si hay un corte pendiente activo (de esta tabla o de otra), lo         consume:, Pega el contenido del portapapeles en la celda actual.          Si el texto es, Escribe un valor pegado en (item, col), usando el resolver de         paste_col, Hook: las subclases lo implementan para crear una fila real (vía         Api, i, Escribe una cuadrícula de valores empezando en (item_inicial,         col_inici

### Community 62 - "TablaGenerador"
Cohesion: 0.15
Nodes (6): generador.py ============ Tabla de renglones de un generador de obra.  Hereda Tr, Persiste edición inline de renglones., Escribe un valor medido en el CAD dentro de la celda actualmente         selecci, Tabla editable de renglones de un generador de obra., Llena la tabla con renglones del generador.         Si seleccionar_id se omite,, TablaGenerador

### Community 63 - "Path"
Cohesion: 0.17
Nodes (9): _copiar_plantillas_incluidas(), Path, Guarda el nombre del último proyecto abierto., Copia las plantillas .tex incluidas en el proyecto a la carpeta del usuario., Carpeta raíz de datos del usuario., Carpeta de logs de importación y errores., Carpeta donde se almacenan las plantillas LaTeX del usuario.         En primera, _cargar_plantilla() (+1 more)

### Community 64 - ".db_proyecto"
Cohesion: 0.18
Nodes (6): Devuelve la lista de archivos .db disponibles, ordenados por fecha., Devuelve la ruta al .db de un proyecto dado su nombre.         Ejemplo: Rutas.db, Devuelve la ruta al último proyecto abierto, o None si no existe., Carpeta donde se guardan los archivos .db de proyectos., Duplica un proyecto existente., Elimina permanentemente un proyecto .db con doble confirmación.

### Community 65 - "._apply_layer_visibility"
Cohesion: 0.17
Nodes (5): Drawing, Carga un documento DXF usando ezdxf para rendering nativo., Re-renderiza la escena completa usando ezdxf (una sola vez)., Capa efectiva de un item de la escena, usando las referencias a         la entid, Aplica self._visible_layers sobre los items ya renderizados,         sin volver

### Community 66 - "CalibrationDialog"
Cohesion: 0.17
Nodes (7): CalibrationDialog, QDialog, calibracion.py ============== Diálogo de calibración de escala de dos clics.  El, Valida y emite la calibración., Devuelve (units_per_pixel, unit) después de accept., Diálogo de calibración de escala para el visor CAD., Muestra preview del factor de escala.

### Community 67 - "mixins/generador.py"
Cohesion: 0.18
Nodes (10): ortho.py ======== Ángulo de bloqueo a 45° para dibujo con Shift presionado.  Cua, Snap cursor al rayo 45° más cercano desde anchor.      Preserva la distancia raw, Retorna el ángulo snapped en grados [-180, 180]., snap_angle_degrees(), snap_to_ortho(), CadTool, visor.py ======== Visor CAD basado en QGraphicsView/QGraphicsScene.  Rendering d, generador.py ============ Mixin de generadores de obra para VentanaPrincipal.  P (+2 more)

### Community 68 - "toolbar.py"
Cohesion: 0.17
Nodes (10): get_iconos(), Cambiar conjunto activo ('lucide' o 'icons8')., Retorna el conjunto activo., Cambiar el tint por defecto (ej. '#1A1F24' para modo claro)., QWidget con icono de búsqueda + QLineEdit + clear button., search_input(), set_default_tint(), set_iconos() (+2 more)

### Community 69 - "._build_generadores_lateral"
Cohesion: 0.18
Nodes (7): QWidget, Panel de renglones directos (sin capa de generadores)., Repobla el árbol del presupuesto., Construye el panel del visor CAD (sin side panel derecho)., Panel lateral para la sección Generadores:         QStackedWidget con idx 0 = ár, Aplica formato compacto al árbol: ocultar columnas, anchos, word wrap., Construye el contenido de la pestaña Generadores: solo el visor CAD.

### Community 70 - ".keyPressEvent"
Cohesion: 0.13
Nodes (7): Selecciona solo los ítems visibles (respeta filtros activos).         Qt nativo, Captura Ctrl+C/X/V/A/Z/Y, navegación de columnas con Izq/Der y         expandir, Índices de columnas visibles, en orden, respetando columnas ocultas         por, Mueve el foco de celda a la columna visible anterior (-1) o siguiente (+1),, Espacio: alterna expandir/colapsar el ítem actual (reemplaza el uso         nat, Ctrl+Z: delega al handler de la ventana principal., Esc: cancela el corte pendiente de esta tabla, si lo hay.

### Community 71 - "importar excel/importar_amazona.py"
Cohesion: 0.24
Nodes (12): aplicar_schema(), calcular_nivel(), importar_catalogo(), importar_generadores(), main(), obtener_o_crear_insumo_compuesto(), Importa CATALOGO_DE_CONCEPTOS_AMPLIACIÓN_AMAZONA_VINCULADO_1.xlsx a un proyecto, Lee hoja 'Generadores' y crea generadores + renglones. (+4 more)

### Community 72 - "Config"
Cohesion: 0.23
Nodes (7): Config, Lee y escribe preferencias en config.json.     Valores disponibles: tema_modo, t, Carga config.json desde disco al caché de clase; retorna dict vacío si no existe, Persiste par clave/valor en config.json y actualiza el caché., Ruta al archivo de configuración de la app., temas.py ======== Gestión de temas visuales: modo (oscuro/claro) + acento (azul/, Temas

### Community 73 - "._open_sidebar_tab"
Cohesion: 0.17
Nodes (6): Widget placeholder con icono + título + mensaje., Abre pestaña según título del sidebar., Cierra la pestaña en el índice dado., Quita la pestaña en `idx`, guardando estado de columnas y         desconectando, Auto-ajusta ancho de columnas al contenido (solo si no hay estado guardado)., Recarga la pestaña de presupuesto con los datos nuevos.

### Community 74 - "RastreoMixin"
Cohesion: 0.23
Nodes (7): RastreoMixin, rastreo_mixins.py ================== Mixin de rastreo de insumos: buscar uso, ta, Abre el APU de una fila de rastreo., Menú contextual sobre tablas de APU y rastreo., Mixin de rastreo — se mezcla en VentanaPrincipal., Busca insumo por id y abre pestaña con todas las matrices donde se usa., Construye pestaña de rastreo con resumen del insumo y tabla de uso.

### Community 75 - "._cut"
Cohesion: 0.21
Nodes (8): _cancelar_corte_activo(), Copy selected rows as TSV (tab-separated values) to clipboard.         Returns, Copia selección al portapapeles como TSV; si no hay selección copia celda actual, Corta: copia la selección al portapapeles y la marca como 'corte         pendie, copy_selection() antepone una fila de encabezados al TSV copiado         (para, Cancela el corte pendiente activo, si hay alguno, en cualquier tabla., Quita prefijos del sistema (iconos de tipo) sin afectar datos del usuario., _strip_icons()

### Community 76 - "_TarjetaRadio"
Cohesion: 0.20
Nodes (7): Ejecuta callback on_click con el valor de la tarjeta y consume el evento., Marca/desmarca la tarjeta y refresca el estilo visual., True si la tarjeta está seleccionada., Aplica colores highlight o default según estado activo/inactivo., Botón grande seleccionable: icono + nombre + descripción.     Activo -> fondo hi, Inicializa tarjeta: icono + nombre + descripción, callback on_click(valor) al ha, _TarjetaRadio

### Community 77 - "TablaExplosion"
Cohesion: 0.18
Nodes (7): Tabla de resultados plana con cada insumo mostrando su tipo.      Columnas: Tipo, Tabla plana de resultados: Tipo, Clave, Descripción, Unidad, Cantidad, P.U., Tot, Llena la tabla agrupando filas por tipo de insumo, con subtotales y total genera, Fila final con TOTAL GENERAL y 100 %., Engancha esta tabla al ciclo de vida estándar (ver         GUIA_INTERFAZ.md §7.6, Idempotente: no falla si nunca se conectó o ya se desconectó., TablaExplosion

### Community 78 - "._abrir"
Cohesion: 0.18
Nodes (6): Database vacía o que abre conexión si se pasa db_path., Abre (o reabre) conexión SQLite, aplica pragmas y schema, guarda como último pro, Cierra la conexión activa y limpia el estado., Aplica schema.sql completo. Crea tablas si no existen.         Para proyectos vi, Migración v5: agrega columnas nuevas a proyectos y migra datos         de config, Crea una nueva instancia de Database y abre conexión al .db.

### Community 79 - "_TransactionContext"
Cohesion: 0.20
Nodes (5): Connection, Conexión SQLite activa (solo lectura)., Context manager: abre transacción, commitea al salir, rollback si falla., Context manager para transacciones SQLite. Commitea al salir, rollback si falla., _TransactionContext

### Community 80 - "export_canvas_to_pdf"
Cohesion: 0.29
Nodes (8): date, export_canvas_to_pdf(), _header_date(), exportar_pdf.py =============== Exportación ligera de PDF para el visor DWG.  Ca, Exporta imagen PNG del canvas a PDF A4 apaisado.      Args:         image_data:, _strip_ext(), _ymd_stamp(), Exporta la vista actual del visor a PDF.

### Community 81 - "_num"
Cohesion: 0.20
Nodes (6): Persiste edición inline del árbol del presupuesto.          No hace falta refres, _num(), Formatea número con separadores de miles y decimales, o string vacío si es falsy, Búsqueda recursiva de la fila cuyo ID_ROLE == nodo_id., ConceptoActualizado: actualiza in-place la fila propia del nodo.          Bloq, NodoEliminado (entidad='estructura_presupuesto'): quita la fila.

### Community 82 - "._agregar_nodo"
Cohesion: 0.20
Nodes (5): Filtra filas del TreeTableWidget activo., Re-aplica el filtro de búsqueda al cambiar de pestaña., Agrega un capítulo/agrupador nuevo al presupuesto (solo si la pestaña activa es, Agrega un concepto nuevo al presupuesto, o un insumo si estamos en la pestaña de, Inserta un nodo del tipo dado en el presupuesto.          - Capítulo: se inser

### Community 83 - "._focus_or_open_tab"
Cohesion: 0.20
Nodes (5): Click simple en sidebar: abre pestaña temporal o enfoca si ya existe., Doble click en sidebar: abre pestaña permanente., Si ya existe una pestaña con ese título, la enfoca; si no, la abre.          P, Handler del botón 'Generadores' en la toolbar (pestaña INICIO)., Handler del botón 'Fuera de presupuesto' en la toolbar.

### Community 84 - "widgets/apu.py"
Cohesion: 0.24
Nodes (7): _combo_operador(), _combo_unidad(), _editable_cols_detalle(), apu.py (widgets) ================= TablaApuDetalle: árbol de desglose de un AP, matriz_id positivo = concepto; negativo = insumo compuesto (ver api.apu())., ColumnaDef, Definición de una columna dentro del catálogo completo de una tabla.      Una

### Community 85 - "EventBus"
Cohesion: 0.25
Nodes (5): EventBus, Bus de eventos simple. Suscribe callbacks a tipos de evento.      Uso:         b, Registra un callback para un tipo de evento., Retira un callback registrado previamente.          Los widgets deben llamar est, Emitir evento a todos los suscriptores registrados.          Cada callback se ej

### Community 86 - "VariableFormulaRepo"
Cohesion: 0.22
Nodes (3): Hard delete — no hay columna `activo` en esta tabla, a         diferencia de fam, Todas las variables de un proyecto, ordenadas por nombre., VariableFormulaRepo

### Community 87 - "PresupuestoPopup"
Cohesion: 0.25
Nodes (4): Abre el presupuesto en una ventana emergente no modal., PresupuestoPopup, QDialog, Popup con el árbol del presupuesto, misma lógica que la pestaña principal.

### Community 88 - "ProjectDialog"
Cohesion: 0.22
Nodes (5): Renombra un proyecto .db., ProjectDialog, Actualiza el estilo de fondo del item seleccionado en la lista., Filtra la lista de proyectos por nombre (case-insensitive) y oculta los que no c, Devuelve el nombre del proyecto seleccionado o None si no hay selección.

### Community 89 - "._get_move_context"
Cohesion: 0.22
Nodes (4): Contexto común para operaciones de mover/indent/outdent.         Devuelve (t, d, Tramos contiguos de ids seleccionados dentro de la lista de         hermanos (e, Saca los nodos seleccionados de su padre (outdent): pasan a         ser hijos d, Mete los nodos seleccionados como hijos del hermano inmediato         anterior

### Community 90 - ".insumo_ids_con_apu"
Cohesion: 0.25
Nodes (4): Devuelve el APU de un concepto del árbol (por nodo_id) o de un insumo         c, Conjunto de ids de insumos compuestos (tienen APU propio)., Catálogo de insumos, opcionalmente filtrado por tipo (ej. 'material', 'mano_obra, Como insumos() pero filtra solo los que aparecen en al menos un APU.

### Community 91 - ".apu_actualizar_valor"
Cohesion: 0.25
Nodes (4): Actualiza la cantidad y opcionalmente la fórmula de un concepto.          Si s, Resuelve todas las variables del proyecto en orden de         dependencias. Dev, Evalúa una expresión contra las variables del proyecto.         Devuelve Decima, Actualiza el valor y opcionalmente la fórmula de un componente APU.          S

### Community 92 - "busqueda_texto.py"
Cohesion: 0.36
Nodes (7): _build_snippet(), find_text_matches(), busqueda_texto.py ================= Búsqueda de texto sobre entidades TEXT/MTEXT, Estima el box world-space de una entidad TEXT., Encuentra entidades TEXT cuyo contenido contiene ``query`` (case-insensitive)., text_box_for_entity(), TextMatch

### Community 93 - "_ExploradorTree"
Cohesion: 0.25
Nodes (5): _ExploradorTree, QTreeWidget, QTreeWidget del sidebar Explorador.      Con el mouse, un clic en un grupo (Pr, Envuelve el sidebar normal y paneles contextuales (p.ej. el de         generado, Construye el explorador lateral.

### Community 94 - "._celdas"
Cohesion: 0.29
Nodes (4): Construye la lista de valores para todas las columnas desde el dict del nodo., Agrega nodo agrupador (capítulo).         El delegado inteligente permite edita, Agrega nodo hoja (concepto).         El delegado inteligente permite editar col, Recorre recursivamente los nodos insertando agrupadores y registros en el widget

### Community 95 - "._apply_column_modes"
Cohesion: 0.25
Nodes (4): Aplica anchos y modos de redimensión a las columnas.          Guarda la config, Aplica anchos y modos de redimension pendientes a cada columna., Restaura estado guardado del usuario; si no hay, aplica anchos por defecto., Restaura estado del header desde config.json si existe. Retorna True si restauró

### Community 96 - "WebSocketClient"
Cohesion: 0.25
Nodes (4): ws_client.py ============ Cliente WebSocket para recibir eventos en tiempo real, Cliente WS que re-emite eventos en el EventBus local.      Se instancia por proy, WebSocketClient, QThread

### Community 97 - "ConnectionManager"
Cohesion: 0.36
Nodes (4): ConnectionManager, Gestiona conexiones WebSocket agrupadas por proyecto., websocket_endpoint(), WebSocket

### Community 98 - "IndirectoRepo"
Cohesion: 0.29
Nodes (4): IndirectoRepo, Lista indirectos de un proyecto, opcionalmente filtrados por tipo., Recalcula el campo 'total' de todos los indirectos del proyecto., Suma de totales de indirectos de un tipo específico.

### Community 99 - "dialogs.py"
Cohesion: 0.33
Nodes (3): colores.py ========== Constantes de color del tema oscuro — una sola fuente de v, tipos_insumo.py ============== Datos maestros de tipos de insumo — una sola fuen, arbol.py ======== Tabla jerárquica del presupuesto (capítulos + conceptos).

### Community 100 - "._fit_transform"
Cohesion: 0.29
Nodes (3): Calcula (sin aplicarla) la transformación que encuadra ``rect``         en el vi, QRectF, QTransform

### Community 101 - "._obtener_o_crear_generador"
Cohesion: 0.33
Nodes (3): Abre la pestaña de generadores y carga el concepto dado., Doble clic en concepto: crea/busca generador y muestra renglones., Busca el primer generador del concepto; si no existe, lo crea.

### Community 102 - ".filter_rows"
Cohesion: 0.33
Nodes (3): Abre diálogo de capas para encender/apagar., Filtra filas visibles buscando text en las columnas configuradas (_search_cols)., Evalúa si item o algún hijo coincide; actualiza visibilidad. Retorna True si es

### Community 103 - "._abrir_indirectos_dlg"
Cohesion: 0.33
Nodes (3): Abre popup de indirectos de campo., Abre popup de indirectos de oficina., Construye y muestra el diálogo de indirectos para un tipo ('campo' | 'oficina').

### Community 104 - "_fmt"
Cohesion: 0.33
Nodes (4): _fmt(), Formatea número como moneda ($1,234.56) o devuelve string vacío si es None., Búsqueda recursiva de todas las filas cuyo INSUMO_ROLE == insumo_id         (un, InsumoActualizado: actualiza in-place todas las filas de concepto         ligad

### Community 105 - "._build_col_calculo"
Cohesion: 0.33
Nodes (3): Marca/desmarca el checkbox., Columna izquierda: tarjetas de selección del método de cálculo., Maneja clic en tarjeta de nivel: desmarca las demás, marca la seleccionada.

### Community 106 - ".insert"
Cohesion: 0.40
Nodes (3): Any, UPDATE genérico. No hace commit (asume transacción externa)., INSERT genérico. No hace commit. Devuelve lastrowid.

### Community 108 - "._build_col_tipos"
Cohesion: 0.40
Nodes (4): _label_seccion(), QLabel, Etiqueta de título de sección (mayúsculas, bold, letter-spacing)., Columna derecha: cuadrícula de checkboxes de tipos + botón toggle.

### Community 109 - "SchemaRegistry"
Cohesion: 0.50
Nodes (3): Valida cada campo del dict contra las reglas de la tabla., Reglas de validación por tabla y campo., SchemaRegistry

### Community 114 - "_editable_cols_arbol"
Cohesion: 0.50
Nodes (3): _editable_cols_arbol(), Columnas editables para una fila del árbol de presupuesto, según su tipo., Inicializa el árbol de presupuesto.         Si extra=True, este árbol muestra n

### Community 117 - "draw_tree_connectors"
Cohesion: 0.50
Nodes (3): draw_tree_connectors(), Dibuja conectores visuales entre nodos jerárquicos.     Por cada nivel dibuja u, Dibuja conectores jerárquicos entre nodos si el modo no es plano.

### Community 118 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, ../ponytail/.opencode/plugins/ponytail.mjs

## Knowledge Gaps
- **3 isolated node(s):** `$schema`, `../ponytail/.opencode/plugins/ponytail.mjs`, `schema_version`
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Rutas` connect `Rutas` to `.db_proyecto`, `HandlersMixin`, `latex.py`, `mixins/generador.py`, `DataService`, `Database`, `GestionProyectosMixin`, `ConnectionManager`, `Config`, `servidor.py`, `PanelesMixin`, `_ExploradorTree`, `QVBoxLayout`, `GeneradorMixin`, `InformesMixin`, `icono`, `Path`?**
  _High betweenness centrality (0.178) - this node is a cross-community bridge._
- **Why does `TreeTableWidget` connect `TreeTableWidget` to `ToolbarMixin`, `DataService`, `SidebarEstructura`, `TablaInsumos`, `DialogoConfigImpresion`, `PanelesMixin`, `_Delegate`, `icono`, `widgets/base.py`, `TablaApuDetalle`, `ventana.py`, `QVBoxLayout`, `._header_context_menu_catalogo`, `._get_active_table`, `._show_all`, `._paste`, `TablaGenerador`, `toolbar.py`, `.keyPressEvent`, `RastreoMixin`, `._cut`, `TablaExplosion`, `widgets/apu.py`, `._apply_column_modes`, `.filter_rows`, `draw_tree_connectors`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `Api` connect `Api` to `NodoRepo`, `DataService`, `Database`, `GestionProyectosMixin`, `.recalcular_proyecto`, `.guardar`, `_BackendHTTP`, `backend/formulas.py`, `.insumo_actualizar_precio`, `.insumo_actualizar_descripcion`, `ApiCliente`, `._http`, `.insumo_ids_con_apu`, `.apu_actualizar_valor`, `GeneradorRepo`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `Api` (e.g. with `InsumoActualizado` and `ProyectoRecalculado`) actually correct?**
  _`Api` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `TreeTableWidget` (e.g. with `._get_active_table()` and `._on_search_col_toggle()`) actually correct?**
  _`TreeTableWidget` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `HandlersMixin` (e.g. with `Rutas` and `ProyectoRecalculado`) actually correct?**
  _`HandlersMixin` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `DataService` (e.g. with `Database` and `ApuComponenteActualizado`) actually correct?**
  _`DataService` has 30 INFERRED edges - model-reasoned connections that need verification._