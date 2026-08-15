#!/usr/bin/env python3
"""71_arte.py — F5: páginas de arte/mapas. Enmascara las etiquetas EN (cajas del dump),
reconstruye el fondo con LaMa (70_lama), el MODELO LOCAL traduce las etiquetas y se
componen encima con las fuentes del libro. Salida: render/paginas/pag-NNN.pdf.

Uso: venv/bin/python 71_arte.py PG [PG…] [--sin-texto] [--muestra]
  --sin-texto  solo marca la página como lista (arte puro sin etiquetas)
"""
import argparse, importlib.util, json, re, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SC = Path(__file__).resolve().parent
P = SC.parent
spec = importlib.util.spec_from_file_location("t", SC / "35_traduce_ollama.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
spec_l = importlib.util.spec_from_file_location("lama", SC / "70_lama.py")
L = importlib.util.module_from_spec(spec_l); spec_l.loader.exec_module(L)
import _proyecto
MOD = _proyecto.get("modelo", "qwen3.5:35b-a3b-coding-nvfp4")
FCAPS = str(P / "plantillas" / "fuentes" / "patched" / "ScalySansCaps-ES.otf")
FSANS = str(P / "plantillas" / "fuentes" / "patched" / "ScalySans-ES.otf")


def agrupa(bloques, holgura=70):
    grupos = []
    for b in sorted(bloques, key=lambda x: (x["bbox"][1], x["bbox"][0])):
        bb = b["bbox"]
        for g in grupos:
            gb = g["bbox"]
            if not (bb[0] > gb[2] + holgura or bb[2] < gb[0] - holgura or
                    bb[1] > gb[3] + holgura or bb[3] < gb[1] - holgura):
                g["miembros"].append(b)
                g["bbox"] = [min(gb[0], bb[0]), min(gb[1], bb[1]), max(gb[2], bb[2]), max(gb[3], bb[3])]
                break
        else:
            grupos.append({"miembros": [b], "bbox": list(bb)})
    return grupos


def traduce_lote(textos):
    pedido = {f"e{i}": t for i, t in enumerate(textos)}
    for _ in range(3):
        try:
            msj = [{"role": "system", "content": m.REGLAS + "\n\nGLOSARIO (en = es):\n" + m.glosario_txt()},
                   {"role": "user", "content": "Etiquetas de mapa/captions (cortas, conserva MAYÚSCULAS y códigos): " + json.dumps(pedido, ensure_ascii=False)}]
            r = json.loads(m.ollama(MOD, msj, timeout=900))
            out = [str(r.get(f"e{i}", "")).strip() for i in range(len(textos))]
            if all(out) and all(m.numeros_de(o) == m.numeros_de(t) for o, t in zip(out, textos)):
                return out
        except Exception:
            pass
    return None


def _aplica_fix(t, fix):
    for a, b in fix.items():
        t = t.replace(a, b)
    return t


def ajusta_fuente(texto, fuente, ancho, alto_linea):
    px = int(alto_linea * 0.92)
    while px > 8:
        f = ImageFont.truetype(fuente, px)
        if f.getlength(texto) <= ancho:
            return f
        px -= 2
    return ImageFont.truetype(fuente, 8)


def procesa(pg, lama):
    eb = json.load(open(P / "traduccion" / "en-bloques" / f"pag-{pg:03d}.json"))
    im = Image.open(P / "corpus" / "render300" / f"pag-{pg:03d}.jpg").convert("RGB")
    bloques = [b for b in eb["blocks"] if b["text"].strip()]
    if not bloques:
        guardar(pg, im, eb)
        print(f"p{pg}: sin etiquetas — página tal cual")
        return True
    grupos = agrupa(bloques)
    textos_en = []
    for g in grupos:
        lineas = sorted(g["miembros"], key=lambda b: (b["bbox"][1], b["bbox"][0]))
        g["texto_en"] = re.sub(r"-\n\n", "", " ".join(b["text"] for b in lineas)).replace("\n\n", " ").strip()
        textos_en.append(g["texto_en"])
    tr = traduce_lote(textos_en)
    if tr is None:
        print(f"p{pg}: ✗ traducción de etiquetas falló")
        return False
    FIX = {"HA FUGADO": "HA HUIDO", "PIEZA DE VARA": "PIEZA DE LA VARA",
           "NIVEL DE DUNGEON": "NIVEL DE MAZMORRA", "Ip a ": "Hasta ", "Ip to ": "Hasta ",
           "ha fugado": "ha huido", "pieza de vara": "pieza de la vara"}
    tr = [_aplica_fix(t, FIX) for t in tr]
    # máscara total y LaMa por grupo (con contexto)
    for g, es_t in zip(grupos, tr):
        gb = g["bbox"]
        MARGEN = 150
        x0, y0 = max(0, int(gb[0] - MARGEN)), max(0, int(gb[1] - MARGEN))
        x1, y1 = min(im.width, int(gb[2] + MARGEN)), min(im.height, int(gb[3] + MARGEN))
        crop = im.crop((x0, y0, x1, y1))
        # color del texto original ANTES de borrar: luminancia de extremos en la caja
        zona = np.asarray(crop.convert("L"))[int(gb[1]-y0):int(gb[3]-y0), int(gb[0]-x0):int(gb[2]-x0)]
        fondo_claro = float(np.median(zona)) > 110
        mask = Image.new("L", crop.size, 0)
        dr = ImageDraw.Draw(mask)
        for b in g["miembros"]:
            bb = b["bbox"]
            dr.rectangle([bb[0]-x0-5, bb[1]-y0-5, bb[2]-x0+5, bb[3]-y0+5], fill=255)
        limpio = lama.inpaint(crop, mask)
        # componer texto ES: re-envolver al ancho del grupo, centrado
        n_lineas = max(1, len(g["miembros"]))
        alto_linea = (gb[3] - gb[1]) / n_lineas
        ancho = gb[2] - gb[0]
        fuente = FCAPS if g["texto_en"].isupper() else FSANS
        color = (58, 48, 40) if fondo_claro else (243, 240, 232)
        # tamaño: altura de tinta de una línea original (mediana de cajas miembro)
        alto_tinta = sorted(b["bbox"][3] - b["bbox"][1] for b in g["miembros"])[len(g["miembros"]) // 2]
        px = max(10, int(alto_tinta * 0.98))
        f0 = ImageFont.truetype(fuente, px)
        palabras = es_t.split()
        lineas_es, actual = [], ""
        for w in palabras:
            cand = (actual + " " + w).strip()
            if f0.getlength(cand) <= ancho or not actual:
                actual = cand
            else:
                lineas_es.append(actual); actual = w
        lineas_es.append(actual)
        while len(lineas_es) > n_lineas and px > 9:  # que quepa en las líneas originales
            px -= 2; f0 = ImageFont.truetype(fuente, px)
            lineas_es, actual = [], ""
            for w in palabras:
                cand = (actual + " " + w).strip()
                if f0.getlength(cand) <= ancho or not actual:
                    actual = cand
                else:
                    lineas_es.append(actual); actual = w
            lineas_es.append(actual)
        dl = ImageDraw.Draw(limpio)
        y = gb[1] - y0
        for ln in lineas_es:  # alineado a la IZQUIERDA como el original
            dl.text((gb[0] - x0, y), ln, font=f0, fill=color)
            y += alto_linea
        im.paste(limpio, (x0, y0))
        print(f"  grupo {g['bbox'][:2]}: {g['texto_en'][:40]!r} → {es_t[:40]!r} ({len(lineas_es)} líneas)")
    guardar(pg, im, eb)
    return True


def guardar(pg, im, eb):
    salida = P / "render" / "paginas" / f"pag-{pg:03d}.pdf"
    wpt, hpt = eb["w"] / 300 * 72, eb["h"] / 300 * 72
    im.save(salida, "PDF", resolution=300.0)
    import csv
    rows = list(csv.reader(open(P / "progress.csv")))
    for r in rows[1:]:
        if r and r[0].isdigit() and int(r[0]) == pg:
            r[2] = r[3] = r[4] = r[5] = "f5"
    csv.writer(open(P / "progress.csv", "w")).writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paginas", type=int, nargs="+")
    ap.add_argument("--sin-texto", action="store_true")
    a = ap.parse_args()
    lama = None
    for pg in a.paginas:
        if a.sin_texto:
            eb = json.load(open(P / "traduccion" / "en-bloques" / f"pag-{pg:03d}.json"))
            guardar(pg, Image.open(P / "corpus" / "render300" / f"pag-{pg:03d}.jpg").convert("RGB"), eb)
            print(f"p{pg}: marcada arte-puro")
            continue
        if lama is None:
            lama = L.Lama()
            print(f"LaMa en {lama.device}")
        procesa(pg, lama)
