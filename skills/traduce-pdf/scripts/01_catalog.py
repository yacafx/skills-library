#!/usr/bin/env python3
"""01_catalog.py — Catálogo inicial de páginas + hojas de contacto de páginas escasas.
Clases heurísticas: arte (<40 palabras), escasa (40–150), texto (>150).
Las 'arte'/'escasa' se revisan visualmente (hojas de contacto) y se refinan a: arte | mapa | mixta | portada.
Uso: venv/bin/python 01_catalog.py
"""
import csv, glob, os, re, subprocess, sys
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import _proyecto
PDF = str(_proyecto.pdf_origen())
IMG = os.path.join(BASE, "corpus", "img")
OCR = os.path.join(BASE, "corpus", "ocr")
QA = os.path.join(BASE, "qa")

# 1) Texto de la capa OCR original (borrador; el re-OCR bueno llega en F1)
raw_path = os.path.join(OCR, "raw-en-capa-original.txt")
if not os.path.exists(raw_path):
    subprocess.run(["pdftotext", "-enc", "UTF-8", PDF, raw_path], check=True)
pages = open(raw_path, encoding="utf-8", errors="replace").read().split("\f")

# 2) Mapa página→archivo jpg
jpgs = {}
for p in glob.glob(os.path.join(IMG, "pag-*.jpg")):
    m = re.match(r"pag-(\d{3})-\d+\.jpg", os.path.basename(p))
    if m:
        jpgs[int(m.group(1))] = p

# 3) Catálogo
rows = []
for i in range(1, 259):
    words = len(pages[i-1].split()) if i-1 < len(pages) else 0
    if i == 1:
        clase = "portada"
    elif i == 258:
        clase = "contraportada"
    elif words < 40:
        clase = "arte?"      # a refinar visualmente
    elif words < 150:
        clase = "escasa?"    # a refinar visualmente
    else:
        clase = "texto"
    rows.append({"pdf_page": i, "book_page": i-1 if 1 < i < 258 else "",
                 "words": words, "clase": clase, "notas": "",
                 "jpg": os.path.basename(jpgs.get(i, ""))})

with open(os.path.join(BASE, "corpus", "catalogo.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

# 4) progress.csv (fuente de verdad de avance por página)
with open(os.path.join(BASE, "progress.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["pdf_page", "ocr", "trad", "fondo", "comp", "v4", "v5"])
    for r in rows:
        w.writerow([r["pdf_page"], "", "", "", "", "", ""])

# 5) Hojas de contacto de las páginas a refinar
review = [r for r in rows if r["clase"] in ("arte?", "escasa?")]
print(f"páginas texto: {sum(1 for r in rows if r['clase']=='texto')}")
print(f"a revisar visualmente: {len(review)} -> {[r['pdf_page'] for r in review]}")

COLS, ROWS_G, TH = 6, 5, 300
per_sheet = COLS * ROWS_G
for s in range(0, len(review), per_sheet):
    chunk = review[s:s+per_sheet]
    sheet = Image.new("RGB", (COLS*TH, ROWS_G*(TH+24)), "#222")
    d = ImageDraw.Draw(sheet)
    for k, r in enumerate(chunk):
        if r["pdf_page"] not in jpgs:
            continue
        im = Image.open(jpgs[r["pdf_page"]])
        im.thumbnail((TH, TH))
        x, y = (k % COLS)*TH, (k // COLS)*(TH+24)
        sheet.paste(im, (x + (TH-im.width)//2, y))
        d.text((x+4, y+TH+4), f"p{r['pdf_page']} ({r['words']}w)", fill="#fff")
    out = os.path.join(QA, f"contacto-revisar-{s//per_sheet+1}.png")
    sheet.save(out)
    print("hoja:", out)
