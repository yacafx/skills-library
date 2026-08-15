#!/usr/bin/env python3
"""97_indice.py — composición especial de la página de ÍNDICE (p3).

Cada línea del índice es «Título .... N»: se reemplaza SOLO el segmento del título
(hasta el arranque de los puntos líder), conservando puntos y número de página.
Las capas de sombra duplican cada palabra («Table Table of of...»): se desduplican.
Los títulos se traducen una vez (caché en traduccion/es/indice.json) con el modelo
local + glosario; los títulos de sección van fijados a proyecto.json.
"""
import importlib.util, json, re, sys
from pathlib import Path

import fitz

SC = Path(__file__).resolve().parent
P = SC.parent
sys.path.insert(0, str(SC))
import _proyecto

_spec = importlib.util.spec_from_file_location("d", SC / "90_digital.py")
_d = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_d)
_t = _d._t

# Títulos de sección fijos: decláralos en proyecto.json como "indice_fijos"
# {"Table of Contents": "Índice", "Chapter 1: Races": "Capítulo 1: Razas", ...}
FIJOS = _proyecto.get("indice_fijos", {})
CACHE = P / "traduccion" / "es" / "indice.json"


def _dedup(palabras):
    out = []
    for w in palabras:
        if not out or out[-1][4] != w[4] or abs(out[-1][0] - w[0]) > 2:
            out.append(w)
    return out


def entradas(page):
    """[(rect_titulo, titulo_en, limite_x)] por columna, sin puntos ni números."""
    todas = [w for w in page.get_text("words") if 30 < w[3] < 810]
    cols = {0: {}, 1: {}}
    for w in todas:
        col = 0 if w[0] < 300 else 1
        cols[col].setdefault(round(w[3] / 3), []).append(w)
    raw = page.get_text("rawdict")
    res = []
    for col in (0, 1):
        for k in sorted(cols[col]):
            ws = _dedup(sorted(cols[col][k], key=lambda w: w[0]))
            tit = []
            for w in ws:
                if re.fullmatch(r"\.{2,}|\d{1,3}|\.*", w[4]):
                    break
                tit.append(w)
            if not tit:
                continue
            texto = " ".join(w[4] for w in tit).strip()
            texto = re.sub(r"\s*\.+$", "", texto)
            if not re.search(r"[A-Za-z]{2}", texto):
                continue
            r = fitz.Rect(tit[0][:4])
            for w in tit[1:]:
                r |= fitz.Rect(w[:4])
            # dígitos FUSIONADOS al final del título («Background114»): se recortan del
            # texto y el límite pasa al primer dígito (posición real por caracteres)
            m = re.search(r"^(.*?[A-Za-z&][.…]*)(\d{1,3})$", texto)
            limite = None
            if m:
                texto = m.group(1).rstrip(" .")
                for b in raw["blocks"]:
                    for ln in b.get("lines", []):
                        for sp in ln["spans"]:
                            for ch in sp["chars"]:
                                cr = fitz.Rect(ch["bbox"])
                                if ch["c"].isdigit() and cr.intersects(r) and (limite is None or cr.x0 < limite):
                                    limite = cr.x0
                if limite is not None:
                    r.x1 = limite - 0.5
            # límite: primer run de puntos o número en la MISMA línea visual (los números
            # de líneas con fuente mayor caen en otro grupo-y, así que se busca global)
            for w in todas:
                if w[0] <= r.x0 + 10 or (0 if w[0] < 300 else 1) != col:
                    continue
                solape = min(r.y1, w[3]) - max(r.y0, w[1])
                if solape > 3 and re.fullmatch(r"\.{2,}|\d{1,3}", w[4]):
                    limite = w[0] if limite is None else min(limite, w[0])
            res.append((r, texto, limite))
    return res


