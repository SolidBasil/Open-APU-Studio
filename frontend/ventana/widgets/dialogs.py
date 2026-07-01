from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QWidget, QFrame,
)

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
