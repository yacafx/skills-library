#!/usr/bin/env python3
"""23_bloques.py — Agrupa líneas OCR en BLOQUES traducibles por página.
- agrupa líneas consecutivas de mismo (type, col) con hueco vertical pequeño
- deshifena («ne-» + «crotic» → «necrotic»), une líneas con espacio
- detecta párrafos por sangría
- dropcap se fusiona como meta del bloque siguiente
Salida: traduccion/en-bloques/pag-NNN.json  {page,w,h,blocks:[{id,type,col,bbox,size_pt,leading,text,meta}]}
Uso: venv/bin/python 23_bloques.py [ini fin]
"""
import json, os, sys, glob, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "corpus", "ocr")
DST = os.path.join(BASE, "traduccion", "en-bloques")
os.makedirs(DST, exist_ok=True)

JOINABLE = {"cuerpo", "readaloud", "stat", "caption", "h1", "h2", "h_mayor", "titulo", "footer", "kicker"}

def agrupar(d):
    H, W = d["h"], d["w"]
    lines = [l for l in d["lines"] if l["type"] not in ("folio", "credito")]
    # normalización: títulos partidos y kickers son de ancho completo
    for l in lines:
        if l["type"] in ("titulo", "h_mayor") and l["y"] < H * 0.16:
            l["type"] = "titulo"; l["col"] = "F"
        if l["type"] in ("kicker", "footer"):
            l["col"] = "F"
    # flujos por columna: agrupar dentro de cada flujo evita intercalado L/R
    lines.sort(key=lambda l: (l["col"], l["y"], l["x"]))
    bloques = []
    for l in lines:
        b = bloques[-1] if bloques else None
        if (b and l["type"] == b["type"] and l["col"] == b["col"]
                and l["type"] in JOINABLE
                and l["y"] - (b["_last_y"] + b["_last_h"]) < b["_med_h"] * 0.75
                and abs(l["x"] - b["bbox"][0]) < d["w"] * 0.25):
            b["_lines"].append(l)
            b["_last_y"], b["_last_h"] = l["y"], l["h"]
            b["_hs"].append(l["h"])
            b["_med_h"] = statistics.median(b["_hs"])
            x0, y0, x1, y1 = b["bbox"]
            b["bbox"] = [min(x0, l["x"]), min(y0, l["y"]),
                         max(x1, l["x"] + l["w"]), max(y1, l["y"] + l["h"])]
        else:
            bloques.append({"type": l["type"], "col": l["col"],
                            "bbox": [l["x"], l["y"], l["x"]+l["w"], l["y"]+l["h"]],
                            "_lines": [l], "_last_y": l["y"], "_last_h": l["h"],
                            "_hs": [l["h"]], "_med_h": l["h"]})
    out = []
    dropcap = None
    bloques.sort(key=lambda b: (b["bbox"][1], {"F": 0, "L": 1, "R": 2}[b["col"]]))
    for i, b in enumerate(bloques):
        ls = b["_lines"]
        if b["type"] == "dropcap":
            dropcap = ls[0]["t"].strip()
            continue
        # párrafos por sangría + deshifenado
        xs = [l["x"] for l in ls]
        x_base = min(xs)
        med_h = statistics.median(b["_hs"])
        partes = []
        for j, l in enumerate(ls):
            t = l["t"].strip()
            nueva_para = j > 0 and (l["x"] - x_base) > med_h * 0.7 and b["type"] in ("cuerpo", "stat")
            if j == 0:
                partes.append(t)
            elif nueva_para:
                partes.append("\n\n" + t)
            else:
                prev = partes[-1]
                if prev.endswith("-") and t and t[0].islower():
                    partes[-1] = prev[:-1] + t          # deshifenar
                else:
                    partes[-1] = prev + " " + t
        texto = "".join(partes)
        # interlineado: mediana de saltos y
        ys = [l["y"] for l in ls]
        leading = statistics.median([ys[k+1]-ys[k] for k in range(len(ys)-1)]) if len(ys) > 1 else med_h*1.3
        blk = {"id": f"b{len(out):02d}", "type": b["type"], "col": b["col"],
               "bbox": [round(v, 1) for v in b["bbox"]],
               "size_pt": round(med_h/300*72, 2), "leading_px": round(leading, 1),
               "text": texto, "meta": {}}
        if dropcap and b["type"] == "cuerpo":
            blk["meta"]["dropcap"] = dropcap
            dropcap = None
        out.append(blk)
    return out

if __name__ == "__main__":
    a, b = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1, 258)
    n = 0; tb = 0
    for f in sorted(glob.glob(os.path.join(SRC, "pag-*.json"))):
        d = json.load(open(f))
        if not (a <= d["page"] <= b):
            continue
        blocks = agrupar(d)
        json.dump({"page": d["page"], "w": d["w"], "h": d["h"], "blocks": blocks},
                  open(os.path.join(DST, os.path.basename(f)), "w"), ensure_ascii=False, indent=1)
        n += 1; tb += len(blocks)
    print(f"páginas: {n}, bloques: {tb}, promedio {tb/max(n,1):.1f}/pág")
