from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QWidget, QFrame,
    QTreeWidgetItem, QAbstractItemView,
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
