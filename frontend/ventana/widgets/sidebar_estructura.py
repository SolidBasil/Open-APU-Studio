"""
sidebar_estructura.py — Panel Lateral Estructural (dos niveles)
================================================================
Panel izquierdo de dos niveles, igual a RAM Elements:
    Nivel 1: 6 categorías (Nudos / Miembros / Placas / Área / Gen / Catálogos)
    Nivel 2: Sub-pestañas con tablas editables por categoría

Cada sub-pestaña es una TreeTableWidget respaldada por la base de datos
SQLite del proyecto (ver backend/database/repos.py): se carga desde ahí al
construirse y cada edición se guarda de inmediato.

Pendiente (confirmado en manual RAM pág. 35): cada tabla debería solo mostrar
los elementos seleccionados en el viewport 3D (requiere picking 3D).
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabBar, QTabWidget, QStackedWidget, QHeaderView, QLabel
from PySide6.QtCore import Signal, QSize, Qt

from frontend.ventana.widgets.base import TreeTableWidget
from frontend.ventana.iconos import icono
from backend.database.hoja_bindings import BINDINGS, cargar_hoja, guardar_fila, eliminar_fila, siguiente_etiqueta


# =============================================================================
# ICONOS DE SUB-PESTAÑA — Lucide SVG (cross-platform)
# =============================================================================

_ICONOS_SUBPESTANA = {
    "Coordenadas": "crosshair",
    "Restricciones": "lock",
    "Resortes": "waves",
    "Diafragma de piso rígido": "building",
    "Masas": "circle",
    "Fuerzas": "arrow-down",
    "Desplazamientos prescritos": "arrow-left-right",
    "Conectividad": "link",
    "Conexiones de nudos": "share-2",
    "Secciones": "square",
    "Materiales": "hard-hat",
    "Ejes locales": "type",
    "Punto cardinal": "compass",
    "Cacho rígido": "move",
    "Articulaciones": "circle-dot",
    "Comportamiento axial": "arrow-up-down",
    "Cargas sobre miembros": "arrow-down",
    "Número de piso": "list",
    "Espesor": "ruler",
    "Ejes locales ": "type",
    "Apoyos intermedios": "chevron-down",
    "Cargas": "arrow-down",
    "Claros": "minus",
    "Interfaces": "layers",
    "Factor de rigidez": "percent",
    "Nudos": "circle-dot",
    "Dirección de carga": "arrow-right",
    "Peso propio": "arrow-down",
    "Aceleración de sismo": "activity",
    "Espectro sísmico": "chart-line",
    "Casos de carga": "arrow-down",
}


def _es_autoid(binding) -> bool:
    """True si la primera columna de la hoja es la etiqueta autoincremental
    del elemento (Nudo/Miembro/Placa/Área) — esa columna no la escribe el
    usuario, se genera sola. Los catálogos (columna "nombre") quedan fuera.
    """
    return bool(
        binding and binding.columnas
        and binding.columnas[0].columna == "etiqueta"
        and binding.columnas[0].tipo == "texto"
    )


# Colores por categoría para distinguir visualmente los iconos
_COLORES_CATEGORIA = {
    "Coordenadas": "#7FAFD6",       # azul acento
    "Restricciones": "#D5B39B",     # café/warning
    "Resortes": "#5E92B8",          # azul claro
    "Diafragma de piso rígido": "#8B6FB5",  # púrpura
    "Masas": "#A06A6A",             # rojo suave
    "Fuerzas": "#D5B39B",           # café/warning
    "Desplazamientos prescritos": "#5B8A72", # verde
    "Conectividad": "#7FAFD6",      # azul acento
    "Conexiones de nudos": "#7FAFD6",
    "Secciones": "#5E92B8",
    "Materiales": "#D5B39B",
    "Ejes locales": "#B7C0C8",      # gris claro
    "Punto cardinal": "#5B8A72",
    "Cacho rígido": "#B7C0C8",
    "Articulaciones": "#7FAFD6",
    "Comportamiento axial": "#5E92B8",
    "Cargas sobre miembros": "#D5B39B",
    "Número de piso": "#B7C0C8",
    "Espesor": "#B7C0C8",
    "Ejes locales ": "#B7C0C8",
    "Apoyos intermedios": "#D5B39B",
    "Cargas": "#D5B39B",
    "Claros": "#5E92B8",
    "Interfaces": "#7FAFD6",
    "Factor de rigidez": "#5B8A72",
    "Nudos": "#7FAFD6",
    "Dirección de carga": "#5E92B8",
    "Peso propio": "#D5B39B",
    "Aceleración de sismo": "#A06A6A",
    "Espectro sísmico": "#8B6FB5",
    "Casos de carga": "#D5B39B",
}


def _icono_subpestana(nombre: str):
    svg_name = _ICONOS_SUBPESTANA.get(nombre, "dot")
    color = _COLORES_CATEGORIA.get(nombre, "#E8EDF2")
    return icono(svg_name, 18, color)


# =============================================================================
# ESTRUCTURA — { categoría: { subpestaña: [columnas...] } }
# Todas las columnas son editables por ahora (tablas de entrada de datos,
# como en RAM). Ajustaremos a solo-lectura/atenuado donde aplique cuando
# conectemos al motor.
# =============================================================================

ESTRUCTURA = {
    "Nudos": {
        "Coordenadas":               ["Nudo", "X", "Y", "Z"],
        "Restricciones":             ["Nudo", "Ux", "Uy", "Uz", "Rx", "Ry", "Rz"],
        "Resortes":                  ["Nudo", "Kx", "Ky", "Kz", "Krx", "Kry", "Krz"],
        "Diafragma de piso rígido":  ["Nudo", "Piso", "Diafragma"],
        "Masas":                     ["Nudo", "Mx", "My", "Mz"],
        "Fuerzas":                   ["Nudo", "Fx", "Fy", "Fz", "Mx", "My", "Mz", "Caso de carga"],
        "Desplazamientos prescritos": ["Nudo", "Dx", "Dy", "Dz", "Rx", "Ry", "Rz", "Caso de carga"],
    },
    "Miembros": {
        "Conectividad":          ["Miembro", "Nudo I", "Nudo J", "Descripción"],
        "Conexiones de nudos":   ["Miembro", "Condición I", "Condición J"],
        "Secciones":             ["Miembro", "Sección"],
        "Materiales":            ["Miembro", "Material"],
        "Ejes locales":          ["Miembro", "Ángulo β"],
        "Punto cardinal":        ["Miembro", "Punto cardinal"],
        "Cacho rígido":          ["Miembro", "Cacho I", "Cacho J"],
        "Articulaciones":        ["Miembro", "Articulación I", "Articulación J"],
        "Comportamiento axial":  ["Miembro", "Tipo"],
        "Cargas sobre miembros": ["Miembro", "Tipo de carga", "Magnitud", "Dirección", "Caso de carga"],
        "Número de piso":        ["Miembro", "Piso"],
    },
    "Placas": {
        "Conectividad":       ["Placa", "Nudo 1", "Nudo 2", "Nudo 3", "Nudo 4", "Descripción"],
        "Espesor":            ["Placa", "Espesor", "Tipo (losa/muro)"],
        "Material":           ["Placa", "Material"],
        "Ejes locales":       ["Placa", "Ángulo"],
        "Apoyos intermedios": ["Placa", "Nudo de apoyo"],
        "Cargas":             ["Placa", "Tipo de carga", "Magnitud", "Dirección", "Caso de carga"],
        "Claros":             ["Placa", "Claro X", "Claro Y"],
        "Interfaces":         ["Placa", "Interface"],
        "Número de piso":     ["Placa", "Piso"],
        "Factor de rigidez":  ["Placa", "Factor"],
    },
    "Área": {
        "Nudos":              ["Área", "Nudo 1", "Nudo 2", "Nudo 3", "Nudo 4"],
        "Dirección de carga": ["Área", "Dirección"],
        "Cargas":             ["Área", "Magnitud", "Caso de carga"],
    },
    "Gen": {
        "Peso propio":        ["Factor X", "Factor Y", "Factor Z"],
        "Aceleración de sismo": ["Caso", "Ax", "Ay", "Az"],
        "Espectro sísmico":   ["Caso", "Periodo (s)", "Sa (g)"],
    },
    "Catálogos": {
        "Secciones":      ["Nombre", "Tipo", "Área", "Iy", "Iz", "J", "b", "h", "d"],
        "Materiales":     ["Nombre", "Tipo", "E", "G", "Poisson", "Peso específico", "fy", "f'c"],
        "Casos de carga": ["Nombre", "Tipo"],
    },
}


class SidebarEstructura(QWidget):
    """Panel izquierdo de dos niveles (categoría -> sub-pestaña -> tabla).

    Cada tabla se carga desde la base de datos del proyecto (`conn`) al
    construirse, y cualquier edición se persiste de inmediato (INSERT si la
    fila es nueva, UPDATE si ya existía) según el mapeo de BINDINGS.

    Expone una interfaz mínima para que el ribbon reaccione a la hoja
    activa, sin necesitar saber que hay dos niveles de pestañas:
        .tabla_activa()       -> TreeTableWidget actualmente visible
        .nombre_hoja_activa() -> nombre de la sub-pestaña activa (para
                                  'Herramientas de la hoja activa')
        .cambio_hoja (Signal) -> se emite cuando cambia categoría o sub-pestaña
        .datos_cambiados (Signal) -> se emite tras cada guardado exitoso
        .error_guardado (Signal[str]) -> se emite si una edición no se pudo
                                          guardar (ej. referencia inexistente)
    """

    cambio_hoja = Signal()
    datos_cambiados = Signal()
    error_guardado = Signal(str)

    # Filas en blanco extra al final de cada hoja, para poder escribir datos
    # nuevos directamente en la tabla (se insertan en la BD al llenarlas).
    FILAS_PLANTILLA = 15

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self._conn = conn
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Categorías (QTabBar, sin pane) ──
        self.tabs_categoria = QTabBar()
        self.tabs_categoria.setObjectName("sidebarCategorias")
        layout.addWidget(self.tabs_categoria)

        # ── Label con nombre del área activa ──
        self._lbl_area = QLabel()
        self._lbl_area.setObjectName("sidebarAreaLabel")
        f = QFont()
        f.setBold(True)
        f.setPointSize(9)
        self._lbl_area.setFont(f)
        self._lbl_area.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._lbl_area)

        # ── Stack de sub-pestañas (una QTabWidget por categoría) ──
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        self.tablas: dict[tuple[str, str], TreeTableWidget] = {}
        self._subtabs: dict[str, QTabWidget] = {}

        for categoria, subpestanas in ESTRUCTURA.items():
            tabs_sub = QTabWidget()
            tabs_sub.setObjectName("sidebarSubpestanas")
            tabs_sub.setTabPosition(QTabWidget.TabPosition.North)
            tabs_sub.setUsesScrollButtons(False)
            tabs_sub.tabBar().setIconSize(QSize(18, 18))
            self._subtabs[categoria] = tabs_sub

            for nombre_sub, columnas in subpestanas.items():
                binding = BINDINGS.get((categoria, nombre_sub))
                autoid = _es_autoid(binding)
                editable_cols = frozenset(range(1, len(columnas))) if autoid else frozenset(range(len(columnas)))
                tabla = TreeTableWidget(columnas, editable_cols=editable_cols, flat=True)
                self.tablas[(categoria, nombre_sub)] = tabla
                idx = tabs_sub.addTab(tabla, "")
                tabs_sub.setTabIcon(idx, _icono_subpestana(nombre_sub))
                tabs_sub.setTabToolTip(idx, nombre_sub)
                self._cargar_hoja_en_tabla(categoria, nombre_sub, tabla)

            tabs_sub.currentChanged.connect(lambda i, tw=tabs_sub: self._actualizar_label_area(tw, i))
            tabs_sub.currentChanged.connect(lambda _=None: self.cambio_hoja.emit())
            self._stack.addWidget(tabs_sub)
            self.tabs_categoria.addTab(categoria)

        self.tabs_categoria.currentChanged.connect(self._on_categoria_changed)
        self._on_categoria_changed(0)

    def _on_categoria_changed(self, idx: int):
        """Cambia la página del stack y actualiza el label."""
        self._stack.setCurrentIndex(idx)
        tabs_sub = self._stack.currentWidget()
        if isinstance(tabs_sub, QTabWidget):
            self._actualizar_label_area(tabs_sub, tabs_sub.currentIndex())
        self.cambio_hoja.emit()

    def _actualizar_label_area(self, tabs_sub: QTabWidget, idx_activo: int):
        """Actualiza el label con el nombre del área activa."""
        if idx_activo >= 0:
            nombre = tabs_sub.tabToolTip(idx_activo)
            self._lbl_area.setText(nombre)

    # ------------------------------------------------------------------ #
    # API para el ribbon / búsqueda
    # ------------------------------------------------------------------ #

    def tabla_activa(self) -> TreeTableWidget | None:
        tabs_sub = self._stack.currentWidget()
        if not isinstance(tabs_sub, QTabWidget):
            return None
        return tabs_sub.currentWidget()

    def nombre_categoria_activa(self) -> str:
        idx = self.tabs_categoria.currentIndex()
        return self.tabs_categoria.tabText(idx)

    def nombre_hoja_activa(self) -> str:
        tabs_sub = self._stack.currentWidget()
        if not isinstance(tabs_sub, QTabWidget):
            return ""
        return tabs_sub.tabToolTip(tabs_sub.currentIndex())

    def ir_a(self, categoria: str, sub: str | None = None):
        """Navega a una categoría (y opcionalmente sub-pestaña) por nombre."""
        for i in range(self.tabs_categoria.count()):
            if self.tabs_categoria.tabText(i) == categoria:
                self.tabs_categoria.setCurrentIndex(i)
                if sub:
                    tabs_sub = self._stack.widget(i)
                    for j in range(tabs_sub.count()):
                        if tabs_sub.tabToolTip(j) == sub:
                            tabs_sub.setCurrentIndex(j)
                            break
                break

    # ------------------------------------------------------------------ #
    # BASE DE DATOS — carga inicial y guardado en cada edición
    # ------------------------------------------------------------------ #

    def _cargar_hoja_en_tabla(self, categoria: str, nombre_sub: str, tabla: TreeTableWidget):
        """Llena `tabla` con las filas reales de la BD + filas en blanco para
        capturar datos nuevos, y conecta el guardado automático de ediciones.

        Si (categoria, nombre_sub) no tiene HojaBinding definida todavía
        (sub-pestañas de RAM que no mapeamos a ninguna tabla), la hoja se
        deja vacía — sin conexión a BD — en vez de fallar.
        """
        binding = BINDINGS.get((categoria, nombre_sub))
        if binding is None:
            return

        tabla.blockSignals(True)
        try:
            for fila_id, valores in cargar_hoja(self._conn, binding):
                tabla.add_row(valores, editable=True)
                item = tabla.topLevelItem(tabla.topLevelItemCount() - 1)
                item.setData(0, Qt.ItemDataRole.UserRole, fila_id)
                self._aplicar_checkboxes(item, binding)

            if not binding.fila_unica:
                ncols = len(binding.columnas)
                for _ in range(self.FILAS_PLANTILLA):
                    tabla.add_row([""] * ncols, editable=True)
                    item = tabla.topLevelItem(tabla.topLevelItemCount() - 1)
                    self._aplicar_checkboxes(item, binding)
        finally:
            tabla.blockSignals(False)

        tabla.itemChanged.connect(
            lambda item, col, cat=categoria, sub=nombre_sub, tw=tabla:
                self._on_item_changed(item, col, cat, sub, tw)
        )
        tabla.filas_eliminar_solicitadas.connect(
            lambda items, cat=categoria, sub=nombre_sub, tw=tabla:
                self._on_eliminar_filas(items, cat, sub, tw)
        )

    @staticmethod
    def _aplicar_checkboxes(item, binding):
        """Habilita el indicador de checkbox en las columnas tipo 'check'
        (Restricciones) y fija su estado según el valor cargado."""
        for i, c in enumerate(binding.columnas):
            if c.tipo != "check":
                continue
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            marcado = item.text(i) in ("1", "true", "True")
            item.setText(i, "")
            item.setCheckState(i, Qt.CheckState.Checked if marcado else Qt.CheckState.Unchecked)

    def _on_item_changed(self, item, col: int, categoria: str, nombre_sub: str, tabla: TreeTableWidget):
        """Persiste la fila completa (INSERT si es nueva, UPDATE si ya existía).

        Antes de guardar, en una fila nueva (fila_id es None):
        - Si la hoja tiene etiqueta autoincremental (Nudo/Miembro/Placa/Área)
          y todavía no tiene una asignada, se genera sola (N1, N2...) en
          cuanto el usuario llena cualquier otra columna.
        - Si la columna editada es numérica, las demás columnas numéricas
          de la fila que sigan vacías se completan con "0" (para no dejar
          una coordenada a medias: "0, 3, 0" en vez de "", "3", "") — el
          usuario las puede seguir editando después normalmente.
        """
        binding = BINDINGS[(categoria, nombre_sub)]
        fila_id = item.data(0, Qt.ItemDataRole.UserRole)

        if fila_id is None:
            tabla.blockSignals(True)
            try:
                if _es_autoid(binding) and col != 0 and not item.text(0).strip():
                    item.setText(0, siguiente_etiqueta(self._conn, binding.tabla))

                if 0 <= col < len(binding.columnas) and binding.columnas[col].numero:
                    for i, c in enumerate(binding.columnas):
                        if i != col and c.numero and not item.text(i).strip():
                            item.setText(i, "0")
            finally:
                tabla.blockSignals(False)

        valores = []
        for i, c in enumerate(binding.columnas):
            if c.tipo == "check":
                valores.append("1" if item.checkState(i) == Qt.CheckState.Checked else "0")
            else:
                valores.append(item.text(i))

        # Fila plantilla que sigue vacía (el usuario tocó y salió sin escribir
        # nada) -> no crear una fila vacía en la BD.
        if fila_id is None and not any(v.strip() for v in valores):
            return

        tabla.blockSignals(True)
        try:
            nuevo_id, error = guardar_fila(self._conn, binding, fila_id, valores)
            if error:
                self.error_guardado.emit(error)
                return
            if fila_id is None:
                item.setData(0, Qt.ItemDataRole.UserRole, nuevo_id)
        finally:
            tabla.blockSignals(False)

        self.datos_cambiados.emit()

    def _on_eliminar_filas(self, items: list, categoria: str, nombre_sub: str, tabla: TreeTableWidget):
        """Elimina las filas seleccionadas (Supr/Backspace en la tabla).

        Las que ya estaban guardadas en la BD se borran ahí también (y por
        FK ON DELETE CASCADE se van sus cargas/hijos, ver schema.sql); las
        filas plantilla vacías simplemente se quitan del árbol. Cada fila
        real que se borra se repone por una fila plantilla en blanco al
        final, para no perder el "colchón" de filas nuevas disponibles.
        """
        binding = BINDINGS.get((categoria, nombre_sub))
        if binding is None or binding.fila_unica or not items:
            return  # la fila única (Gen → Peso propio) no se puede borrar

        ncols = len(binding.columnas)
        hubo_borrado_real = False

        tabla.blockSignals(True)
        try:
            for item in items:
                fila_id = item.data(0, Qt.ItemDataRole.UserRole)
                if fila_id is not None:
                    try:
                        eliminar_fila(self._conn, binding, fila_id)
                    except sqlite3.IntegrityError:
                        # Referenciado por otro elemento (ej. nudo usado por
                        # una barra) — no se borra, se avisa y se conserva.
                        etiqueta = item.text(0) or fila_id
                        self.error_guardado.emit(
                            f"No se pudo eliminar '{etiqueta}': está en uso por otro elemento."
                        )
                        continue
                    hubo_borrado_real = True

                idx = tabla.indexOfTopLevelItem(item)
                if idx >= 0:
                    tabla.takeTopLevelItem(idx)

                if fila_id is not None:
                    nuevo = tabla.add_row([""] * ncols, editable=True)
                    self._aplicar_checkboxes(nuevo, binding)
        finally:
            tabla.blockSignals(False)

        if hubo_borrado_real:
            self.datos_cambiados.emit()