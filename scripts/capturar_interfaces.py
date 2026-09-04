"""
capturar_interfaces.py
======================
Captura automática de capturas de pantalla de las principales interfaces
de Open APU Studio para documentación.

Uso (desde la raíz del repo):
    .venv/bin/python scripts/capturar_interfaces.py
    .venv/bin/python scripts/capturar_interfaces.py --proyecto D60JALISCOT
    .venv/bin/python scripts/capturar_interfaces.py --tema oscuro --acento azul
    .venv/bin/python scripts/capturar_interfaces.py --solo 01-presupuesto 03-insumos

Cómo funciona:
    - Arranca QApplication + VentanaPrincipal sin mostrar ventana (offscreen
      no es fiable en todas las plataformas; por defecto se usa una ventana
      real de tamaño fijo pero la renderización es idéntica).
    - Abre un proyecto .db de datos_usuario/proyectos/.
    - Navega programaáticamente a cada vista y usa widget.grab() (renderizado
      directo de Qt, sin depender de captura de pantalla del sistema).
    - Guarda cada captura como PNG en capturas/<n>.png determinístico y
      también con el nombre amigable en capturas/<n>-<vista>.png.

Opciones:
    --proyecto NOMBRE   Proyecto .db a usar (default: D60JALISCOT).
    --tema modo         Oscuro|claro (default: oscuro).
    --acento acento     azul|rosa|cafe|verde (default: azul).
    --solo A,B,C        Captura solo las vistas indicadas (por prefijo de índice).
    --guardar DIR       Carpeta de salida (default: capturas/).
    --fuente 'familia'  Familia tipográfica (default: Segoe UI).
    --pantalla WxH      Tamaño de ventana (default: 1440x900).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os = __import__("os")
if sys.platform != "win32":
    # En Linux/macOS Si no hay display, Qt intenta usar offscreen. Se conserva
    # el renderizado real (mismos estilos), útil para CI.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--proyecto", default="D60JALISCOT")
    parser.add_argument("--tema", default="oscuro", choices=["oscuro", "claro"])
    parser.add_argument("--acento", default="azul", choices=["azul", "rosa", "cafe", "verde"])
    parser.add_argument("--solo", default=None, help="Prefijos de índice a capturar, separados por coma")
    parser.add_argument("--guardar", default="capturas")
    parser.add_argument("--fuente", default="Segoe UI")
    parser.add_argument("--pantalla", default="1440x900")
    args = parser.parse_args()

    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Open APU Studio")
    app.setOrganizationName("OpenAPU")
    app.setWindowIcon(QIcon(str(ROOT / "assets" / "favicon.ico")))

    w, h = (int(x) for x in args.pantalla.lower().split("x"))

    from frontend.temas import Temas
    modo, acento = args.tema, args.acento
    # Solo se aplica en memoria: no tocar config.json del usuario.
    Temas.aplicar(app, modo, acento)

    if args.fuente:
        app.setFont(QFont(args.fuente, 10))

    from frontend.ventana import VentanaPrincipal
    win = VentanaPrincipal()
    # Sobrescribir el tema que la ventana leyó de config.json por el pedido
    # (afecta el tint de los iconos recolorables y los colores de la cinta).
    win._tema_modo = modo
    win._tema_acento = acento
    from frontend.ventana.colores import TEXT, TEXT_INVERSO
    from frontend.ventana.iconos import set_default_tint
    set_default_tint(TEXT if modo == "oscuro" else TEXT_INVERSO)
    win._update_label_colors() if hasattr(win, "_update_label_colors") else None
    win.resize(w, h)
    win.show()
    app.processEvents()

    salida = Path(args.guardar)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "vistas.txt").write_text(
        "Capturas generadas por scripts/capturar_interfaces.py\n"
        f"Proyecto: {args.proyecto} | Tema: {modo} | Acento: {acento}\n"
        f"Fecha: {__import__('datetime').datetime.now().isoformat(timespec='minutes')}\n",
        encoding="utf-8",
    )

    cap = Capturador(win, app, args.proyecto, salida)

    vistas = [
        ("01", "presupuesto",           cap.presupuesto),
        ("02", "insumos-materiales",    cap.insumos_materiales),
        ("03", "insumos-todos",         cap.insumos_todos),
        ("04", "apu",                   cap.apu),
        ("05", "explosion-insumos",     cap.explosion_insumos),
        ("06", "explosion-matrices",    cap.explosion_matrices),
        ("07", "rastreo-uso",           cap.rastreo),
        ("08", "buscar-partidas",       cap.buscar_partidas),
        ("09", "fuera-presupuesto",     cap.fuera_presupuesto),
    ]

    solo = {p.strip() for p in args.solo.split(",")} if args.solo else None

    for idx, nombre, fn in vistas:
        if solo is not None and not any(idx.startswith(p) or nombre.startswith(p)
                                        for p in solo):
            continue
        print(f"[capturar] {idx} {nombre} …", flush=True)
        try:
            fn()
        except Exception as e:
            print(f"  ERROR capturando {nombre}: {e}", flush=True)
            continue
        app.processEvents()
        px = win.grab()
        fichero = salida / f"{idx}-{nombre}.png"
        ok = px.save(str(fichero))
        print(f"  -> {'OK' if ok else 'FALLO'} {fichero}", flush=True)
        try:
            tab_actual = win._tabs.tabText(win._tabs.currentIndex())
        except Exception:
            tab_actual = "(sin pestañas)"
        with (salida / "vistas.txt").open("a", encoding="utf-8") as fh:
            fh.write(f"{idx}-{nombre}.png  <-  tab activa: {tab_actual}\n")

    # Limpieza sin cerrar de golpe (evita warning de grabación)
    win.close()
    app.processEvents()
    return 0


class Capturador:
    """Navega VentanaPrincipal a cada vista a capturar."""

    def __init__(self, win, app, proyecto, salida: Path):
        self.win = win
        self.app = app
        self.salida = salida
        self._abrir_proyecto(proyecto)

    # ── helpers ──────────────────────────────────────────────────────
    def _procesar(self):
        self.app.processEvents()

    def _primera_pestana(self, title):
        """Devuelve el índice de la pestaña normal con ese título (o None)."""
        tabs = self.win._tabs
        for i in range(tabs.count()):
            if tabs.tabText(i) == title:
                return i
        return None

    def _focus_tab(self, title):
        idx = self._primera_pestana(title)
        if idx is None:
            return False
        self.win._tabs.setCurrentIndex(idx)
        self._procesar()
        return True

    def _todos_concepto_ids(self):
        return self.win._api.todos_concepto_ids()

    def _abrir_proyecto(self, nombre):
        from pathlib import Path as P
        from backend.database.db import Database
        ruta = ROOT / "datos_usuario" / "proyectos" / f"{nombre}.db"
        if not ruta.exists():
            raise SystemExit(f"No existe el proyecto {nombre} en {ruta}")
        if self.win._db:
            self.win._db.close()
            self.win._stop_server()
        self.win._db = Database.abrir(ruta)
        self.win._wire_servicios(self.win._db)
        self.win._api.unificar_matrices_apu()
        self.win._reload_presupuesto()
        self.win._update_statusbar()
        self.win._switch_tab("PRINCIPAL")
        self._procesar()

    # ── vistas ───────────────────────────────────────────────────────

    def presupuesto(self):
        self.win._switch_tab("PRINCIPAL")
        self._focus_tab("Presupuesto programable")
        t = self.win._arbol_presupuesto
        if t:
            t.expandAll()
            t.show_todo()
            self._procesar()

    def insumos_materiales(self):
        self.win._switch_tab("PRINCIPAL")
        self.win._open_sidebar_tab("Materiales", temporary=False)

    def insumos_todos(self):
        self.win._switch_tab("PRINCIPAL")
        self.win._open_sidebar_tab("Todos", temporary=False)

    def apu(self):
        """Abre el APU del primer concepto que tenga matriz en el catálogo.

        _abrir_apu_por_id() no abre pestaña si el concepto no tiene APU, así
        que se itera sobre los conceptos hasta que la pestaña 'APU: …' exista.
        """
        api = self.win._api
        tabs = self.win._tabs
        for concepto in api.conceptos_planos():
            nodo_id = concepto.get("id")
            if not nodo_id:
                continue
            antes = tabs.count()
            self.win._abrir_apu_por_id(nodo_id)
            self._procesar()
            if tabs.count() > antes:
                # se abrió una pestaña: es la actual
                tabs.setCurrentIndex(tabs.count() - 1)
                self._procesar()
                return
        # Ningún concepto con APU: intentar con un insumo compuesto directo
        for ins in api.insumos():
            if ins.get("es_compuesto"):
                self.win._abrir_apu_insumo(ins["id"])
                self._procesar()
                if any(tabs.tabText(i).startswith("APU") for i in range(tabs.count())):
                    return

    def explosion_insumos(self):
        # Explosión de insumos abre un diálogo modal; aquí se preselecciona
        # "todo el árbol" llamando a PestañaExplosion directamente.
        from frontend.ventana.widgets.explosion import PestañaExplosion
        api = self.win._api
        concepto_ids = api.todos_concepto_ids()
        if not concepto_ids:
            return
        filas, total_g = api.explotar(concepto_ids=concepto_ids, nivel="basico",
                                      tipos_ids=[1, 2, 4, 8, 16])
        if not filas:
            return
        tipos_nombres = api.resumen_tipos_explosion([1, 2, 4, 8, 16])
        resumen = {"nivel": "basico", "n_conceptos": len(concepto_ids),
                   "tipos_nombres": tipos_nombres}
        pestaña = PestañaExplosion(filas, total_g, resumen,
                                   on_apu_click=self.win._abrir_apu_insumo,
                                   on_rastrear=self.win._on_rastrear_insumo)
        pestaña.conectar_eventos(self.win._event_bus, self.win._api)
        idx = self.win._tabs.addTab(pestaña, "Explosión de insumos")
        self.win._tabs.setCurrentIndex(idx)
        self._procesar()

    def explosion_matrices(self):
        self.win._switch_tab("PRINCIPAL")
        w = self.win._build_matriz_explosion()
        if w is None:
            return
        idx = self.win._tabs.addTab(w, "Explosión de matrices")
        self.win._tabs.setCurrentIndex(idx)
        self._procesar()

    def rastreo(self):
        api = self.win._api
        # rastrear el primer insumo que aparezca en alguna matriz
        for concepto in api.conceptos_planos():
            insumo_id = concepto.get("insumo_id")
            if insumo_id:
                self.win._on_rastrear_insumo(insumo_id)
                return

    def buscar_partidas(self):
        self.win._switch_tab("PRINCIPAL")
        self.win._open_sidebar_tab("Buscar partidas", temporary=False)

    def fuera_presupuesto(self):
        self.win._switch_tab("PRINCIPAL")
        self.win._open_sidebar_tab("Fuera de presupuesto", temporary=False)


if __name__ == "__main__":
    raise SystemExit(main())