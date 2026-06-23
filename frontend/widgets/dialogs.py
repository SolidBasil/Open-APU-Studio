from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QWidget, QFrame,
)

_SEL_BG = "#2A4158"


class ProjectDialog(QDialog):
    _items: list[QListWidgetItem] = []

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

        # Header
        header = QLabel(titulo)
        header.setObjectName("dlgHeader")
        header.setFixedHeight(48)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Search
        search = QLineEdit()
        search.setObjectName("dlgSearch")
        search.setPlaceholderText("\U0001f50d  Buscar proyecto\u2026")
        search.setClearButtonEnabled(True)
        sc = QWidget()
        sl = QHBoxLayout(sc)
        sl.setContentsMargins(16, 12, 16, 4)
        sl.addWidget(search)
        layout.addWidget(sc)

        # List
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
        layout.addWidget(self._lista, 1)

        # Apply initial selection
        if self._lista.count():
            self._lista.setCurrentRow(idx_selected)

        # Sep
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("dlgSep")
        layout.addWidget(sep)

        # Buttons
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

    def _on_seleccion(self, current, previous):
        for item in (current, previous):
            if not item:
                continue
            w = self._lista.itemWidget(item)
            if w:
                selected = item is current and item is not None
                bg = _SEL_BG if selected else "transparent"
                w.setStyleSheet(f"background-color: {bg}; border-radius: 4px;")

    def _filtrar(self, texto: str):
        t = texto.lower()
        for i in range(self._lista.count()):
            item = self._lista.item(i)
            w = self._lista.itemWidget(item)
            name = w.findChild(QLabel, "dlgName").text().lower()
            visible = t in name
            item.setHidden(not visible)

    @property
    def proyecto_seleccionado(self) -> str | None:
        item = self._lista.currentItem()
        if not item:
            return None
        w = self._lista.itemWidget(item)
        return w.findChild(QLabel, "dlgName").text()
