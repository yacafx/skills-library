#!/usr/bin/env python3
"""20_entidades.py — Candidatos a glosario desde el corpus EN.
a) N-gramas capitalizados fuera de inicio de oración (nombres propios, objetos, lugares)
b) Cabeceras (h1/h2/h_mayor/titulo) únicas — secciones y ubicaciones
c) stat_h — nombres de criatura con bloque propio
Salida: traduccion/candidatos.txt (ordenado por frecuencia)
"""
import json, glob, os, re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP = set("""The A An In On At Of For To From With By As If When While After Before During
Once This That These Those They He She It You Your His Her Its Their Any Each Every All Both
Some No Not And Or But So Yet Nor Chapter Appendix Area Areas If Unless Otherwise See Use Using
Make Making Roll Rolling Read Aloud DC STR DEX CON INT WIS CHA XP HP AC PB D&D""".split())

texto_total = []
headers = Counter()
stat_names = Counter()
for f in sorted(glob.glob(os.path.join(BASE, "corpus", "ocr", "pag-*.json"))):
    d = json.load(open(f))
    for l in d["lines"]:
        t = l["t"].strip()
        if l["type"] in ("h1", "h2", "h_mayor", "titulo"):
            hh = re.sub(r"^[A-Z]\d+:\s*", "", t)  # quita prefijos C1:, Z8:
            if len(hh) > 2:
                headers[hh.title()] += 1
        elif l["type"] == "stat_h":
            stat_names[t.title()] += 1
        if l["type"] in ("cuerpo", "readaloud", "stat"):
            texto_total.append(t)

texto = " ".join(texto_total)
# n-gramas capitalizados (permite of/the/and/de en medio), no tras punto
pat = re.compile(r"(?<![.!?:•—]\s)(?<!^)\b([A-Z][a-zA-Z'’\-]+(?:\s+(?:of|the|and|de|del)\s+[A-Z][a-zA-Z'’\-]+|\s+[A-Z][a-zA-Z'’\-]+)+)\b")
ngramas = Counter(m.group(1) for m in pat.finditer(texto))
# palabras sueltas capitalizadas en medio de oración
pat1 = re.compile(r"(?<=[a-z,;]\s)([A-Z][a-z'’\-]{3,})\b")
solas = Counter(m.group(1) for m in pat1.finditer(texto))
for s in list(solas):
    if s in STOP or any(s in ng for ng in ngramas):
        del solas[s]

out = os.path.join(BASE, "traduccion", "candidatos.txt")
with open(out, "w") as f:
    f.write("== STAT BLOCKS (criaturas con perfil) ==\n")
    for k, v in stat_names.most_common():
        f.write(f"{v:4} {k}\n")
    f.write("\n== CABECERAS ÚNICAS (secciones/ubicaciones) ==\n")
    for k, v in headers.most_common(120):
        f.write(f"{v:4} {k}\n")
    f.write("\n== N-GRAMAS PROPIOS ==\n")
    for k, v in ngramas.most_common(220):
        if v >= 2:
            f.write(f"{v:4} {k}\n")
    f.write("\n== SUELTAS ==\n")
    for k, v in solas.most_common(120):
        if v >= 4:
            f.write(f"{v:4} {k}\n")
print("candidatos ->", out)
print(f"stat:{len(stat_names)} headers:{len(headers)} ngramas:{len(ngramas)} sueltas:{len(solas)}")
