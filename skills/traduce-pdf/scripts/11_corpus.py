#!/usr/bin/env python3
"""11_corpus.py — Corpus EN completo: Vision OCR + clasificador de bloques v1.
Por página: corpus/ocr/pag-NNN.json  {page, w, h, lines:[{t,x,y,w,h,c,type,col}]}
Tipos v1: titulo, kicker, h_mayor, h1, h2, h3, cuerpo, readaloud, stat, caption, folio, footer, credito, otro
Heurísticas: color de tinta (rojo/negro/blanco), color de fondo (pergamino/panel lila/panel ocre/arte),
altura de línea, posición. Actualiza progress.csv (col ocr).
Uso: venv/bin/python 11_corpus.py [pag_ini pag_fin]
"""
import sys, os, json, glob, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import importlib
vis = importlib.import_module("10_ocr_vision")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R300 = os.path.join(BASE, "corpus", "render300")
OUT = os.path.join(BASE, "corpus", "ocr")

def clasificar(im, ln, W, H):
    x, y, w, h = ln["x"], ln["y"], ln["w"], ln["h"]
    cx, cy = x + w/2, y + h/2
    # muestreo de tinta: pixeles oscuros dentro de la caja
    box = im.crop((max(0,int(x)), max(0,int(y)), min(W,int(x+w)), min(H,int(y+h)))).convert("RGB")
    px = list(box.getdata())
    if not px:
        return "otro", "?"
    # tinta = promedio del 5 % más oscuro; fondo = mediana
    srt = sorted(px, key=sum)
    k = len(srt)//20 or 1
    core = [sum(c)//k for c in zip(*srt[:k])]
    med = srt[len(srt)//2]
    brillo_med = sum(sum(p) for p in px) / (3*len(px))
    rojo = core[0] >= 20 and (core[0] - (core[1]+core[2])/2.0) >= 9
    t = ln["t"].strip()
    caps = t.upper() == t and any(ch.isalpha() for ch in t)
    caption = brillo_med < 120 and sum(1 for p in px if sum(p) >= 600) >= len(px)*0.08
    panel_ocre = med[0] >= 200 and (med[0] - med[2]) >= 30
    lig = srt[-(len(srt)//5 or 1):]
    bg = [sum(c)//len(lig) for c in zip(*lig)]
    panel_lila = (not panel_ocre) and 200 <= bg[0] <= 235 and 195 <= bg[1] <= 230 and 205 <= bg[2] <= 240 and bg[2] >= bg[1]
    col = "L" if cx < W*0.5 else "R"
    if w > W*0.6: col = "F"  # ancho completo
    hpt = h/300*72
    # 1) posición
    if y > H*0.952:
        return ("folio" if w < W*0.06 else "footer"), col
    if h > W*0.004 and w < W*0.035 and h > w*3:
        return "credito", col
    if y < H*0.055 and w < W*0.35 and abs(cx - W/2) < W*0.22:
        return "kicker", col
    # 2) paneles (antes que el color de tinta: el ocre contamina el canal R)
    if panel_ocre:
        return ("stat_h" if (rojo and caps and hpt >= 11) else "stat"), col
    if panel_lila:
        return "readaloud", col
    # 3) tinta roja (cabeceras siempre en versalitas/caps en este libro)
    if rojo and hpt >= 20 and len(t) <= 2:
        return "dropcap", col
    if rojo and caps:
        if hpt >= 20: return "titulo", col
        if hpt >= 16.5: return "h_mayor", col
        if hpt >= 12: return "h1", col
        return "h2", col
    if caption:
        return "caption", col
    return "cuerpo", col

def procesar(n):
    src = os.path.join(R300, f"pag-{n:03d}.jpg")
    if not os.path.exists(src):
        return None
    r = vis.ocr(src)
    im = Image.open(src)
    W, H = r["w"], r["h"]
    for ln in r["lines"]:
        t, c = clasificar(im, ln, W, H)
        ln["type"], ln["col"] = t, c
    r["page"] = n
    dst = os.path.join(OUT, f"pag-{n:03d}.json")
    json.dump(r, open(dst, "w"), ensure_ascii=False)
    return r

if __name__ == "__main__":
    a, b = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1, 258)
    from collections import Counter
    tot = Counter(); done = 0
    for n in range(a, b+1):
        r = procesar(n)
        if r:
            done += 1
            tot.update(l["type"] for l in r["lines"])
            if n % 25 == 0:
                print(f"  ...página {n} ({done} hechas)")
    print(f"páginas procesadas: {done}")
    print("líneas por tipo:", dict(tot.most_common()))
    # progress.csv col ocr
    pp = os.path.join(BASE, "progress.csv")
    rows = list(csv.reader(open(pp)))
    hechas = {int(os.path.basename(f)[4:7]) for f in glob.glob(os.path.join(OUT, "pag-*.json"))}
    for row in rows[1:]:
        if int(row[0]) in hechas:
            row[1] = "ok"
    csv.writer(open(pp, "w")).writerows(rows)
    print("progress.csv actualizado")
