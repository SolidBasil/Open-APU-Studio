"""
main.py — orquesta:  .DBF/.FPT  -->  backend (SQLite + árbol)  -->  frontend (HTML)

Uso:
    python main.py --uploads /mnt/user-data/uploads --out D60JALISCOT.sqlite \
                    --html presupuesto.html --titulo "VIVIENDA D60"

Para PyQt, en tu app usarías en vez de --html:
    from backend.core import build_budget_tree
    from frontend.render_pyqt import PresupuestoModel
    modelo = PresupuestoModel(build_budget_tree("D60JALISCOT.sqlite"))
"""
import argparse

from backend.core import convert_directory, run_default_checks, build_budget_tree, count_nodes, count_concepts
from frontend.render_html import render as render_html


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--uploads", required=True)
    p.add_argument("--out", default="D60JALISCOT.sqlite")
    p.add_argument("--html", default=None)
    p.add_argument("--titulo", default="Obra")
    args = p.parse_args()

    print("== Convirtiendo DBF -> SQLite ==")
    convert_directory(args.uploads, args.out)

    print("\n== Validando ==")
    print(run_default_checks(args.out))

    print("\n== Construyendo árbol ==")
    tree = build_budget_tree(args.out)
    print(f"{count_nodes(tree)} nodos, {count_concepts(tree)} conceptos")

    if args.html:
        render_html(tree, args.html, titulo=args.titulo)
        print("Generado:", args.html)

    return tree


if __name__ == "__main__":
    main()
