"""
frontend/render_html.py — toma el árbol genérico de backend.core.build_budget_tree()
y genera el reporte HTML interactivo (estilo Opus/Neodata).

No conoce SQL ni DBF: solo recibe una lista de nodos con el contrato de datos
descrito en ARQUITECTURA_CONVERSION.md (sección 3.1).

Uso:
    from backend.core import build_budget_tree
    from frontend.render_html import render
    tree = build_budget_tree("D60JALISCOT.sqlite")
    render(tree, "presupuesto.html", titulo="VIVIENDA D60")
"""
import json

_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Presupuesto de Obra — __TITULO__</title>
<style>
  :root{ --azul:#1c3f6e; --azul2:#274d80; --cap1:#dde6f0; --cap2:#eaf0f7;
         --linea:#c7d2de; --texto:#1d2733; --suave:#5a6679; --verde:#1d6b3f; }
  *{box-sizing:border-box;}
  body{margin:0;font-family:"Segoe UI",Tahoma,Arial,sans-serif;background:#f4f6f9;
       color:var(--texto);font-size:13px;}
  header{background:linear-gradient(180deg,var(--azul),var(--azul2));color:#fff;padding:18px 24px;}
  header h1{margin:0;font-size:18px;}
  header .sub{margin-top:4px;font-size:12px;color:#cfe0f5;}
  .toolbar{display:flex;gap:10px;align-items:center;background:#fff;border-bottom:1px solid var(--linea);
           padding:8px 24px;position:sticky;top:0;flex-wrap:wrap;}
  .toolbar input{flex:1;min-width:200px;padding:6px 10px;border:1px solid var(--linea);border-radius:4px;}
  .toolbar button{padding:6px 12px;border:1px solid var(--linea);background:#f0f3f7;border-radius:4px;cursor:pointer;}
  .stat{font-size:11px;color:var(--suave);margin-left:auto;}
  .wrap{padding:14px 24px 60px;max-width:1280px;margin:0 auto;}
  .tablehead{display:grid;grid-template-columns:32px 150px 1fr 70px 90px 100px 120px;
             background:var(--azul);color:#fff;font-size:11px;text-transform:uppercase;border-radius:6px 6px 0 0;}
  .tablehead div{padding:8px 10px;}
  .tree{background:#fff;border:1px solid var(--linea);border-top:none;border-radius:0 0 6px 6px;}
  .row{display:grid;grid-template-columns:32px 150px 1fr 70px 90px 100px 120px;
       align-items:center;border-bottom:1px solid #eef1f5;}
  .row:hover{background:#f5f8fc;}
  .row>div{padding:6px 10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .row .num{text-align:right;font-variant-numeric:tabular-nums;}
  .row.cap{font-weight:600;}
  .row.cap.n1{background:var(--cap1);} .row.cap.n2{background:var(--cap2);}
  .row.cap .num{color:var(--verde);font-weight:700;}
  .toggle{cursor:pointer;text-align:center;color:var(--suave);font-size:11px;width:14px;display:inline-block;}
  .toggle.leaf{visibility:hidden;}
  .desc-cell{display:flex;align-items:center;gap:6px;}
  .clave{font-family:monospace;font-size:11.5px;color:#34507a;background:#eef3fa;
         padding:1px 6px;border-radius:3px;white-space:nowrap;}
  .row.con .clave{background:transparent;color:var(--suave);padding-left:0;}
  .children.collapsed{display:none;}
  .empty-desc{color:#a3acb8;font-style:italic;}
  footer{text-align:center;color:var(--suave);font-size:11px;padding:18px;}
</style>
</head>
<body>
<header><h1>Presupuesto de Obra</h1><div class="sub">__TITULO__ · vista estilo Opus/Neodata</div></header>
<div class="toolbar">
  <button id="btnExpand">Expandir todo</button>
  <button id="btnCollapse">Colapsar todo</button>
  <input type="text" id="buscador" placeholder="Buscar por clave o descripción…">
  <div class="stat" id="stat"></div>
</div>
<div class="wrap">
  <div class="tablehead"><div></div><div>Clave</div><div>Descripción</div><div>Unidad</div>
       <div>Cantidad</div><div>P.U.</div><div>Importe</div></div>
  <div class="tree" id="tree"></div>
</div>
<footer>Generado automáticamente desde SQLite — presupuesto_builder.py + export_html.py</footer>
<script>
const DATA = __TREE_JSON__;
const fmtMoney = v => v == null ? '' : '$' + Number(v).toLocaleString('es-MX', {minimumFractionDigits:2, maximumFractionDigits:2});
const fmtQty = v => v == null ? '' : Number(v).toLocaleString('es-MX', {maximumFractionDigits:4});
function esc(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function rowHtml(node, depth){
  const hasKids = node.hijos && node.hijos.length > 0;
  const indent = depth * 14;
  const claveHtml = node.clave ? `<span class="clave">${esc(node.clave)}</span>` : '';
  const descClass = node.desc === '(sin descripción)' ? 'empty-desc' : '';
  const rowClass = node.es_capitulo ? `cap n${Math.min(depth+1,5)}` : 'con';
  let html = `<div class="row ${rowClass}" data-clave="${esc(node.clave||'')}" data-desc="${esc(node.desc||'')}">`;
  html += `<div class="toggle${hasKids?'':' leaf'}" data-toggle="${node.id}">${hasKids?'▾':''}</div>`;
  html += `<div style="padding-left:${node.es_capitulo?10:indent}px">${claveHtml}</div>`;
  html += `<div class="desc-cell ${descClass}" style="padding-left:${node.es_capitulo?indent:0}px" title="${esc(node.desc||'')}">${esc(node.desc||'')}</div>`;
  html += `<div>${esc(node.unidad||'')}</div><div class="num">${fmtQty(node.cantidad)}</div>`;
  html += `<div class="num">${fmtMoney(node.precio)}</div><div class="num">${fmtMoney(node.importe)}</div></div>`;
  if(hasKids){
    html += `<div class="children" id="children-${node.id}">`;
    for(const c of node.hijos) html += rowHtml(c, depth+1);
    html += `</div>`;
  }
  return html;
}
function countLeaves(nodes){ let n=0; for(const x of nodes){ if(!x.es_capitulo) n++; n+=countLeaves(x.hijos);} return n; }
function countAll(nodes){ let n=0; for(const x of nodes){ n++; n+=countAll(x.hijos);} return n; }
const container = document.getElementById('tree');
container.innerHTML = DATA.map(n => rowHtml(n, 0)).join('');
container.addEventListener('click', e => {
  const t = e.target.closest('[data-toggle]'); if(!t) return;
  const kids = document.getElementById('children-' + t.getAttribute('data-toggle')); if(!kids) return;
  const collapsed = kids.classList.toggle('collapsed');
  t.textContent = collapsed ? '▸' : '▾';
});
document.getElementById('stat').textContent = `${countLeaves(DATA)} conceptos · ${countAll(DATA)} renglones`;
document.getElementById('btnExpand').onclick = () => {
  document.querySelectorAll('.children.collapsed').forEach(el => el.classList.remove('collapsed'));
  document.querySelectorAll('.toggle').forEach(el => { if(el.textContent) el.textContent = '▾'; });
};
document.getElementById('btnCollapse').onclick = () => {
  document.querySelectorAll('.children').forEach(el => el.classList.add('collapsed'));
  document.querySelectorAll('.toggle').forEach(el => { if(el.textContent) el.textContent = '▸'; });
};
document.getElementById('buscador').addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase();
  document.querySelectorAll('.row').forEach(row => {
    const match = !q || (row.dataset.clave+row.dataset.desc).toLowerCase().includes(q);
    row.style.display = match ? '' : 'none';
    if(match && q){
      let el = row.closest('.children');
      while(el){ el.classList.remove('collapsed');
        const t = document.querySelector(`[data-toggle="${el.id.replace('children-','')}"]`);
        if(t) t.textContent = '▾';
        el = el.parentElement ? el.parentElement.closest('.children') : null; }
    }
  });
});
</script>
</body>
</html>
"""


def render(tree, out_path, titulo="Obra"):
    html = _TEMPLATE.replace("__TITULO__", titulo)
    html = html.replace("__TREE_JSON__", json.dumps(tree, ensure_ascii=False))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    from backend.core import build_budget_tree

    db = sys.argv[1] if len(sys.argv) > 1 else "D60JALISCOT.sqlite"
    out = sys.argv[2] if len(sys.argv) > 2 else "presupuesto.html"
    tree = build_budget_tree(db)
    render(tree, out, titulo="VIVIENDA D60")
    print("Generado:", out)
