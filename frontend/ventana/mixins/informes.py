"""
informes.py
===========
Mixin de informes: generar presupuesto PDF, compilar PDF, vista previa.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""


class InformesMixin:
    """Mixin de informes — se mezcla en VentanaPrincipal."""

    def _on_generar_presupuesto(self):
        """Genera .tex y .pdf del presupuesto en la carpeta de reportes del usuario."""
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from backend.exportar.informe_pdf.latex import ReportePresupuesto, compilar_pdf
        from backend.database.db import Rutas
        from pathlib import Path

        if not self._api:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        nombre = Path(self._db.db_path).stem
        nodos = self._api.presupuesto_arbol()
        if not nodos:
            QMessageBox.information(self, "Sin datos", "El presupuesto está vacío.")
            return

        tex_path = Rutas.reportes() / f"{nombre}_presupuesto.tex"
        ReportePresupuesto(nombre, nodos).generar(tex_path)

        pdf = compilar_pdf(tex_path)
        if pdf:
            self._sb.showMessage(f"PDF generado: {pdf}", 5000)
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf))
        else:
            self._sb.showMessage(f"Reporte .tex generado: {tex_path}", 5000)

    def _on_compilar_pdf(self):
        """Compila el .tex seleccionado a PDF con pdflatex."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from backend.exportar.informe_pdf.latex import compilar_pdf

        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo .tex",
            "", "LaTeX (*.tex)",
        )
        if not path:
            return

        pdf = compilar_pdf(path)
        if pdf:
            QMessageBox.information(self, "Compilación exitosa",
                                    f"PDF generado:\n{pdf}")
        else:
            QMessageBox.warning(self, "Error de compilación",
                                "No se pudo compilar el PDF.\n"
                                "Verifica que pdflatex esté instalado y en el PATH.")

    def _on_vista_previa(self):
        """Abre el PDF generado con el visor del sistema."""
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo PDF",
            "", "PDF (*.pdf)",
        )
        if not path:
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
