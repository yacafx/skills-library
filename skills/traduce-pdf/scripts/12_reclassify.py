#!/usr/bin/env python3
"""12_reclassify.py — Re-etiqueta tipos de bloque en corpus/ocr/*.json SIN re-OCR.
Reusa las cajas guardadas y la función clasificar() vigente de 11_corpus.py.
Uso: venv/bin/python 12_reclassify.py
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import importlib
m = importlib.import_module("11_corpus")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from collections import Counter
tot = Counter(); n = 0
for f in sorted(glob.glob(os.path.join(BASE, "corpus", "ocr", "pag-*.json"))):
    d = json.load(open(f))
    src = os.path.join(BASE, "corpus", "render300", f"pag-{d['page']:03d}.jpg")
    if not os.path.exists(src):
        continue
    im = Image.open(src)
    for ln in d["lines"]:
        t, c = m.clasificar(im, ln, d["w"], d["h"])
        ln["type"], ln["col"] = t, c
    json.dump(d, open(f, "w"), ensure_ascii=False)
    tot.update(l["type"] for l in d["lines"]); n += 1
print(f"re-etiquetadas: {n} páginas")
print("líneas por tipo:", dict(tot.most_common()))
