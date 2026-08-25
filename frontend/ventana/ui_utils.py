"""
ui_utils.py
===========
Utilidades pequeñas de UI compartidas entre mixins.

cursor_espera(): la app no usa hilos para operaciones lentas (compilar
LaTeX, importar un proyecto legado) — corren directo sobre el hilo
principal, así que mientras duran, Qt no repinta y la ventana se ve
congelada sin ningún aviso. Este helper al menos cambia el cursor a
"reloj de arena" para que quede claro que la app sigue viva y está
trabajando.
"""

from contextlib import contextmanager

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog, QMessageBox


def traducir_error(e: Exception) -> str:
    """Traduce excepciones técnicas comunes a un mensaje que dice qué
    pasó y qué hacer, en vez del texto crudo de Python — cosas como
    "PermissionError: [Errno 13] Permission denied: 'C:\\Users\\...\\
    proyecto.presup'" no le dicen a la mayoría de las personas qué hacer.

    No pretende cubrir todas las excepciones posibles — solo las más
    frecuentes en las operaciones de archivo/BD de esta app (abrir
    proyecto, importar, exportar, recalcular). Si no reconoce la
    excepción, devuelve su texto tal cual en vez de ocultarlo — mejor
    un mensaje técnico que ninguno.
    """
    import sqlite3
    texto = str(e)

    if isinstance(e, PermissionError):
        return ("No se pudo acceder al archivo — probablemente está abierto "
                "en otro programa (o en otra ventana de esta misma app). "
                "Ciérralo e intenta de nuevo.")
    if isinstance(e, FileNotFoundError):
        return f"No se encontró el archivo:\n{texto}"
    if isinstance(e, sqlite3.OperationalError):
        if "locked" in texto.lower():
            return ("La base de datos del proyecto está ocupada — puede estar "
                    "abierta en otra ventana de la app. Ciérrala e intenta "
                    "de nuevo.")
        return "Hubo un problema al leer o escribir la base de datos del proyecto."
    if isinstance(e, OSError):
        return f"Problema al acceder al disco:\n{texto}"
    return texto


def mostrar_error(parent, titulo: str, e: Exception, *, critico: bool = True):
    """QMessageBox con el mensaje traducido (ver traducir_error arriba)
    como texto principal, y el texto técnico original disponible bajo
    "Show Details" en vez de mostrado siempre — así quien lo necesite
    (para reportarlo) lo puede ver y copiar, sin que la mayoría de las
    personas tengan que leer un traceback para saber qué pasó.
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(titulo)
    msg.setIcon(QMessageBox.Icon.Critical if critico else QMessageBox.Icon.Warning)
    mensaje = traducir_error(e)
    msg.setText(mensaje)
    detalle = str(e)
    if detalle and detalle.strip() != mensaje.strip():
        msg.setDetailedText(f"Detalle técnico:\n{type(e).__name__}: {detalle}")
    msg.exec()


def confirmar(parent, titulo: str, texto: str, texto_accion: str = "Sí", *,
              destructivo: bool = False) -> bool:
    """Diálogo de confirmación (Sí/No) con botones en español.

    QMessageBox.question(...) con los StandardButton.Yes/No nativos de Qt
    muestra "Yes"/"No" en inglés — la app no instala ningún QTranslator
    para los strings propios de Qt, así que esos botones nunca se
    traducen solos. Este helper arma los mismos dos botones a mano, con
    texto en español, con el mismo patrón que ya se usaba a mano en
    gestion_proyectos.py para sus diálogos más elaborados (addButton con
    ButtonRole explícito) — aquí generalizado para reusarse en cualquier
    confirmación simple de la app, sea un mixin o un widget suelto.

    texto_accion: texto del botón que confirma (ej. "Eliminar", "Guardar
    de todas formas"). destructivo=True lo marca con DestructiveRole
    (algunos estilos de plataforma lo resaltan, ej. en rojo).
    "Cancelar" siempre queda como botón por default — para una acción
    destructiva, presionar Enter sin querer nunca debe borrar nada.

    Devuelve True si se confirmó, False si se canceló.
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(titulo)
    msg.setText(texto)
    msg.setIcon(QMessageBox.Icon.Question)
    rol = (QMessageBox.ButtonRole.DestructiveRole if destructivo
           else QMessageBox.ButtonRole.AcceptRole)
    btn_accion = msg.addButton(texto_accion, rol)
    btn_cancelar = msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    msg.setDefaultButton(btn_cancelar)
    msg.exec()
    return msg.clickedButton() is btn_accion


@contextmanager
def cursor_espera():
    """Cursor de reloj de arena mientras dura el bloque `with`.

    Restaura el cursor normal aunque la operación lance una excepción.
    Para que el usuario vea el cambio ANTES de que arranque la operación
    bloqueante (Qt no repinta hasta que el hilo vuelve al event loop),
    llama a QApplication.processEvents() justo después de mostrar
    cualquier mensaje de status bar y antes de entrar al bloque:

        self._sb.showMessage("Generando PDF…")
        QApplication.processEvents()
        with cursor_espera():
            pdf = compilar_pdf(tex_path)
    """
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


@contextmanager
def progreso_indeterminado(parent, mensaje: str):
    """Diálogo de "trabajando…" (barra indeterminada, sin botón Cancelar)
    para operaciones largas y bloqueantes de un solo hilo.

    No es una barra de progreso real con porcentaje — la app no corre
    estas operaciones en un hilo aparte (ver cursor_espera arriba), así
    que no hay de dónde sacar un avance medible sin reestructurar la
    llamada en pasos. Lo que sí resuelve: cursor_espera() por sí solo es
    fácil de no notar (un cambio de forma de cursor, nada más); este
    diálogo ocupa una porción visible de la pantalla, deja claro que algo
    tarda, y evita que la persona piense que la app se congeló durante
    una importación grande, una compilación de PDF, o un recálculo de un
    presupuesto con miles de conceptos.

    Igual que cursor_espera(), depende de que Qt alcance a pintar el
    diálogo ANTES de que arranque el bloqueo — por eso el show() +
    processEvents() van aquí adentro, no hace falta que cada caller se
    acuerde de llamarlos aparte:

        with progreso_indeterminado(self, "Compilando PDF…"):
            pdf = compilar_pdf(tex_path)
    """
    dlg = QProgressDialog(mensaje, "", 0, 0, parent)
    dlg.setWindowTitle("Un momento…")
    dlg.setCancelButton(None)
    dlg.setWindowModality(Qt.WindowModality.WindowModal)
    dlg.setMinimumDuration(0)
    dlg.show()
    QApplication.processEvents()
    try:
        yield dlg
    finally:
        dlg.close()
