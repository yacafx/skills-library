#!/usr/bin/env python3
"""30_compose.py v2 — Compone páginas ES sobre el fondo original.
ES json por página: { "b00": "texto", "b01": "~"(solo parche), "b02": null(dejar original),
  "b03": {"t":"...", "type":"h1", "dropcap":"L", "extiende":["b04","b05"] | "resto-L" | "resto-R", "size": 9.0},
  "__statblocks__": [ {"col":"R"|"L"|"F", "cols":2, "size":8.8, "titulo":"...", "sub":"*...*",
      "secciones":[ {"h":null,"t":"**Clase de Armadura** ..."},
                    {"tabla":[["FUE","26 (+8)"],["DES","15 (+2)"],...]},
                    {"h":"ACCIONES","t":"***Ataque múltiple.*** ..."} ] } ] }
Marcado: **negrita-cursiva de entradilla** → <b><i>; *cursiva*; ‹sc›versalitas‹/sc›; \n\n párrafo; «• » viñeta.
"""
import json, os, re, subprocess, sys, html
from PIL import Image, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = "/private/tmp/claude-501/-Users-yacafx/2d3aac53-d252-4802-92c5-5898f7207585/scratchpad/compose"
F = os.path.join(BASE, "plantillas", "fuentes", "patched")
os.makedirs(SCRATCH, exist_ok=True)

GRANATE = "#701f2e"; DORADO = "#c9a44a"; TINTA = "#221a14"; ROJOSTAT = "#9c2b1e"
FONTFILE = {"cuerpo": f"{F}/Bookinsanity-ES.otf", "readaloud": f"{F}/ScalySans-ES.otf",
            "stat": f"{F}/ScalySans-ES.otf", "titulo": f"{F}/NodestoCapsCondensed-Bold-ES.otf"}
_fc = {}
def fuente(path, px):
    k = (path, max(int(px), 6))
    if k not in _fc: _fc[k] = ImageFont.truetype(path, k[1])
    return _fc[k]

def limpia(t): return re.sub(r"\*\*|\*|‹sc›|‹/sc›", "", t)

def simula(texto, fpath, spx, ancho, track=1.0):
    fnt = fuente(fpath, spx); lineas = 0
    for para in texto.split("\n\n"):
        para = limpia(para).strip()
        if not para: continue
        cur = 0.0; lineas += 1
        for w in para.split():
            ww = fnt.getlength(w + " ") * track
            if cur + ww > ancho and cur > 0: lineas += 1; cur = ww
            else: cur += ww
    return lineas

HOEFLER = "/System/Library/Fonts/Hoefler Text.ttc"

def ajusta(texto, tipo, size_pt, leading_px, bbox):
    if tipo not in ("cuerpo", "readaloud", "stat"):
        return size_pt, leading_px, 0.0, True
    # las cajas de Vision inflan la altura en bloques cortos: el interlineado real manda
    size_pt = max(min(size_pt, leading_px/300*72*0.80), 4.0)  # piso: leading degenerado en fragmentos de una línea
    fpath = FONTFILE.get(tipo, FONTFILE["cuerpo"])
    ancho = bbox[2] - bbox[0]
    alto = (bbox[3] - bbox[1]) + leading_px * 0.3
    for tr, lf, sf in [(0,1,1),(-.01,1,1),(-.01,.97,1),(-.015,.97,1),
                       (-.015,.96,.972),(-.02,.94,.972),(-.02,.93,.945),
                       (-.02,.92,.92),(-.025,.90,.90)]:
        spt = size_pt*sf; lead = leading_px*lf
        n = simula(texto, fpath, spt/72*300, ancho, 1+tr)
        if n*lead*0.985 <= alto:
            return round(spt,2), round(lead,1), tr, True
    return round(spt,2), round(lead,1), tr, False

def encoge_titular(texto, tipo, size_pt, bbox_w_px):
    """cabeceras y títulos: una sola línea por segmento ⏎, encogidas para caber"""
    lineas = [limpia(x.strip()) for x in texto.split("⏎")]
    if tipo == "titulo":
        f = ImageFont.truetype(FONTFILE["titulo"], 100)
        factor = 1.0
    else:
        f = ImageFont.truetype(HOEFLER, 100, index=0)
        factor = 0.94   # las versalitas reales miden un poco menos que las CAPS
    spx = size_pt/72*300
    peor = 1.0
    for ln in lineas:
        w = f.getlength(ln.upper()) / 100.0 * spx * factor
        if w > bbox_w_px:
            peor = min(peor, bbox_w_px / w)
    return round(size_pt * max(peor, 0.62), 2), len(lineas)