def traducciones(titulos):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    faltan = [t for t in titulos if t not in cache and t not in FIJOS]
    glos = _d.glosario_pagina("\n".join(faltan))
    for j in range(0, len(faltan), 12):
        lote = {str(i): t for i, t in enumerate(faltan[j:j + 12])}
        for _ in range(3):
            msj = [{"role": "system", "content": _t.REGLAS +
                    "\n- Son TÍTULOS de un índice: traduce cada uno breve y en su caso oficial."
                    + ("\n\nGLOSARIO:\n" + glos if glos else "")},
                   {"role": "user", "content": json.dumps(lote, ensure_ascii=False)}]
            try:
                r = json.loads(_t.ollama(MOD_LOCAL, msj, timeout=600))
            except Exception:
                continue
            ok = True
            for i, t in lote.items():
                v = _d.desenvuelve(r.get(i, ""))
                if v:
                    cache[t] = re.sub(r"‹[^›]*›|[«»]", "", v).strip()
                else:
                    ok = False
            if ok:
                break
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    return {**cache, **FIJOS}


MOD_LOCAL = _proyecto.get("modelo", "qwen3.5:35b-a3b-coding-nvfp4")


def compone_indice(doc, pg=None):
    pg = pg or _proyecto.get("pagina_indice", 3)
    page = doc[pg - 1]
    ents = entradas(page)
    mapa = traducciones([t for _, t, _l in ents])
    glifos = [fitz.Rect(ch[3]) for sp in page.get_texttrace() for ch in sp["chars"]]
    trazos = []
    for dr in page.get_drawings():
        tr = fitz.Rect(dr["rect"])
        if 3 < tr.height < 60 and tr.width < page.rect.width * 0.9:
            trazos.append(tr)
    tareas = []
    for r, en, limite in ents:
        es = mapa.get(en, "").strip()
        if not es or es == en:
            if not re.search(r"[A-Za-z]", en) or en in ("SI:7",):
                continue
            es = es or en
        est = _d._estilo_en(page, r)
        # tope duro: jamás invadir los puntos líder ni el número de página
        techo_x = (limite - 1.5) if limite else (r.x1 + 24)
        ext = fitz.Rect(r)
        zona = fitz.Rect(r.x0 - 2, r.y0 - 2, min(r.x1 + 2, techo_x), r.y1 + 2)
        for g in glifos:
            if g.intersects(zona):
                ext |= (g & fitz.Rect(r.x0 - 6, r.y0 - 6, techo_x, r.y1 + 3))
        for tzr in trazos:
            if tzr.intersects(zona) and (tzr & zona).get_area() > tzr.get_area() * 0.5:
                ext |= (tzr + (-1, -1, 1, 1))
        ext.x1 = min(ext.x1, techo_x)
        page.add_redact_annot(ext)
        tareas.append((fitz.Rect(r.x0, r.y0, techo_x, r.y1), es, est))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    import html as H
    for r, es, (tam0, col0, neg0, ser0) in tareas:
        rgb = f"rgb({col0 >> 16 & 255},{col0 >> 8 & 255},{col0 & 255})"
        fam = "serif" if ser0 else "sans-serif"
        cuerpo = f"<b>{H.escape(es)}</b>" if neg0 else H.escape(es)
        caja = fitz.Rect(r.x0 - 1, r.y0 - 1, r.x1 + 1, r.y1 + 2)
        for factor in (1.0, 0.92, 0.84, 0.76, 0.68, 0.6, 0.52):
            css = (f"* {{font-family:{fam}; font-size:{tam0*factor:.1f}px; color:{rgb};"
                   f" margin:0; line-height:1.05; white-space:nowrap;}}")
            sobra, _ = page.insert_htmlbox(caja, cuerpo, css=css, scale_low=0.5)
            if sobra >= 0:
                break
    print(f"  p{pg}: índice compuesto ({len(tareas)} entradas)")


if __name__ == "__main__":
    doc = _d.abre()
    compone_indice(doc)
    doc.select([2])
    out = P / "render" / "paginas" / "indice-es.pdf"
    doc.save(str(out), deflate=True)
    print(f"✓ {out}")
