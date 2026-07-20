"""
mixins/
=======
Paquete de mixins que se mezclan en VentanaPrincipal (ver ventana.py).

Cada archivo es un mixin independiente, sin estado propio de módulo:
    toolbar.py           — ToolbarMixin: toolbar, temas, barra de búsqueda
    paneles.py           — PanelesMixin: sidebar, presupuesto, insumos, buscador
    navegacion.py        — HandlersMixin: navegación, búsqueda, vista, adjuntos
    gestion_proyectos.py — GestionProyectosMixin: lifecycle de proyectos
    informes.py          — InformesMixin: generación de PDF
    diag_dialogs.py       — DiagDialogsMixin: diagnóstico y utilidades
    apu.py                — ApuMixin: pestañas APU y edición
    rastreo.py            — RastreoMixin: rastreo de insumos
    explosion.py          — ExplosionMixin: explosión de insumos/matrices y sobrecostos
    generador.py          — GeneradorMixin: generadores de obra

No confundir con frontend/ventana/widgets/: ahí viven las clases QWidget
reutilizables (TablaApuDetalle, TablaExplosion, TablaGenerador, etc.) que
estos mixins usan. Antes ambos paquetes tenían archivos con el mismo
nombre (apu.py, explosion.py, generador.py) — ya no.
"""