def m2h(t):
    t = html.escape(t).replace("&amp;nbsp;", "&nbsp;")
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", t, flags=re.S)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t, flags=re.S)
    t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t, flags=re.S)
    t = t.replace("‹sc›", '<span class="sc">').replace("‹/sc›", "</span>")
    out = []
    for p in (x.strip() for x in t.split("\n\n")):
        if not p: continue
        cls = ' class="bullet"' if p.startswith("•") else ""
        out.append(f"<p{cls}>{p}</p>")
    return "".join(out)

def color_parche(im, bbox, oscuro=False):
    x0,y0,x1,y1 = [int(v) for v in bbox]
    x0,y0 = max(0,x0-4), max(0,y0-4); x1,y1 = min(im.width,x1+4), min(im.height,y1+4)
    px = list(im.crop((x0,y0,x1,y1)).convert("RGB").getdata())
    srt = sorted(px, key=sum)
    seg = srt[:int(len(srt)*0.5)] if oscuro else srt[int(len(srt)*0.6):]
    seg = seg or srt
    r,g,b = (sum(p[i] for p in seg)//len(seg) for i in range(3))
    return f"#{r:02x}{g:02x}{b:02x}"

def pt(v): return v/300*72

def compone(pg):
    eb = json.load(open(f"{BASE}/traduccion/en-bloques/pag-{pg:03d}.json"))
    es = json.load(open(f"{BASE}/traduccion/es/pag-{pg:03d}.json"))
    W,H = eb["w"], eb["h"]; Wc = W/2
    Wpt, Hpt = pt(W), pt(H)
    bgfile = f"{BASE}/corpus/render300/pag-{pg:03d}.jpg"
    im = Image.open(bgfile).convert("RGB")
    bloques = {b["id"]: b for b in eb["blocks"]}
    absorbidos = set(); fitrep = []; parches = []; textos = []
    divs = None  # (se separan parches y textos: todos los parches van debajo de todo el texto)

    # --- statblocks estructurados
    for sb in es.get("__statblocks__", []):
        lado = sb.get("col","F")
        def enlado(b):
            cx = (b["bbox"][0]+b["bbox"][2])/2
            return lado=="F" or (lado=="L" and cx<Wc) or (lado=="R" and cx>=Wc)
        core = [b for b in eb["blocks"] if b["type"] in ("stat","stat_h") and enlado(b)]
        if sb.get("caja"):
            x0, y0, x1, y1 = sb["caja"]
        elif not core:
            print(f"p{pg}: statblock sin bloques {lado}"); continue
        else:
            x0 = min(b["bbox"][0] for b in core); y0 = min(b["bbox"][1] for b in core)
            x1 = max(b["bbox"][2] for b in core); y1 = max(b["bbox"][3] for b in core)
        for b in eb["blocks"]:   # absorbe todo lo que caiga dentro
            cx = (b["bbox"][0]+b["bbox"][2])/2; cy = (b["bbox"][1]+b["bbox"][3])/2
            if x0-30<=cx<=x1+30 and y0-30<=cy<=y1+30 and b["id"] not in es:
                absorbidos.add(b["id"])
                bb2 = b["bbox"]  # el parche DEBE cubrir también lo absorbido (si no, su EN queda visible)
                x0, y0 = min(x0, bb2[0]), min(y0, bb2[1])
                x1, y1 = max(x1, bb2[2]), max(y1, bb2[3])
        pcol = color_parche(im, [x0,y0,x1,y1])
        pad=8
        parches.append(f'<div class="patch" style="left:{pt(x0)-pad:.1f}pt;top:{pt(y0)-pad:.1f}pt;'
                    f'width:{pt(x1-x0)+2*pad:.1f}pt;height:{pt(y1-y0)+2*pad:.1f}pt;background:{pcol}"></div>')
        size = sb.get("size", 8.8)
        ncols = sb.get("cols", 2)
        spx = size/72*300
        gap_px = 14/72*300
        colw_px = (x1-x0 - gap_px*(ncols-1)) / ncols
        piezas = []   # (html, alto_px estimado)
        if sb.get("titulo"):
            piezas.append((f'<div class="sbt">{html.escape(sb["titulo"])}</div>', spx*1.85*(2 if len(sb["titulo"])>26 and ncols==1 else 1)))
        if sb.get("sub"):
            piezas.append((f'<div class="sbs">{m2h(sb["sub"])}</div>', spx*1.75))
        SSF = FONTFILE["stat"]
        for sec in sb["secciones"]:
            if "tabla" in sec:
                cells = "".join(f"<td><div class='ab'>{a}</div><div>{v}</div></td>" for a,v in sec["tabla"])
                piezas.append((f'<table class="abt"><tr>{cells}</tr></table>', spx*3.4))
            else:
                if sec.get("h"):
                    piezas.append((f'<div class="sbh">{html.escape(sec["h"])}</div>', spx*2.1))
                paras = sec["t"].split("\n\n")
                for pa in paras:
                    n = simula(pa, SSF, spx, colw_px)
                    piezas.append((f'<div class="sbx">{m2h(pa)}</div>', n*spx*1.26 + spx*0.5))
        total = sum(h for _,h in piezas)
        objetivo = total/ncols * 1.06
        cols_html = [[] for _ in range(ncols)]; acum = 0.0; ci = 0
        for htmlp, hp in piezas:
            if ci < ncols-1 and acum + hp*0.5 > objetivo:
                ci += 1; acum = 0.0
            cols_html[ci].append(htmlp); acum += hp
        for k in range(ncols):
            cx0 = x0 + k*(colw_px+gap_px)
            textos.append(f'<div class="blk sbwrap" style="left:{pt(cx0):.1f}pt;top:{pt(y0):.1f}pt;'
                        f'width:{pt(colw_px):.1f}pt;font-size:{size}pt">{"".join(cols_html[k])}</div>')
        fitrep.append({"id":"__sb__","tipo":"statblock","size":size,
                       "cabe": total <= (y1-y0+2*pad)*ncols})

    # --- extiende / resto-X
    for bid, val in list(es.items()):
        if isinstance(val, dict) and "extiende" in val:
            ext = val["extiende"]
            if ext in ("resto-L","resto-R"):
                lado = ext[-1]
                ids = [b["id"] for b in eb["blocks"] if b["id"]!=bid and b["id"] not in es
                       and b["id"] not in absorbidos
                       and (((b["bbox"][0]+b["bbox"][2])/2 < Wc) == (lado=="L"))]
            else: ids = ext
            bb = bloques[bid]["bbox"][:]
            for i in ids:
                if i in bloques:
                    b2 = bloques[i]["bbox"]; absorbidos.add(i)
                    bb = [min(bb[0],b2[0]),min(bb[1],b2[1]),max(bb[2],b2[2]),max(bb[3],b2[3])]
            bloques[bid] = {**bloques[bid], "bbox": bb}

    # --- caja explícita (huecos de OCR adjudicados contra render; gana sobre el hull)
    for bid, val in es.items():
        if isinstance(val, dict) and "caja" in val and bid in bloques:
            bloques[bid] = {**bloques[bid], "bbox": list(val["caja"])}

    # --- bloques normales
    for b in eb["blocks"]:
        bid = b["id"]
        if bid in absorbidos: continue
        val = es.get(bid)
        if val is None: continue                    # dejar original (arte/mapas F5)
        tipo, drop, size_o = b["type"], b["meta"].get("dropcap"), None
        txt = val
        if isinstance(val, dict):
            txt = val.get("t","")
            tipo = val.get("type", tipo); drop = val.get("dropcap", drop)
            size_o = val.get("size")
        bb = bloques[bid]["bbox"]
        oscuro = tipo=="caption"
        pcol = color_parche(im, bb, oscuro=oscuro)
        pad = 6
        parches.append(f'<div class="patch" style="left:{pt(bb[0])-pad:.1f}pt;top:{pt(bb[1])-pad:.1f}pt;'
                    f'width:{pt(bb[2]-bb[0])+2*pad:.1f}pt;height:{pt(bb[3]-bb[1])+2*pad:.1f}pt;background:{pcol}"></div>')
        if txt == "~": continue                     # solo parche
        TITULARES = ("titulo","kicker","h1","h2","h_mayor","stat_h","footer")
        if tipo in TITULARES:
            cxb = (bb[0]+bb[2])/2
            borde = 0.487*W if cxb < Wc else 0.940*W
            avail = max(bb[2]-bb[0], borde-bb[0]) if tipo not in ("titulo","kicker","footer") else (bb[2]-bb[0])*1.02
            spt, nlin = encoge_titular(txt, tipo, size_o or b["size_pt"], avail)
            fitrep.append({"id":bid,"tipo":tipo,"size":spt,"track":0,"cabe":True})
            wpt = pt(avail)
            ytop = pt(bb[1]) - 0.05*spt
            st = f"top:{ytop:.1f}pt;font-size:{spt}pt;line-height:1.12;white-space:nowrap;"
            if tipo in ("titulo","kicker"):
                if isinstance(val, dict) and val.get("caja"):   # centrado DENTRO de su caja
                    st += f"left:{pt(bb[0]):.1f}pt;width:{pt(bb[2]-bb[0]):.1f}pt;text-align:center;"
                else:
                    st += f"left:0;width:{Wpt:.1f}pt;text-align:center;"
            elif tipo == "footer":
                st += f"left:{pt(bb[0])-40:.1f}pt;width:{wpt+43:.1f}pt;text-align:right;"
            else:
                st += f"left:{pt(bb[0]):.1f}pt;width:{wpt+6:.1f}pt;"
            cls = tipo
            if tipo in ("h1","h2","h_mayor") and (size_o or b["size_pt"]) >= 11:
                cls += " conregla"
                st = st.replace("white-space:nowrap;", f"white-space:nowrap;")
            # titulares = contenido INLINE puro (un <p> dentro de un <span> genera línea fantasma)
            inner = html.escape(limpia(txt) if tipo != "titulo" else limpia(txt)).replace("⏎","<br>")
            if "conregla" in cls:
                textos.append(f'<div class="blk {cls}" style="{st}"><span class="txtreg" style="border-bottom:1pt solid #c9a44a;padding-bottom:1.5pt">{inner}</span></div>')
            else:
                textos.append(f'<div class="blk {cls}" style="{st}">{inner}</div>')
            continue
        # caja + size explícitos = el autor manda: interlineado derivado del size, sin tope del OCR
        lead_in = (size_o/72*300*1.34) if (isinstance(val, dict) and val.get("caja") and size_o) else b["leading_px"]
        spt, lead, tr, cabe = ajusta(txt, tipo, size_o or b["size_pt"], lead_in, bb)
        fitrep.append({"id":bid,"tipo":tipo,"size":spt,"track":tr,"cabe":cabe})
        lpt = pt(lead)
        st = f"left:{pt(bb[0]):.1f}pt;top:{pt(bb[1]):.1f}pt;width:{pt(bb[2]-bb[0])+3:.1f}pt;"
        st += f"font-size:{spt}pt;line-height:{lpt:.2f}pt;"
        if tr: st += f"letter-spacing:{tr}em;"
        cls = tipo
        inner = m2h(txt)
        if drop:
            inner = f'<span class="drop">{drop}</span>' + inner
        textos.append(f'<div class="blk {cls}" style="{st}">{inner}</div>')

    Wpt, Hpt = pt(W), pt(H)
    doc = f"""<html lang="es"><head><meta charset="utf-8"><style>
@page {{ size:{Wpt:.2f}pt {Hpt:.2f}pt; margin:0 }} html,body{{margin:0}}
@font-face{{font-family:BI;src:url("{F}/Bookinsanity-ES.otf")}}
@font-face{{font-family:BI;src:url("{F}/Bookinsanity-Italic-ES.otf");font-style:italic}}
@font-face{{font-family:BI;src:url("{F}/Bookinsanity-Bold-ES.otf");font-weight:700}}
@font-face{{font-family:BI;src:url("{F}/Bookinsanity-BoldItalic-ES.otf");font-weight:700;font-style:italic}}
@font-face{{font-family:SS;src:url("{F}/ScalySans-ES.otf")}}
@font-face{{font-family:SS;src:url("{F}/ScalySans-Italic-ES.otf");font-style:italic}}
@font-face{{font-family:SS;src:url("{F}/ScalySans-Bold-ES.otf");font-weight:700}}
@font-face{{font-family:SS;src:url("{F}/ScalySans-BoldItalic-ES.otf");font-weight:700;font-style:italic}}
@font-face{{font-family:SSC;src:url("{F}/ScalySansCaps-ES.otf")}}
@font-face{{font-family:SSC;src:url("{F}/ScalySansCaps-Bold-ES.otf");font-weight:700}}
@font-face{{font-family:NB;src:url("{F}/NodestoCapsCondensed-Bold-ES.otf")}}
.page{{position:relative;width:{Wpt:.2f}pt;height:{Hpt:.2f}pt}}
.bg{{position:absolute;left:0;top:0;width:100%;height:100%}}
.patch{{position:absolute}} .blk{{position:absolute;color:{TINTA}}}
.blk p{{margin:0;text-indent:9pt}} .blk p:first-child{{text-indent:0}}
.blk p.bullet{{text-indent:-7pt;padding-left:7pt}}
.cuerpo{{font-family:BI;text-align:justify;hyphens:auto}}
.readaloud{{font-family:SS;text-align:justify;hyphens:auto;color:#332a20}}
.stat{{font-family:SS;hyphens:auto;color:#2b2117}} .stat p{{text-indent:0;margin-bottom:1.5pt}}
.caption{{font-family:"Hoefler Text";font-variant-caps:small-caps;color:#f2ecdc;letter-spacing:.1em}}
.h1,.h2,.h_mayor{{font-family:"Hoefler Text";font-variant-caps:small-caps;color:{GRANATE}}}
.conregla .txtreg{{border-bottom:1pt solid {DORADO};padding-bottom:1pt}}
.titulo{{font-family:NB;color:{GRANATE};line-height:1.04}}
.kicker{{font-family:"Hoefler Text";font-variant-caps:small-caps;letter-spacing:.32em;color:#4a3c30}}
.footer{{font-family:"Hoefler Text";font-variant-caps:small-caps;color:#8a2433;text-align:right}}
.sc{{font-variant-caps:small-caps;font-family:"Hoefler Text"}}
.drop{{float:left;font-family:NB;color:{GRANATE};font-size:30pt;line-height:.82;padding:1.5pt 3pt 0 0}}
.sbwrap{{font-family:SS;color:#2b2117;line-height:1.24}}
.sbt{{font-family:SSC;color:{GRANATE};font-size:1.55em;line-height:1.05}}
.sbs{{font-style:italic;margin-bottom:3pt}}
.sbh{{font-family:SSC;color:{GRANATE};font-size:1.2em;border-bottom:.8pt solid {ROJOSTAT};margin:4pt 0 2pt}}
.sbx p{{text-indent:0;margin:0 0 2.5pt}}
.abt{{width:100%;border-collapse:collapse;border-top:1.6pt solid {ROJOSTAT};border-bottom:1.6pt solid {ROJOSTAT};margin:3pt 0}}
.abt td{{text-align:center;padding:1.5pt 0}} .abt .ab{{font-weight:700}}
i{{font-style:italic}} b{{font-weight:700}}
</style></head><body><div class="page"><img class="bg" src="{bgfile}">
{chr(10).join(parches)}
{chr(10).join(textos)}
</div></body></html>"""
    hpath = os.path.join(SCRATCH, f"pag-{pg:03d}.html")
    open(hpath,"w").write(doc)
    outpdf = f"{BASE}/render/paginas/pag-{pg:03d}.pdf"
    r = subprocess.run(["weasyprint", hpath, outpdf], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"p{pg} weasyprint ERROR:", r.stderr[-300:]); return False
    subprocess.run(["pdftoppm","-r","150","-png","-singlefile",outpdf,
                    f"{BASE}/render/paginas/pag-{pg:03d}"], check=True)
    json.dump(fitrep, open(f"{BASE}/qa/fit/pag-{pg:03d}.json","w"), ensure_ascii=False, indent=1)
    mal = [f["id"] for f in fitrep if not f["cabe"]]
    print(f"p{pg}: {len(fitrep)} bloques, overflow={len(mal)}" + (f" ← {mal}" if mal else " ✓"))
    return not mal

if __name__ == "__main__":
    os.makedirs(f"{BASE}/qa/fit", exist_ok=True)
    ok = sum(bool(compone(int(a))) for a in sys.argv[1:])
    print(f"sin overflow: {ok}/{len(sys.argv)-1}")
