#!/usr/bin/env python3
"""95_libro.py — ensambla el libro COMPLETO por la ruta A: compone todas las páginas
sobre el PDF original (vectorial) y escribe los marcadores en español.

COMPUERTA DE VALIDACIÓN (obligatoria para el libro completo): si no existe
qa/validacion-total.tsv con cobertura de TODAS las páginas (ver _validacion.py), el
entregable sale como *-BORRADOR.pdf. Escape consciente: --sin-validar.

Uso:
  venv/bin/python 95_libro.py                # libro completo (exige validación total)
  venv/bin/python 95_libro.py 5 20           # rango (para pruebas; sin compuerta)
  venv/bin/python 95_libro.py --sin-validar  # entrega sin validación (bajo tu riesgo)
"""
import importlib.util, sys
from pathlib import Path

import fitz

SC = Path(__file__).resolve().parent
P = SC.parent
sys.path.insert(0, str(SC))
import _proyecto
import _validacion

_spec = importlib.util.spec_from_file_location("d", SC / "90_digital.py")
_d = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_d)

SIN_VALIDAR = "--sin-validar" in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
ini, fin = (int(_args[0]), int(_args[1])) if len(_args) >= 2 else (1, None)

_spec2 = importlib.util.spec_from_file_location("ind", SC / "97_indice.py")
_ind = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(_ind)


def portada(doc):
    """Portada con título en efecto contorno (N copias desplazadas + relleno claro).
    Se activa solo si proyecto.json declara:
      "portada": {"zona": [x0,y0,x1,y1], "caja": [x0,y0,x1,y1], "titulo": "…",
                  "tamano": 52, "color": "white", "contorno": "black"}
    La zona se redacta (texttrace incluido); la caja recibe el título."""
    cfg = _proyecto.get("portada")
    if not cfg:
        return
    page = doc[0]
    zona = fitz.Rect(cfg["zona"])
    ext = fitz.Rect(zona)
    for sp in page.get_texttrace():
        for ch in sp["chars"]:
            g = fitz.Rect(ch[3])
            if g.intersects(zona):
                ext |= g
    page.add_redact_annot(ext)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    caja = fitz.Rect(cfg.get("caja", cfg["zona"]))
    html = cfg.get("titulo", _proyecto.titulo_es())
    base = ("* {font-family:serif; font-weight:bold; font-variant:small-caps;"
            f" font-size:{cfg.get('tamano', 52)}px; text-align:center; margin:0; color:%s;}}")
    for dx, dy in ((-1.6, -1.6), (1.6, -1.6), (-1.6, 1.6), (1.6, 1.6), (0, 2.2), (0, -2.2)):
        page.insert_htmlbox(caja + (dx, dy, dx, dy), html, css=base % cfg.get("contorno", "black"), scale_low=0.5)
    page.insert_htmlbox(caja, html, css=base % cfg.get("color", "white"), scale_low=0.5)
    print("  p1: portada compuesta")

doc = _d.abre()
fin = fin or len(doc)
for pg in range(ini, fin + 1):
    try:
        if pg == 1 and _proyecto.get("portada"):
            portada(doc)                 # la portada va por composición especial
        elif pg == _proyecto.get("pagina_indice"):
            _ind.compone_indice(doc)     # el índice va por composición especial
        else:
            _d.compone(pg, doc)
    except Exception as e:
        print(f"  p{pg}: ERROR {e}")

toc = [[1, titulo, pagina] for pagina, titulo in _proyecto.secciones() if ini <= pagina <= fin]
if toc and ini == 1:
    doc.set_toc(toc)

salida = P / "render" / f"{_proyecto.slug()}-es.pdf"
completo = ini == 1 and fin == len(doc)
if ini > 1 or fin < len(doc):
    doc.select(list(range(ini - 1, fin)))
    salida = P / "render" / f"{_proyecto.slug()}-es-{ini}-{fin}.pdf"
if completo:
    ok, motivo = _validacion.estado(P, fin)
    if ok:
        print(f"✓ {motivo}")
    elif SIN_VALIDAR:
        print(f"⚠ ENTREGA SIN VALIDACIÓN TOTAL (--sin-validar): {motivo}")
    else:
        salida = P / "render" / f"{_proyecto.slug()}-es-BORRADOR.pdf"
        print("⛔ VALIDACIÓN TOTAL EN↔ES PENDIENTE — el entregable sale como BORRADOR.")
        print(f"   Motivo: {motivo}")
        print("   Haz la validación (SKILL.md §F7.5), registra qa/validacion-total.tsv")
        print("   y relanza. Escape consciente: --sin-validar.")
doc.save(str(salida), deflate=True, deflate_images=True, deflate_fonts=True, garbage=4)
tam = salida.stat().st_size / 1e6
print(f"✓ {salida} ({tam:.1f} MB)")
