from datetime import datetime


def _parse_float(texto: str) -> float | None:
    """Convierte texto a float o None si es cero."""
    try:
        v = float(texto.replace(",", "."))
        return v if v else None
    except ValueError:
        return None
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QDoubleValidator
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QWidget, QFrame,
    QTreeWidgetItem, QAbstractItemView, QComboBox, QMessageBox,
    QCheckBox, QGroupBox, QGridLayout,
)
from PySide6.QtCore import Qt

_SEL_BG = "#2A4158"


# ── Diálogo de selección de proyecto ──────────────────────────────

class ProjectDialog(QDialog):

    # ── Constructor y layout ──────────────────────────────────────

    def __init__(self, proyectos: list[Path], titulo: str, accion: str,
                 accion_color: str = "#7FAFD6", seleccionado: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumSize(520, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Cabecera ──────────────────────────────────────────────
        header = QLabel(titulo)
        header.setObjectName("dlgHeader")
        header.setFixedHeight(48)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # ── Búsqueda ──────────────────────────────────────────────
        search = QLineEdit()
        search.setObjectName("dlgSearch")
        search.setPlaceholderText("\U0001f50d  Buscar proyecto\u2026")
        search.setClearButtonEnabled(True)
        sc = QWidget()
        sl = QHBoxLayout(sc)
        sl.setContentsMargins(16, 12, 16, 4)
        sl.addWidget(search)
        layout.addWidget(sc)

        # ── Lista de proyectos ────────────────────────────────────
        self._lista = QListWidget()
        self._lista.setObjectName("dlgList")
        self._lista.setAlternatingRowColors(True)

        idx_selected = 0
        for i, p in enumerate(proyectos):
            size_b = p.stat().st_size
            dt = datetime.fromtimestamp(p.stat().st_mtime)
            date_str = dt.strftime("%Y-%m-%d  %H:%M")
            size_str = f"{size_b / 1024:.0f} KB" if size_b < 1024 * 1024 else f"{size_b / (1024 * 1024):.1f} MB"

            w = QWidget()
            w.setObjectName("dlgItemWidget")
            wl = QHBoxLayout(w)
            wl.setContentsMargins(12, 6, 16, 6)
            wl.setSpacing(12)

            icon = QLabel("\U0001f4c1")
            icon.setObjectName("dlgIcon")
            wl.addWidget(icon)

            info = QVBoxLayout()
            info.setSpacing(0)
            lbl_name = QLabel(p.stem)
            lbl_name.setObjectName("dlgName")
            lbl_detail = QLabel(f"{date_str}  \u00b7  {size_str}")
            lbl_detail.setObjectName("dlgDetail")
            info.addWidget(lbl_name)
            info.addWidget(lbl_detail)
            wl.addLayout(info, 1)

            item = QListWidgetItem()
            item.setSizeHint(w.minimumSizeHint())
            self._lista.addItem(item)
            self._lista.setItemWidget(item, w)

            if seleccionado and p.stem == seleccionado:
                idx_selected = i

        self._lista.currentItemChanged.connect(self._on_seleccion)
        self._lista.itemDoubleClicked.connect(lambda: self.accept())
        layout.addWidget(self._lista, 1)

        # Apply initial selection
        if self._lista.count():
            self._lista.setCurrentRow(idx_selected)

        # Sep
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("dlgSep")
        layout.addWidget(sep)

        # ── Botones de acción ─────────────────────────────────────
        bl = QHBoxLayout()
        bl.setContentsMargins(16, 10, 16, 14)
        bl.setSpacing(8)

        cancel = QPushButton("Cancelar")
        cancel.setObjectName("dlgCancel")
        cancel.clicked.connect(self.reject)

        action = QPushButton(accion)
        action.setObjectName("dlgAction")
        action.setStyleSheet(f"""
            QPushButton#dlgAction {{
                background-color: {accion_color};
                color: #12161D;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 20px;
            }}
            QPushButton#dlgAction:hover {{
                background-color: {accion_color}CC;
            }}
        """)
        action.clicked.connect(self.accept)

        bl.addStretch()
        bl.addWidget(action)
        bl.addWidget(cancel)
        layout.addLayout(bl)

        search.textChanged.connect(self._filtrar)

    # ── Resaltado visual del ítem seleccionado ────────────────────

    def _on_seleccion(self, current, previous):
        """Actualiza el estilo de fondo del item seleccionado en la lista."""
        for item in (current, previous):
            if not item:
                continue
            w = self._lista.itemWidget(item)
            if w:
                selected = item is current and item is not None
                bg = _SEL_BG if selected else "transparent"
                w.setStyleSheet(f"background-color: {bg}; border-radius: 4px;")

    # ── Filtro por nombre ─────────────────────────────────────────

    def _filtrar(self, texto: str):
        """Filtra la lista de proyectos por nombre (case-insensitive) y oculta los que no coinciden."""
        t = texto.lower()
        for i in range(self._lista.count()):
            item = self._lista.item(i)
            w = self._lista.itemWidget(item)
            name = w.findChild(QLabel, "dlgName").text().lower()
            visible = t in name
            item.setHidden(not visible)

    # ── Propiedad: proyecto actual ────────────────────────────────

    @property
    def proyecto_seleccionado(self) -> str | None:
        """Devuelve el nombre del proyecto seleccionado o None si no hay selección."""
        item = self._lista.currentItem()
        if not item:
            return None
        w = self._lista.itemWidget(item)
        return w.findChild(QLabel, "dlgName").text()


# ── Diálogo de edición de descripción de insumo ───────────────────

class EditarDescripcionDialog(QDialog):
    """Diálogo modal para editar la descripción de un insumo.

    Muestra la descripción actual en un campo editable y el hash
    que se generaría con la nueva descripción (actualizado en tiempo real).
    Si el usuario acepta, el llamador debe invocar api.insumo_actualizar_descripcion()
    y manejar el ValueError en caso de duplicado.

    Uso:
        dlg = EditarDescripcionDialog(descripcion_actual, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nueva = dlg.descripcion
            try:
                api.insumo_actualizar_descripcion(insumo_id, nueva)
            except ValueError as e:
                QMessageBox.warning(self, "Descripción duplicada", str(e))
    """

    def __init__(self, descripcion_actual: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar descripción")
        self.setMinimumWidth(520)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # ── Etiqueta ──────────────────────────────────────────────
        lbl = QLabel("Descripción del insumo:")
        layout.addWidget(lbl)

        # ── Campo de texto ────────────────────────────────────────
        self._campo = QLineEdit(descripcion_actual)
        self._campo.setMinimumHeight(32)
        self._campo.selectAll()
        layout.addWidget(self._campo)

        # ── Preview del hash ──────────────────────────────────────
        self._lbl_hash = QLabel()
        self._lbl_hash.setObjectName("hashPreview")
        self._lbl_hash.setStyleSheet("color: #7FAFD6; font-family: monospace; font-size: 11px;")
        layout.addWidget(self._lbl_hash)
        self._actualizar_hash(descripcion_actual)
        self._campo.textChanged.connect(self._actualizar_hash)

        # ── Botones ───────────────────────────────────────────────
        bl = QHBoxLayout()
        bl.setSpacing(8)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        guardar = QPushButton("Guardar")
        guardar.setDefault(True)
        guardar.clicked.connect(self._on_guardar)
        bl.addStretch()
        bl.addWidget(guardar)
        bl.addWidget(cancelar)
        layout.addLayout(bl)

    def _actualizar_hash(self, texto: str):
        """Actualiza el label de preview del hash en tiempo real."""
        try:
            from backend.database.core import generar_hash
            h = generar_hash(texto) if texto.strip() else "—"
        except Exception:
            h = "—"
        self._lbl_hash.setText(f"Hash generado: {h}")

    def _on_guardar(self):
        """Valida que el campo no esté vacío antes de aceptar."""
        if not self._campo.text().strip():
            self._lbl_hash.setText("⚠ La descripción no puede estar vacía.")
            self._lbl_hash.setStyleSheet("color: #E06C75; font-size: 11px;")
            return
        self.accept()

    @property
    def descripcion(self) -> str:
        """Devuelve la descripción ingresada por el usuario."""
        return self._campo.text().strip()


# ── Diálogo de edición de precio de insumo ────────────────────────

class EditarPrecioDialog(QDialog):
    """Diálogo modal para editar el precio de un insumo.

    Uso:
        dlg = EditarPrecioDialog(precio_actual, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            api.insumo_actualizar_precio(insumo_id, dlg.precio)
    """

    def __init__(self, precio_actual: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar precio")
        self.setFixedWidth(320)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        lbl = QLabel("Precio unitario:")
        layout.addWidget(lbl)

        self._campo = QLineEdit(f"{precio_actual:.4f}")
        self._campo.setMinimumHeight(32)
        self._campo.selectAll()
        layout.addWidget(self._campo)

        self._lbl_error = QLabel("")
        self._lbl_error.setStyleSheet("color: #E06C75; font-size: 11px;")
        layout.addWidget(self._lbl_error)

        bl = QHBoxLayout()
        bl.setSpacing(8)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        guardar = QPushButton("Guardar")
        guardar.setDefault(True)
        guardar.clicked.connect(self._on_guardar)
        bl.addStretch()
        bl.addWidget(guardar)
        bl.addWidget(cancelar)
        layout.addLayout(bl)

    def _on_guardar(self):
        """Valida que el valor sea numérico y no negativo."""
        try:
            val = float(self._campo.text().replace(",", "."))
            if val < 0:
                raise ValueError
            self._precio = val
            self.accept()
        except ValueError:
            self._lbl_error.setText("⚠ Ingresa un número válido mayor o igual a 0.")

    @property
    def precio(self) -> float:
        """Devuelve el precio validado."""
        return getattr(self, "_precio", 0.0)


# ── Tipos de insumo para filtros ──────────────────────────────────

_TIPO_ICONO = {
    1: "🧱", 2: "👷", 4: "🔧", 8: "🚜",
    16: "⚙️", 32: "📄", 64: "🚛", 128: "🏗️",
}

_TIPO_NOMBRE = {
    1: "Materiales", 2: "Mano de obra", 4: "Herramienta", 8: "Equipo",
    16: "Auxiliares", 32: "Conceptos", 64: "Fletes", 128: "Trabajos",
}

_FILTROS_TIPO = [
    (32, "📄",  "Conceptos"),
    (1,  "🧱",  "Materiales"),
    (2,  "👷",  "Mano de obra"),
    (4,  "🔧",  "Herramienta"),
    (8,  "🚜",  "Equipo"),
    (16, "⚙️",  "Auxiliares"),
    (64, "🚛",  "Fletes"),
    (128,"🏗️", "Trabajos"),
]


# ── Diálogo de selección de insumo ─────────────────────────────────

class DialogoSeleccionarInsumo(QDialog):
    """Diálogo modal para buscar y seleccionar un insumo del catálogo.

    Tiene barra de búsqueda + botones de filtro por tipo + tabla
    (mismas columnas que la vista de insumos, incluido Tipo con icono).

    Uso:
        dlg = DialogoSeleccionarInsumo(api, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nuevo_id = dlg.insumo_seleccionado
    """

    def __init__(self, api, parent=None, *, default_tipos: set[int] | None = None):
        super().__init__(parent)
        self._api = api
        self._selected_id = None
        self._tipos_filtro: set[int] = {32} if default_tipos is None else default_tipos
        self._items: list[tuple[int, QTreeWidgetItem, int]] = []

        self.setWindowTitle("Seleccionar insumo")
        self.setMinimumSize(700, 520)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # ── Search bar ──────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Buscar insumo…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._aplicar_filtros)
        layout.addWidget(self._search)

        # ── Filter buttons (icono + tooltip, azul al activarse) ──
        fila_btns = QHBoxLayout()
        fila_btns.setSpacing(4)
        self._btns_tipo: dict[int, QPushButton] = {}
        for tipo_id, icono, nombre in _FILTROS_TIPO:
            btn = QPushButton(icono)
            btn.setToolTip(nombre)
            btn.setCheckable(True)
            btn.setMinimumSize(76, 66)
            btn.setMaximumSize(90, 70)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            fnt = btn.font()
            fnt.setFamilies(["Segoe UI Emoji", "Segoe UI"])
            fnt.setPointSize(26)
            btn.setFont(fnt)
            btn.setStyleSheet(
                "QPushButton { padding: 0; margin: 0; }"
                "QPushButton:checked { background-color: #7FAFD6; color: #12161D; }"
            )
            btn.clicked.connect(lambda _, t=tipo_id: self._on_tipo_click(t))
            self._btns_tipo[tipo_id] = btn
            fila_btns.addWidget(btn)
        fila_btns.addStretch()
        layout.addLayout(fila_btns)

        # ── Toolbar: nuevo / editar insumo ─────────────────────────
        tb = QHBoxLayout()
        tb.setSpacing(4)
        self._btn_nuevo = QPushButton("➕  Nuevo")
        self._btn_nuevo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_nuevo.clicked.connect(self._on_nuevo_insumo)
        tb.addWidget(self._btn_nuevo)
        self._btn_editar = QPushButton("✏️  Editar")
        self._btn_editar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_editar.clicked.connect(self._on_editar_insumo)
        tb.addWidget(self._btn_editar)
        tb.addStretch()
        layout.addLayout(tb)

        # ── Results tree (usa TablaInsumos internamente) ────────
        from frontend.ventana.widgets.insumos import TablaInsumos, TIPO_NOMBRE, COLUMNAS_CATALOGO
        self._tree = TablaInsumos()
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.itemDoubleClicked.connect(self._on_aceptar)
        layout.addWidget(self._tree)

        # ── Load data ───────────────────────────────────────────
        self._cargar_insumos()

        # ── Default: tipos pasados por el caller (ej. {1,2}=Materiales+MO) ──
        for tid in self._tipos_filtro:
            if tid in self._btns_tipo:
                self._btns_tipo[tid].setChecked(True)
        self._aplicar_filtros()

        # ── Buttons ─────────────────────────────────────────────
        bl = QHBoxLayout()
        bl.setSpacing(8)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        aceptar = QPushButton("Seleccionar")
        aceptar.setDefault(True)
        aceptar.clicked.connect(self._on_aceptar)
        bl.addStretch()
        bl.addWidget(aceptar)
        bl.addWidget(cancelar)
        layout.addLayout(bl)

    def _cargar_insumos(self):
        """Carga todos los insumos del proyecto en la tabla."""
        try:
            filas = self._api.insumos()
        except Exception:
            filas = []
        self._tree.poblar(filas)
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            ins_id = item.data(0, Qt.ItemDataRole.UserRole)
            tipo_id = filas[i].get("tipo_id", 0) if i < len(filas) else 0
            self._items.append((ins_id, item, tipo_id))

    def _on_tipo_click(self, tipo_id: int):
        from PySide6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if tipo_id in self._tipos_filtro:
                self._tipos_filtro.discard(tipo_id)
            else:
                self._tipos_filtro.add(tipo_id)
        else:
            if self._tipos_filtro == {tipo_id}:
                self._tipos_filtro.clear()
            else:
                self._tipos_filtro = {tipo_id}
        for tid, btn in self._btns_tipo.items():
            btn.setChecked(tid in self._tipos_filtro)
        self._aplicar_filtros()

    def _aplicar_filtros(self):
        texto = self._search.text()
        if texto:
            self._tree.filter_rows(texto)
        else:
            self._tree._show_all()
        if self._tipos_filtro:
            for _, item, tipo_id in self._items:
                if tipo_id not in self._tipos_filtro:
                    item.setHidden(True)

    def _on_nuevo_insumo(self):
        """Abre el diálogo de nuevo insumo; recarga la lista si se creó uno."""
        dlg = InsumoDialog(self._api, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._cargar_insumos()
            self._aplicar_filtros()
            nuevo_id = dlg.insumo_id
            if nuevo_id is not None:
                self._selected_id = nuevo_id
                self.accept()

    def _on_editar_insumo(self):
        """Abre el diálogo de edición para el insumo seleccionado."""
        sel = self._tree.currentItem()
        if not sel:
            return
        insumo_id = sel.data(0, Qt.ItemDataRole.UserRole)
        if not insumo_id:
            return
        dlg = InsumoDialog(self._api, insumo_id=insumo_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._cargar_insumos()
            self._aplicar_filtros()

    def _on_aceptar(self):
        sel = self._tree.currentItem()
        if not sel:
            return
        self._selected_id = sel.data(0, Qt.ItemDataRole.UserRole)
        if self._selected_id is not None:
            self.accept()

    @property
    def insumo_seleccionado(self) -> int | None:
        return self._selected_id


# ── Diálogo de nuevo / editar insumo ────────────────────────────────

class InsumoDialog(QDialog):
    """Diálogo para crear o editar un insumo.

    Uso (crear):
        dlg = InsumoDialog(api, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nuevo_id = dlg.insumo_id   # int del insumo recién creado

    Uso (editar):
        dlg = InsumoDialog(api, insumo_id=42, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pass  # insumo 42 actualizado
    """

    def __init__(self, api, insumo_id: int | None = None, parent=None):
        super().__init__(parent)
        self._api = api
        self._insumo_id = insumo_id
        self._resultado: int | None = insumo_id  # en edición se mantiene el mismo

        self.setWindowTitle("Nuevo insumo" if insumo_id is None else "Editar insumo")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # ── Tipo * + Unidad ──────────────────────────────────────
        tipo_unidad_row = QHBoxLayout()
        tipo_unidad_row.setSpacing(8)
        tipo_col = QVBoxLayout()
        tipo_col.setSpacing(2)
        tipo_col.addWidget(QLabel("Tipo *:"))
        self._tipo = QComboBox()
        for tid in (32, 1, 2, 4, 8, 16, 64, 128):
            icono = _TIPO_ICONO.get(tid, "")
            nombre = _TIPO_NOMBRE.get(tid, f"Tipo {tid}")
            self._tipo.addItem(f"{icono}  {nombre}", tid)
        tipo_col.addWidget(self._tipo)
        tipo_unidad_row.addLayout(tipo_col, 1)
        unidad_col = QVBoxLayout()
        unidad_col.setSpacing(2)
        unidad_col.addWidget(QLabel("Unidad *:"))
        from frontend.ventana.widgets.base import UNIDADES
        self._unidad_warn = QLabel()
        self._unidad_warn.setStyleSheet("color: #D5B39B; font-size: 11px;")
        self._unidad_warn.hide()
        self._unidad = QComboBox()
        self._unidad.setEditable(True)
        self._unidad.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._unidad.lineEdit().textChanged.connect(self._checar_unidad)
        for u in UNIDADES:
            self._unidad.addItem(u)
        self._unidad.setCurrentText("")
        unidad_col.addWidget(self._unidad)
        unidad_col.addWidget(self._unidad_warn)
        tipo_unidad_row.addLayout(unidad_col, 1)
        layout.addLayout(tipo_unidad_row)

        # ── Descripción * ─────────────────────────────────────────
        layout.addWidget(QLabel("Descripción *:"))
        self._desc = QLineEdit()
        self._desc.setPlaceholderText("Descripción del insumo")
        layout.addWidget(self._desc)

        # ── Desc. corta ──────────────────────────────────────────
        layout.addWidget(QLabel("Desc. corta:"))
        self._desc_corta = QLineEdit()
        self._desc_corta.setPlaceholderText("Abreviatura")
        layout.addWidget(self._desc_corta)

        # ── Familia ──────────────────────────────────────────────
        layout.addWidget(QLabel("Familia:"))
        self._familia = QComboBox()
        self._familia.setEditable(True)
        self._familia.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._familia.addItem("(Sin familia)", None)
        for f in self._api.familias():
            self._familia.addItem(f.get("nombre", "?"), f.get("id"))
        self._familia.currentIndexChanged.connect(self._recargar_subfamilias)
        layout.addWidget(self._familia)

        # ── Subfamilia ───────────────────────────────────────────
        layout.addWidget(QLabel("Subfamilia:"))
        self._subfamilia = QComboBox()
        self._subfamilia.setEditable(True)
        self._subfamilia.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._subfamilia.addItem("(Sin subfamilia)", None)
        layout.addWidget(self._subfamilia)

        # ── Precios ──────────────────────────────────────────────
        precios_box = QGroupBox("Precios unitarios")
        precios_layout = QGridLayout(precios_box)
        precios_layout.setSpacing(6)

        self._es_compuesto = QCheckBox("Insumo compuesto (tiene APU propio)")
        precios_layout.addWidget(self._es_compuesto, 0, 0, 1, 2)

        precios_layout.addWidget(QLabel("PU MN:"), 1, 0)
        self._precio_mn = QLineEdit("0.00")
        self._precio_mn.setValidator(QDoubleValidator(0.0, 1e12, 4))
        precios_layout.addWidget(self._precio_mn, 1, 1)

        precios_layout.addWidget(QLabel("PU ME:"), 2, 0)
        self._precio_me = QLineEdit("0.00")
        self._precio_me.setValidator(QDoubleValidator(0.0, 1e12, 4))
        precios_layout.addWidget(self._precio_me, 2, 1)

        layout.addWidget(precios_box)

        self._es_compuesto.toggled.connect(self._alternar_precios)
        self._alternar_precios(self._es_compuesto.isChecked())

        # ── Opciones avanzadas (colapsable) ───────────────────────
        self._avanzadas_btn = QPushButton("▶  Opciones avanzadas")
        self._avanzadas_btn.setFlat(True)
        self._avanzadas_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._avanzadas_btn.setStyleSheet("""
            QPushButton { text-align: left; padding: 4px 0; font-weight: bold;
                          color: #7FAFD6; border: none; }
            QPushButton:hover { color: #9BC1E8; }
        """)
        self._avanzadas_btn.clicked.connect(self._alternar_avanzadas)
        layout.addWidget(self._avanzadas_btn)

        self._avanzadas_panel = QFrame()
        self._avanzadas_panel.setVisible(False)
        av_layout = QVBoxLayout(self._avanzadas_panel)
        av_layout.setSpacing(6)
        av_layout.setContentsMargins(0, 0, 0, 0)

        av_layout.addWidget(QLabel("Comentarios / Notas:"))
        self._comentarios = QLineEdit()
        self._comentarios.setPlaceholderText("Notas internas del insumo")
        av_layout.addWidget(self._comentarios)

        adv_grid = QGridLayout()
        adv_grid.setSpacing(6)
        adv_grid.addWidget(QLabel("Clave OPUS:"), 0, 0)
        self._clave_opus = QLineEdit()
        self._clave_opus.setPlaceholderText("Código original OPUS")
        adv_grid.addWidget(self._clave_opus, 0, 1)

        adv_grid.addWidget(QLabel("Peso (kg):"), 0, 2)
        self._peso_kg = QLineEdit("0.00")
        self._peso_kg.setValidator(QDoubleValidator(0.0, 1e6, 4))
        adv_grid.addWidget(self._peso_kg, 0, 3)


        av_layout.addLayout(adv_grid)

        layout.addWidget(self._avanzadas_panel)

        # ── Pre-cargar si es edición ─────────────────────────────
        if insumo_id is not None:
            self._cargar()

        # ── Botones ──────────────────────────────────────────────
        bl = QHBoxLayout()
        bl.setSpacing(8)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        guardar = QPushButton("Guardar")
        guardar.setDefault(True)
        guardar.clicked.connect(self._guardar)
        bl.addStretch()
        bl.addWidget(guardar)
        bl.addWidget(cancelar)
        layout.addLayout(bl)

    def _cargar(self):
        """Pre-puebla los campos desde la BD (modo edición)."""
        insumo = self._api.insumo_por_id(self._insumo_id)
        if not insumo:
            return
        idx = self._tipo.findData(insumo.get("tipo_id"))
        if idx >= 0:
            self._tipo.setCurrentIndex(idx)
        self._desc.setText(insumo.get("descripcion", ""))
        u = insumo.get("unidad", "")
        idx = self._unidad.findText(u)
        if idx >= 0:
            self._unidad.setCurrentIndex(idx)
        else:
            self._unidad.setEditText(u)
        self._checar_unidad(insumo.get("unidad", ""))

        comp = bool(insumo.get("es_compuesto"))
        self._es_compuesto.setChecked(comp)

        fid = insumo.get("familia_id")
        if fid:
            idx = self._familia.findData(fid)
            if idx >= 0:
                self._familia.setCurrentIndex(idx)
            else:
                self._familia.setEditText(insumo.get("familia_nombre") or "")
            self._recargar_subfamilias()
            sfid = insumo.get("subfamilia_id")
            if sfid:
                s_idx = self._subfamilia.findData(sfid)
                if s_idx >= 0:
                    self._subfamilia.setCurrentIndex(s_idx)
                else:
                    self._subfamilia.setEditText(insumo.get("subfamilia_nombre") or "")

        self._precio_mn.setText(f"{insumo.get('costo_mn', 0):.2f}")
        self._precio_me.setText(f"{insumo.get('costo_me', 0):.2f}")

        self._desc_corta.setText(insumo.get("descripcion_corta") or "")
        self._clave_opus.setText(insumo.get("clave_opus") or "")
        self._peso_kg.setText(f"{insumo.get('peso_kg', 0):.4f}" if insumo.get('peso_kg') else "0.00")
        self._comentarios.setText(insumo.get("comentarios") or "")

    def _recargar_subfamilias(self):
        """Recarga subfamilias al cambiar la familia seleccionada."""
        self._subfamilia.clear()
        self._subfamilia.addItem("(Sin subfamilia)", None)
        fid = self._familia.currentData()
        if fid:
            for sf in self._api.subfamilias(fid):
                self._subfamilia.addItem(sf.get("nombre", "?"), sf.get("id"))

    def _alternar_avanzadas(self):
        visible = self._avanzadas_panel.isVisible()
        self._avanzadas_panel.setVisible(not visible)
        self._avanzadas_btn.setText("▼  Opciones avanzadas" if not visible else "▶  Opciones avanzadas")
        self.adjustSize()

    def _alternar_precios(self, compuesto: bool):
        """Habilita/deshabilita los campos de precio según es_compuesto."""
        self._precio_mn.setDisabled(compuesto)
        self._precio_me.setDisabled(compuesto)
        color = "#555" if compuesto else ""
        self._precio_mn.setStyleSheet(f"color: {color};" if compuesto else "")
        self._precio_me.setStyleSheet(f"color: {color};" if compuesto else "")

    def _checar_unidad(self, texto: str):
        """Muestra advertencia si la unidad no está en el catálogo estándar."""
        from frontend.ventana.widgets.base import UNIDADES
        t = texto.strip()
        if t and t not in UNIDADES:
            self._unidad_warn.setText("⚠ Unidad no estándar (no aparece en el catálogo)")
            self._unidad_warn.show()
        else:
            self._unidad_warn.hide()

    def _resolver_familia(self) -> int | None:
        """Crea la familia si el texto no coincide con ninguna existente."""
        texto = self._familia.currentText().strip()
        if not texto or texto == "(Sin familia)":
            return None
        existing = self._familia.findText(texto)
        if existing >= 0:
            return self._familia.itemData(existing)
        fid = self._api.familia_insertar(texto)
        self._familia.addItem(texto, fid)
        self._familia.setCurrentIndex(self._familia.count() - 1)
        return fid

    def _resolver_subfamilia(self, familia_id: int) -> int | None:
        """Crea la subfamilia si el texto no coincide con ninguna existente."""
        texto = self._subfamilia.currentText().strip()
        if not texto or texto == "(Sin subfamilia)" or familia_id is None:
            return None
        existing = self._subfamilia.findText(texto)
        if existing >= 0:
            return self._subfamilia.itemData(existing)
        sfid = self._api.subfamilia_insertar(familia_id, texto)
        self._subfamilia.addItem(texto, sfid)
        self._subfamilia.setCurrentIndex(self._subfamilia.count() - 1)
        return sfid

    def _guardar(self):
        desc = self._desc.text().strip()
        if not desc:
            QMessageBox.warning(self, "Campo requerido", "La descripción no puede estar vacía.")
            return

        tipo_id = self._tipo.currentData()
        unidad = self._unidad.currentText().strip()
        if not unidad:
            QMessageBox.warning(self, "Campo requerido", "La unidad no puede estar vacía.")
            return
        es_compuesto = 1 if self._es_compuesto.isChecked() else 0
        familia_id = self._resolver_familia()
        subfamilia_id = self._resolver_subfamilia(familia_id) if familia_id else None

        if not es_compuesto:
            try:
                costo_mn = float(self._precio_mn.text().replace(",", "."))
                costo_me = float(self._precio_me.text().replace(",", "."))
            except ValueError:
                QMessageBox.warning(self, "Valor inválido", "Ingresa números válidos para los precios.")
                return
        else:
            costo_mn = 0.0
            costo_me = 0.0

        from frontend.ventana.widgets.base import UNIDADES
        if unidad and unidad not in UNIDADES:
            resp = QMessageBox.question(
                self, "Unidad no estándar",
                f"'{unidad}' no es una unidad del catálogo estándar.\n¿Guardar de todas formas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        # ── Campos avanzados ──
        extra = {
            "clave_opus": self._clave_opus.text().strip() or None,
            "descripcion_corta": self._desc_corta.text().strip() or None,
            "peso_kg": _parse_float(self._peso_kg.text()),
            "comentarios": self._comentarios.text().strip() or None,
        }

        if self._insumo_id is not None:
            # ── Editar existente ──
            iid = self._insumo_id
            try:
                self._api.insumo_actualizar_descripcion(iid, desc)
            except ValueError as e:
                QMessageBox.warning(self, "Descripción duplicada", str(e))
                return
            if unidad:
                self._api.insumo_actualizar_campo(iid, "unidad", unidad)
            self._api.insumo_actualizar_campo(iid, "es_compuesto", es_compuesto)
            if familia_id:
                self._api.insumo_actualizar_campo(iid, "familia_id", familia_id)
            elif familia_id is None:
                self._api.insumo_actualizar_campo(iid, "familia_id", None)
                self._api.insumo_actualizar_campo(iid, "subfamilia_id", None)
            elif subfamilia_id:
                self._api.insumo_actualizar_campo(iid, "subfamilia_id", subfamilia_id)
            self._api.insumo_actualizar_precios(iid, costo_mn, costo_me)
            for campo, valor in extra.items():
                if valor is not None:
                    self._api.insumo_actualizar_campo(iid, campo, valor)
        else:
            # ── Crear nuevo ──
            try:
                self._resultado = self._api.insumo_insertar(
                    tipo_id=tipo_id, descripcion=desc, unidad=unidad,
                    costo=costo_mn, costo_me=costo_me,
                    es_compuesto=es_compuesto,
                    familia_id=familia_id, subfamilia_id=subfamilia_id,
                )
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))
                return
            # clave_usuario auto = "INS-{id}"
            self._api.insumo_actualizar_campo(self._resultado, "clave_usuario", f"INS-{self._resultado}")
            for campo, valor in extra.items():
                if valor is not None:
                    self._api.insumo_actualizar_campo(self._resultado, campo, valor)

        self.accept()

    @property
    def insumo_id(self) -> int | None:
        return self._resultado
