"""
informes.py
===========
Mixin de informes: generar presupuesto PDF, compilar PDF, vista previa.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""


class InformesMixin:
    """Mixin de informes — se mezcla en VentanaPrincipal."""

    def _on_generar_presupuesto(self):
        """Genera .tex y .pdf del presupuesto.

        Por defecto, si hay algo seleccionado en el árbol del presupuesto
        (uno o más capítulos/conceptos), el reporte incluye solo esa
        selección; si no hay nada seleccionado, incluye todo el
        presupuesto. Aplica al resto de reportes (APU, Explosión,
        Catálogo) en cuanto se implementen — ver
        TablaArbol.ids_seleccionados_arbol().
        """
        arbol = getattr(self, "_arbol_presupuesto", None)
        ids_seleccionados = arbol.ids_seleccionados_arbol() if arbol is not None else set()
        self._generar_reporte_presupuesto(ids_seleccionados=ids_seleccionados or None)

    def _generar_reporte_presupuesto(self, ids_seleccionados: set[int] | None = None):
        """Lógica de generación y compilación del .tex del presupuesto.

        ids_seleccionados=None (o vacío) → presupuesto completo.
        ids_seleccionados con contenido  → solo esos capítulos/conceptos
        (ver backend/exportar/informe_pdf/latex.py::filtrar_por_seleccion).
        """
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from backend.exportar.informe_pdf.latex import ReportePresupuesto, compilar_pdf
        from backend.database.db import Rutas
        from pathlib import Path

        if self._requiere_proyecto(api=True):
            return

        nombre = Path(self._db.db_path).stem
        nodos = self._api.presupuesto_arbol()
        if not nodos:
            self._sb.showMessage("El presupuesto está vacío.", 3000)
            return

        arbol = getattr(self, "_arbol_presupuesto", None)
        columnas = arbol.columnas_para_reporte() if arbol is not None else None

        from frontend.ventana.widgets.config_impresion import config_actual
        cfg = config_actual()

        sufijo = "_seleccion" if ids_seleccionados else ""
        tex_path = Rutas.reportes() / f"{nombre}_presupuesto{sufijo}.tex"

        from frontend.ventana.ui_utils import progreso_indeterminado
        with progreso_indeterminado(self, "Generando reporte…"):
            ReportePresupuesto(
                nombre, nodos, columnas=columnas, ids_seleccionados=ids_seleccionados,
                margenes={"sup": cfg["margen_sup_cm"], "inf": cfg["margen_inf_cm"],
                          "izq": cfg["margen_izq_cm"], "der": cfg["margen_der_cm"]},
                orientacion=cfg["orientacion"],
                anchos_cm=cfg["anchos_cm"],
            ).generar(tex_path)

            pdf = compilar_pdf(tex_path)
        if pdf:
            self._sb.showMessage(f"PDF generado: {pdf}", 5000)
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf))
        else:
            self._sb.showMessage(f"Reporte .tex generado: {tex_path}", 5000)

    def _on_config_impresion(self):
        """Abre el diálogo de configuración de impresión (márgenes,
        orientación y anchos de columna) del reporte de presupuesto."""
        from frontend.ventana.widgets.config_impresion import DialogoConfigImpresion

        arbol = getattr(self, "_arbol_presupuesto", None)
        columnas = arbol.columnas_para_reporte() if arbol is not None else None
        DialogoConfigImpresion(self, columnas_actuales=columnas).exec()

    def _on_compilar_pdf(self):
        """Compila el .tex seleccionado a PDF con pdflatex."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from backend.exportar.informe_pdf.latex import compilar_pdf
        from frontend.ventana.ui_utils import progreso_indeterminado

        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo .tex",
            "", "LaTeX (*.tex)",
        )
        if not path:
            return

        with progreso_indeterminado(self, "Compilando PDF…"):
            pdf = compilar_pdf(path)
        if pdf:
            self._sb.showMessage(f"PDF generado: {pdf}", 6000)
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
