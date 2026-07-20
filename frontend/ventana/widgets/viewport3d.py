"""
viewport3d.py — Viewport 3D para modelos estructurales
======================================================
Basado en PyVista (VTK) embebido en Qt vía pyvistaqt.QtInteractor.

Proporciona visualización 3D interactiva (rotar/zoom/pan con mouse) de:
- Geometría de la estructura (nodos + elementos)
- Forma deformada escalada
- Diagramas de fuerza interna (momento, cortante, axial)

Uso:
    from frontend.ventana.widgets.viewport3d import Viewport3D

    vp = Viewport3D()
    vp.mostrar_modelo(nodos, elementos)
    vp.mostrar_deformada(nodos, elementos, escala=50)
    vp.mostrar_fuerza(nodos, elementos, campo="momento_y")
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor


# =============================================================================
# PALETA DE COLORES — Tema oscuro de Open APU Studio
# =============================================================================
COLOR_FONDO       = "#12161D"   # Fondo del viewport
COLOR_COLUMNA     = "#7FAFD6"   # Columnas (azul claro)
COLOR_VIGA        = "#5A82AB"   # Vigas (azul medio)
COLOR_NODO        = "#E8EDF2"   # Nodos libres (blanco grisáceo)
COLOR_NODO_FIJO   = "#D66A6A"   # Nodos restringidos/apoyos (rojo)
COLOR_DEFORMADA   = "#F2C14E"   # Forma deformada / momento (dorado)
COLOR_UNDEFORMADA = "#3A4756"   # Geometría original semitransparente (gris)
COLOR_FUERZA      = "#6FCF97"   # Diagramas de fuerza (verde)


class Viewport3D(QWidget):
    """Widget embebible con un render 3D interactivo.

    Attributes:
        plotter: Instancia de QtInteractor (PyVista) para dibujar en 3D.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # PyVista QtInteractor — widget 3D interactivo
        self.plotter = QtInteractor(self)
        self.plotter.set_background(COLOR_FONDO)
        layout.addWidget(self.plotter.interactor)

        # Estilo de cámara "terrain": rota por azimuth (alrededor del eje Z,
        # que es la vertical de la estructura) + elevación, en vez del
        # trackball libre por defecto. Esto evita que la estructura pueda
        # quedar "de cabeza" al rotar — la base siempre se mantiene abajo,
        # igual que en un viewport CAD/BIM típico. Middle-click para hacer
        # pan (con shift_pans=False, shift+izquierdo restringe la rotación
        # a un solo eje a la vez).
        self.plotter.camera.up = (0.0, 0.0, 1.0)
        self.plotter.enable_terrain_style(mouse_wheel_zooms=True, shift_pans=False)

        # State para tracking de actores
        self._actor_nodos = None
        self._actor_elementos: list = []
        self._mostrar_etiquetas = False

    # ------------------------------------------------------------------ #
    # API PÚBLICA — Métodos principales de visualización
    # ------------------------------------------------------------------ #

    def limpiar(self):
        """Limpia todos los elementos de la escena 3D."""
        self.plotter.clear()
        self._actor_elementos = []
        self._actor_nodos = None

    def mostrar_modelo(self, nodos, elementos, etiquetas: bool = False):
        """Dibuja la geometría no-deformada de la estructura.

        Args:
            nodos: Lista de objetos Nodo con coordenadas.
            elementos: Lista de objetos Elemento con conectividad.
            etiquetas: Si True, muestra tags de nodos como labels.
        """
        self.limpiar()
        coords = {n.tag: n.coord for n in nodos}

        # Dibujar elementos (vigas/columnas) como tubos
        self._dibujar_elementos(elementos, coords, color=COLOR_VIGA,
                                 color_columna=COLOR_COLUMNA)
        # Dibujar nodos como esferas
        self._dibujar_nodos(nodos, deformado=False)

        if etiquetas:
            self._dibujar_etiquetas(nodos)

        # Reset camera para ver toda la estructura
        self.plotter.reset_camera()
        self.plotter.view_isometric()

    def mostrar_deformada(self, nodos, elementos, escala: float = 50.0,
                           mostrar_original: bool = True):
        """Superpone la forma deformada (escalada) sobre la geometría original.

        Args:
            nodos: Lista de nodos con desplazamientos (dx, dy, dz).
            elementos: Lista de elementos.
            escala: Factor de escala para los desplazamientos.
            mostrar_original: Si True, muestra la geometría original semitransparente.
        """
        self.limpiar()
        coords_orig = {n.tag: n.coord for n in nodos}

        # Geometría original semitransparente
        if mostrar_original:
            self._dibujar_elementos(elementos, coords_orig,
                                     color=COLOR_UNDEFORMADA,
                                     color_columna=COLOR_UNDEFORMADA,
                                     opacidad=0.35, radio=0.04)

        # Coordenadas deformadas = originales + desplazamiento * escala
        coords_def = {
            n.tag: (n.x + n.dx * escala, n.y + n.dy * escala, n.z + n.dz * escala)
            for n in nodos
        }
        self._dibujar_elementos(elementos, coords_def, color=COLOR_DEFORMADA,
                                 color_columna=COLOR_DEFORMADA, radio=0.06)
        self._dibujar_nodos(nodos, deformado=True, escala=escala)

        self.plotter.reset_camera()
        self.plotter.view_isometric()

    def mostrar_fuerza(self, nodos, elementos, campo: str, escala: float = None,
                        color: str = COLOR_FUERZA):
        """Diagrama genérico de fuerza interna sobre la estructura.

        Dibuja polilíneas desplazadas perpendicularmente al eje del elemento,
        donde el offset es proporcional al valor de la fuerza.

        Args:
            nodos: Lista de nodos.
            elementos: Lista de elementos con datos de fuerza.
            campo: Nombre del atributo en Elemento ('momento_y', 'momento_z',
                   'corte_y', 'corte_z', 'axial').
            escala: Factor de escala. Si es None, se calcula automáticamente
                    para que el valor máximo sea ~1.5 unidades.
            color: Color del diagrama en hex.
        """
        self.limpiar()
        coords = {n.tag: n.coord for n in nodos}

        # Estructura original semitransparente
        self._dibujar_elementos(elementos, coords, color=COLOR_UNDEFORMADA,
                                 color_columna=COLOR_UNDEFORMADA,
                                 opacidad=0.35, radio=0.04)

        # Escala automática: normalizar a ~1.5 unidades máximas
        if escala is None:
            valores = [abs(getattr(el, campo)) for el in elementos]
            max_val = max(valores) if valores else 1.0
            if max_val < 1e-10:
                max_val = 1.0
            escala = 1.5 / max_val

        # Dibujar diagrama por cada elemento
        for el in elementos:
            p1 = np.array(coords.get(el.nodo_i, (0, 0, 0)))
            p2 = np.array(coords.get(el.nodo_j, (0, 0, 0)))
            if el.nodo_i not in coords or el.nodo_j not in coords:
                continue

            valor = getattr(el, campo)
            if abs(valor) < 1e-10:
                continue

            # Vector del elemento y su normal en el plano XZ
            vec = p2 - p1
            largo = np.linalg.norm(vec)
            if largo < 1e-10:
                continue

            # Normal perpendicular al elemento en el plano XZ (rotación 90°)
            normal = np.array([-vec[2], 0.0, vec[0]])
            norm_len = np.linalg.norm(normal)
            if norm_len < 1e-10:
                # Elemento vertical: usar eje X como normal
                normal = np.array([1.0, 0.0, 0.0])
            else:
                normal = normal / norm_len

            # 4 puntos de la polilínea del diagrama
            # i -> offset_i -> offset_j -> j
            offset = normal * valor * escala
            pts = np.array([p1, p1 + offset, p2 + offset, p2])

            # Línea del contorno del diagrama
            line = pv.lines_from_points(pts)
            self.plotter.add_mesh(line, color=color, line_width=3)

            # Relleno semitransparente (dos triángulos formando un quad)
            faces = np.array([3, 0, 1, 3, 3, 1, 2, 3])
            surf = pv.PolyData(pts, faces=faces)
            self.plotter.add_mesh(surf, color=color, opacity=0.3)

        # Línea de referencia (eje del elemento) en gris
        for el in elementos:
            p1 = coords.get(el.nodo_i)
            p2 = coords.get(el.nodo_j)
            if p1 and p2:
                line = pv.lines_from_points(np.array([p1, p2]))
                self.plotter.add_mesh(line, color=COLOR_UNDEFORMADA, line_width=1)

        self._dibujar_nodos(nodos, deformado=False)
        self.plotter.reset_camera()
        self.plotter.view_isometric()

    def mostrar_reacciones(self, nodos, elementos, escala: float = None,
                            color: str = COLOR_NODO_FIJO):
        """Dibuja las reacciones de apoyo como flechas en los nudos restringidos.

        Requiere que el modelo ya esté analizado (usa rx_reac/ry_reac/rz_reac
        de cada Nodo, calculados por OpenSeesRepo.obtener_nodos()).

        Args:
            nodos: Lista de nodos (con reacciones si el modelo fue analizado).
            elementos: Lista de elementos (se dibuja la estructura de referencia).
            escala: Factor de escala de las flechas. Si es None, se calcula
                    automáticamente para que la reacción máxima sea ~1.5 unidades.
            color: Color de las flechas y etiquetas.
        """
        self.limpiar()
        coords = {n.tag: n.coord for n in nodos}

        # Estructura original semitransparente de referencia
        self._dibujar_elementos(elementos, coords, color=COLOR_UNDEFORMADA,
                                 color_columna=COLOR_UNDEFORMADA,
                                 opacidad=0.35, radio=0.04)
        self._dibujar_nodos(nodos, deformado=False)

        # Solo nudos restringidos con reacción no nula (evita flechas de largo 0)
        restringidos = [
            n for n in nodos
            if n.restringido and (abs(n.rx_reac) + abs(n.ry_reac) + abs(n.rz_reac)) > 1e-10
        ]

        if restringidos:
            if escala is None:
                max_val = max(
                    (abs(n.rx_reac) ** 2 + abs(n.ry_reac) ** 2 + abs(n.rz_reac) ** 2) ** 0.5
                    for n in restringidos
                )
                escala = 1.5 / max_val if max_val > 1e-10 else 1.0

            cent  = np.array([n.coord for n in restringidos])
            direc = np.array([(n.rx_reac, n.ry_reac, n.rz_reac) for n in restringidos]) * escala
            self.plotter.add_arrows(cent, direc, mag=1.0, color=color)

            etiquetas = [
                f"{(n.rx_reac ** 2 + n.ry_reac ** 2 + n.rz_reac ** 2) ** 0.5:.1f}"
                for n in restringidos
            ]
            self.plotter.add_point_labels(
                cent, etiquetas, font_size=10, text_color=color,
                shape=None, always_visible=True,
            )

        self.plotter.reset_camera()
        self.plotter.view_isometric()

    def guardar_captura(self, ruta: str) -> bool:
        """Guarda una captura de la vista 3D actual (PNG/JPG) en `ruta`.

        Returns:
            True si se guardó correctamente, False si falló.
        """
        try:
            self.plotter.screenshot(ruta)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # MÉTODOS INTERNOS — Helpers para dibujar elementos, nodos, etiquetas
    # ------------------------------------------------------------------ #

    def _dibujar_elementos(self, elementos, coords, color, color_columna,
                            opacidad: float = 1.0, radio: float = 0.05):
        """Dibuja elementos estructurales como tubos 3D.

        Args:
            elementos: Lista de elementos con nodo_i, nodo_j, tipo.
            coords: Dict {tag: (x, y, z)} con coordenadas.
            color: Color para vigas.
            color_columna: Color para columnas.
            opacidad: Opacidad (0.0 a 1.0).
            radio: Radio del tubo.
        """
        for el in elementos:
            p1 = coords.get(el.nodo_i)
            p2 = coords.get(el.nodo_j)
            if p1 is None or p2 is None:
                continue
            linea = pv.Line(p1, p2)
            tubo = linea.tube(radius=radio)
            # Columnas en azul claro, vigas en azul medio
            c = color_columna if el.tipo == "columna" else color
            actor = self.plotter.add_mesh(tubo, color=c, opacity=opacidad,
                                           smooth_shading=True)
            self._actor_elementos.append(actor)

    def _dibujar_nodos(self, nodos, deformado: bool, escala: float = 1.0):
        """Dibuja nodos como esferas, con apoyos en color distinto.

        Args:
            nodos: Lista de nodos.
            deformado: Si True, usa coordenadas deformadas.
            escala: Escala para coordenadas deformadas.
        """
        puntos, colores = [], []
        for n in nodos:
            p = n.coord_deformada if deformado else n.coord
            puntos.append(p)
            colores.append(COLOR_NODO_FIJO if n.restringido else COLOR_NODO)

        # Nube de puntos para todos los nodos
        nube = pv.PolyData(np.array(puntos))
        nube["color"] = colores
        self._actor_nodos = self.plotter.add_mesh(
            nube, scalars=None, color=COLOR_NODO, point_size=10,
            render_points_as_spheres=True,
        )
        # Apoyos (nodos fijos) más grandes y en rojo
        fijos = np.array([n.coord for n in nodos if n.restringido])
        if len(fijos):
            self.plotter.add_mesh(pv.PolyData(fijos), color=COLOR_NODO_FIJO,
                                   point_size=16, render_points_as_spheres=True)

    def _dibujar_etiquetas(self, nodos):
        """Dibuja labels con el tag de cada nodo.

        Args:
            nodos: Lista de nodos.
        """
        puntos = [n.coord for n in nodos]
        etiquetas = [str(n.tag) for n in nodos]
        self.plotter.add_point_labels(
            puntos, etiquetas, font_size=10, text_color=COLOR_NODO,
            shape=None, always_visible=True,
        )
